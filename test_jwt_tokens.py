"""
JWT token regression tests.

These need no database and no running server - they exercise the mint
and verify helpers directly, which is where the bugs actually were:

  1. /refresh minted its access token as {"sub": ...} only. verify_jwt
     requires user_id, so every renewed session was rejected on its
     first request.

  2. /refresh minted its replacement refresh token the same way.
     verify_refresh_tokken requires user_id too, so a session could be
     refreshed exactly once and never again.

  3. The refresh token's own exp was hardcoded to 1 day while the
     database row recording it was written with 7, so the row outlived
     the token it described by six days.

Run:  python test_jwt_tokens.py
"""

import sys
from datetime import datetime, timedelta, timezone

import jwt

from backend.helper_functions.token_service.access_tokken.jtw_tokken import (
    create_access_token,
)
from backend.helper_functions.token_service.access_tokken.verify_tokken import (
    verify_jwt,
)
from backend.helper_functions.token_service.refresh_tokken.jwt_refresh_tokken import (
    create_refresh_tokken,
)
from backend.helper_functions.token_service.refresh_tokken.verify_refresh_tokken import (
    verify_refresh_tokken,
)
from backend.microservices.auth_services.core.config import settings
from backend.microservices.auth_services.services.token_claims import (
    access_claims,
    refresh_claims,
    role_of,
)


PASSED = []
FAILED = []


def check(name, condition, detail=""):
    if condition:
        PASSED.append(name)
        print(f"  PASS  {name}")
    else:
        FAILED.append((name, detail))
        print(f"  FAIL  {name}{f' - {detail}' if detail else ''}")


class FakeRole:
    """Role is a model object with .name - not an enum with .value."""

    def __init__(self, name):
        self.name = name


class FakeUser:
    def __init__(self, role="guardian"):
        self.user_id = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
        self.email = "parent@example.com"
        self.name = "Muhammad Ahmed"
        self.role = FakeRole(role) if role else None


class Boom(Exception):
    """Stands in for the HTTPException the routers pass in."""


def decode(token):
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


# ---------------------------------------------------------------
# Claims
# ---------------------------------------------------------------

def test_claims():
    print("\nclaims")

    user = FakeUser()

    a = access_claims(user)
    check("access claims carry user_id", a.get("user_id") == str(user.user_id))
    check("access claims carry role", a.get("role") == "guardian")
    check("access claims carry name", a.get("name") == "Muhammad Ahmed")
    check("access claims carry sub", a.get("sub") == user.email)

    r = refresh_claims(user)
    check("refresh claims carry user_id", r.get("user_id") == str(user.user_id))

    check("role_of reads .name", role_of(user) == "guardian")
    check("role_of tolerates no role", role_of(FakeUser(role=None)) is None)

    # The bug this replaced: str() on a Role model object.
    check(
        "role is not a repr string",
        "object at 0x" not in str(a.get("role")),
        str(a.get("role")),
    )


# ---------------------------------------------------------------
# Access token round trip
# ---------------------------------------------------------------

def test_access_token():
    print("\naccess token")

    user = FakeUser(role="admin")
    token = create_access_token(access_claims(user))

    data = verify_jwt(token, Boom("rejected"))

    check("verifies", data is not None)
    check("user_id survives", str(data.user_id) == str(user.user_id))
    check("role survives", data.role == "admin")
    check("username survives", data.username == user.email)

    payload = decode(token)
    check("name is in the token", payload.get("name") == "Muhammad Ahmed")

    # The exact shape /refresh used to mint.
    broken = create_access_token({"sub": user.email})
    try:
        verify_jwt(broken, Boom("rejected"))
        check("a token without user_id is rejected", False, "it was accepted")
    except Boom:
        check("a token without user_id is rejected", True)


# ---------------------------------------------------------------
# Refresh token round trip
# ---------------------------------------------------------------

