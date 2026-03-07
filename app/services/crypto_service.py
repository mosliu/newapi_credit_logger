import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import get_settings


def _build_fernet() -> Fernet:
    secret = get_settings().api_key_encrypt_secret.encode("utf-8")
    digest = hashlib.sha256(secret).digest()
    fernet_key = base64.urlsafe_b64encode(digest)
    return Fernet(fernet_key)


def encrypt_api_key(raw_api_key: str) -> str:
    return _build_fernet().encrypt(raw_api_key.encode("utf-8")).decode("utf-8")


def decrypt_api_key(encrypted_api_key: str) -> str:
    return _build_fernet().decrypt(encrypted_api_key.encode("utf-8")).decode("utf-8")


def mask_api_key(raw_api_key: str) -> str:
    if len(raw_api_key) <= 8:
        return "*" * len(raw_api_key)
    return f"{raw_api_key[:4]}{'*' * (len(raw_api_key) - 8)}{raw_api_key[-4:]}"
