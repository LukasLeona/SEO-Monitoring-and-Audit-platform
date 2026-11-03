import pytest

from seo_monitor.security import UnsafeURLError, normalize_url, validate_public_url


def test_normalize_url_removes_fragment_and_default_port() -> None:
    assert normalize_url("HTTPS://Example.COM:443/path?q=1#section") == (
        "https://example.com/path?q=1"
    )


async def test_private_address_is_rejected() -> None:
    with pytest.raises(UnsafeURLError):
        await validate_public_url("http://127.0.0.1/admin")


async def test_private_address_can_be_enabled_for_local_development() -> None:
    assert (
        await validate_public_url(
            "http://127.0.0.1/test",
            allow_private_hosts=True,
        )
        == "http://127.0.0.1/test"
    )
