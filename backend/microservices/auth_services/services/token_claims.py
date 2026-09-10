"""
The claims that go into an access token.

Two places mint access tokens - /login and /refresh - and they had
drifted badly. /login wrote sub, user_id, role and name, while
/refresh wrote only sub. verify_jwt requires user_id, so every token
handed out by /refresh was rejected on its first use, and the role and
name the admin panel and navbar read were gone with it.

Building the claims in one place is what stops that happening again.
"""


def role_of(user) -> str | None:
    """
    The role's name, as a plain string.

    user.role is a Role model object, not an enum, so it has a `name`
    and no `value`. str(user.role) on its own yields
    "<...Role object at 0x...>", which is what used to end up in the
    token.
    """
    if user.role is None:
        return None

    if getattr(user.role, "name", None):
        return user.role.name

    if hasattr(user.role, "value"):
        return user.role.value

    return str(user.role)


def access_claims(user) -> dict:
    """
    The payload for create_access_token().

    user_id is what verify_jwt checks for; role is what require_admin
    reads; name is what the UI shows instead of an email address.
    """
    return {
        "sub": user.email,
        "user_id": str(user.user_id),
        "role": role_of(user),
        "name": user.name,
    }


def refresh_claims(user) -> dict:
    """
    The payload for create_refresh_tokken().

    user_id is required: verify_refresh_tokken rejects a refresh token
    without it, so a replacement minted without user_id could never be
    used to refresh again.
    """
    return {
        "sub": user.email,
        "user_id": str(user.user_id),
    }
