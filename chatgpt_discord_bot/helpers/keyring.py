from urllib.parse import urlparse

import keyring


def is_keyring_url(url_or_token: str) -> bool:
    return isinstance(url_or_token, str) and url_or_token.startswith(
        ("keyring:", "keyring://")
    )


def get_password(url_or_token: str) -> str:
    if not is_keyring_url(url_or_token):
        raise ValueError("Invalid keyring URL")

    url = urlparse(url_or_token)
    if url.scheme != "keyring":
        raise ValueError("Invalid keyring URL scheme")
    elif url.params or url.query or url.fragment:
        raise ValueError("Invalid keyring URL")

    service_name, user_name = url.netloc, url.path.lstrip("/")
    return keyring.get_password(service_name, user_name)


def try_get_password(url_or_token: str) -> str:
    if is_keyring_url(url_or_token):
        return get_password(url_or_token)
    else:
        return url_or_token
