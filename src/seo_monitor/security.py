import asyncio
import ipaddress
import socket
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit


class UnsafeURLError(ValueError):
    """Raised when a crawl target could reach a private or unsupported resource."""


def normalize_url(url: str) -> str:
    candidate, _ = urldefrag(url.strip())
    parsed = urlsplit(candidate)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsafeURLError("only http and https URLs are supported")
    if not parsed.hostname:
        raise UnsafeURLError("URL must contain a hostname")
    if parsed.username or parsed.password:
        raise UnsafeURLError("credentials in URLs are not supported")

    host = parsed.hostname.encode("idna").decode("ascii").lower()
    port = parsed.port
    default_port = 80 if parsed.scheme.lower() == "http" else 443
    netloc = host if port in {None, default_port} else f"{host}:{port}"
    path = parsed.path or "/"
    return urlunsplit((parsed.scheme.lower(), netloc, path, parsed.query, ""))


async def validate_public_url(url: str, *, allow_private_hosts: bool = False) -> str:
    normalized = normalize_url(url)
    if allow_private_hosts:
        return normalized

    hostname = urlsplit(normalized).hostname
    assert hostname is not None
    try:
        addresses = await asyncio.to_thread(
            socket.getaddrinfo,
            hostname,
            None,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise UnsafeURLError(f"hostname could not be resolved: {hostname}") from exc

    resolved = {ipaddress.ip_address(item[4][0]) for item in addresses}
    if not resolved or any(not address.is_global for address in resolved):
        raise UnsafeURLError("URL resolves to a private, loopback, or reserved address")
    return normalized


def resolve_link(base_url: str, href: str) -> str | None:
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
        return None
    try:
        return normalize_url(urljoin(base_url, href))
    except (UnsafeURLError, ValueError):
        return None


def same_origin(left: str, right: str) -> bool:
    left_url = urlsplit(normalize_url(left))
    right_url = urlsplit(normalize_url(right))
    return (
        left_url.scheme,
        left_url.hostname,
        left_url.port,
    ) == (
        right_url.scheme,
        right_url.hostname,
        right_url.port,
    )

