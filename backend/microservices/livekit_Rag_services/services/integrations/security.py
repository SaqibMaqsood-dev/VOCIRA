"""
What keeps the Integration Hub safe to run.

- A source's error text never carries a credential: scrub() takes every
  secret value and any user:password in a link out of it before it is
  logged, stored in a sync run, or shown on the panel.
- The server fetches what an admin typed in, so an address may only reach
  the public internet, unless the super admin says the system runs on the
  school's own network (allow_private_network) - a school's admin cannot.
"""

import asyncio
import ipaddress
import re
import socket
from urllib.parse import urlparse

_USERINFO = re.compile(r"(?i)(\b[a-z][a-z0-9+.-]*://)[^/\s@]+@")
_BEARER = re.compile(r"(?i)\b(bearer|token|basic)\s+[A-Za-z0-9._~+/=-]{8,}")
_KEYVALUE = re.compile(r"(?i)\b(password|passwd|pwd|secret|api_key|apikey|token|access_token)=([^&\s]+)")


def scrub(text, secrets=None, limit: int = 500) -> str:
    """An error as it may be kept and shown: no secret values, no credentials in links."""
    out = str(text or "")
    for value in (secrets or {}).values():
        value = str(value or "")
        if len(value) >= 4:
            out = out.replace(value, "••••")
    out = _USERINFO.sub(r"\1••••@", out)
    out = _BEARER.sub(r"\1 ••••", out)
    out = _KEYVALUE.sub(r"\1=••••", out)
    return out[:limit]


class AddressError(ValueError):
    """The address may not be reached from the server."""


async def check_host(host: str, port: int | None, allow_private_network: bool) -> None:
    """The host must resolve to public addresses only - unless the school's own network is allowed."""
    if not host:
        raise AddressError("An address is needed.")
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, port or 443)
    except socket.gaierror:
        raise AddressError(f"{host} could not be found - check the address.")
    if allow_private_network:
        return
    for info in infos:
        address = ipaddress.ip_address(info[4][0].split("%")[0])
        if not address.is_global:
            raise AddressError(
                f"{host} is inside a private network. Only public addresses are allowed - the platform's "
                "super admin can allow a system on the school's own network."
            )


async def check_url(url: str, allow_private_network: bool) -> None:
    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise AddressError("The address must be a full link starting with https://")
    await check_host(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), allow_private_network)