def test_refresh_token():
    print("\nrefresh token")

    user = FakeUser()
    token = create_refresh_tokken(refresh_claims(user))

    data = verify_refresh_tokken(token, Boom("rejected"))

    check("verifies", data is not None)
    check("user_id survives", str(data.user_id) == str(user.user_id))

    payload = decode(token)
    check("is marked type=refresh", payload.get("type") == "refresh")

    # The exact shape /refresh used to mint for its replacement.
    broken = create_refresh_tokken({"sub": user.email})
    try:
        verify_refresh_tokken(broken, Boom("rejected"))
        check("a refresh token without user_id is rejected", False, "it was accepted")
    except Boom:
        check("a refresh token without user_id is rejected", True)

    # An access token must not pass as a refresh token.
    access = create_access_token(access_claims(user))
    try:
        verify_refresh_tokken(access, Boom("rejected"))
        check("an access token is not accepted as a refresh token", False)
    except Boom:
        check("an access token is not accepted as a refresh token", True)


# ---------------------------------------------------------------
# Lifetimes
# ---------------------------------------------------------------

def test_lifetimes():
    print("\nlifetimes")

    user = FakeUser()
    now = datetime.now(timezone.utc)

    access_exp = datetime.fromtimestamp(
        decode(create_access_token(access_claims(user)))["exp"], tz=timezone.utc
    )
    want = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    check(
        "access token honours ACCESS_TOKEN_EXPIRE_MINUTES",
        abs((access_exp - want).total_seconds()) < 60,
        f"{access_exp.isoformat()} vs {want.isoformat()}",
    )

    refresh_exp = datetime.fromtimestamp(
        decode(create_refresh_tokken(refresh_claims(user)))["exp"], tz=timezone.utc
    )
    want = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    check(
        "refresh token honours REFRESH_TOKEN_EXPIRE_DAYS",
        abs((refresh_exp - want).total_seconds()) < 60,
        f"{refresh_exp.isoformat()} vs {want.isoformat()}",
    )

    # This is what made the setting meaningless: the JWT was minted
    # for a day while the database row said seven.
    check(
        "refresh token outlives the access token",
        refresh_exp > access_exp,
    )


# ---------------------------------------------------------------
# Tampering
# ---------------------------------------------------------------

def test_tampering():
    print("\ntampering")

    user = FakeUser(role="guardian")
    token = create_access_token(access_claims(user))

    # Re-sign with a different key: a forged admin token must not pass.
    # The wrong key is given a realistic length so PyJWT does not warn
    # about a short HMAC key and make this look like a config problem.
    payload = decode(token)
    payload["role"] = "admin"
    forged = jwt.encode(
        payload,
        "an-entirely-different-key-of-a-realistic-length-0123456789",
        algorithm=settings.JWT_ALGORITHM,
    )

    try:
        verify_jwt(forged, Boom("rejected"))
        check("a token signed with another key is rejected", False, "it was accepted")
    except Boom:
        check("a token signed with another key is rejected", True)

    expired = jwt.encode(
        {**payload, "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    try:
        verify_jwt(expired, Boom("rejected"))
        check("an expired token is rejected", False, "it was accepted")
    except Boom:
        check("an expired token is rejected", True)


def main():
    print("=" * 60)
    print("JWT TOKEN TESTS")
    print("=" * 60)
    print(f"algorithm : {settings.JWT_ALGORITHM}")
    print(f"secret    : {len(settings.JWT_SECRET_KEY)} characters")
    print(f"access    : {settings.ACCESS_TOKEN_EXPIRE_MINUTES} minutes")
    print(f"refresh   : {settings.REFRESH_TOKEN_EXPIRE_DAYS} days")

    test_claims()
    test_access_token()
    test_refresh_token()
    test_lifetimes()
    test_tampering()

    print("\n" + "=" * 60)
    print(f"passed {len(PASSED)}, failed {len(FAILED)}")
    for name, detail in FAILED:
        print(f"  FAILED  {name}{f' - {detail}' if detail else ''}")
    print("=" * 60)

    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
