from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PublishedObject:
    object_id: str
    ciphertext: bytes
    payload_digest: str


@dataclass(frozen=True)
class AccessPackage:
    provider_id: str
    object_id: str
    wrapped_key: str
    locator: str


def _keystream(key: bytes, size: int) -> bytes:
    blocks = []
    counter = 0
    while sum(len(block) for block in blocks) < size:
        blocks.append(hashlib.sha256(key + counter.to_bytes(4, "big")).digest())
        counter += 1
    return b"".join(blocks)[:size]


def _xor(data: bytes, key: bytes) -> bytes:
    stream = _keystream(key, len(data))
    return bytes(a ^ b for a, b in zip(data, stream))


def _wrap_key(content_key: bytes, provider_public_key: str) -> str:
    wrapping_key = hashlib.sha256(provider_public_key.encode()).digest()
    return base64.b64encode(_xor(content_key, wrapping_key)).decode()


def _unwrap_key(wrapped_key: str, provider_public_key: str) -> bytes:
    wrapping_key = hashlib.sha256(provider_public_key.encode()).digest()
    return _xor(base64.b64decode(wrapped_key), wrapping_key)


def publish_payload(payload: bytes, provider_keys: dict[str, str], nonce: Optional[bytes] = None) -> tuple[PublishedObject, list[AccessPackage]]:
    """Publish one ciphertext plus a small encrypted access package per provider.

    This is a toy interface implementation. It uses SHA-256 based XOR wrapping so
    the artifact can run without external key-management dependencies.
    """
    content_key = nonce or os.urandom(32)
    ciphertext = _xor(payload, content_key)
    object_id = hashlib.sha256(ciphertext).hexdigest()
    published = PublishedObject(
        object_id=object_id,
        ciphertext=ciphertext,
        payload_digest=hashlib.sha256(payload).hexdigest(),
    )
    packages = [
        AccessPackage(
            provider_id=provider_id,
            object_id=object_id,
            wrapped_key=_wrap_key(content_key, public_key),
            locator=f"local-object://{object_id}",
        )
        for provider_id, public_key in provider_keys.items()
    ]
    return published, packages


def recover_payload(published: PublishedObject, package: AccessPackage, provider_public_key: str) -> bytes:
    content_key = _unwrap_key(package.wrapped_key, provider_public_key)
    payload = _xor(published.ciphertext, content_key)
    if hashlib.sha256(payload).hexdigest() != published.payload_digest:
        raise ValueError("payload digest mismatch")
    return payload
