"""
Ed25519 Key Management for Orbitron Contact Tokens
"""

import hashlib
import os
from pathlib import Path
from typing import Tuple, Union

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization
from security.exceptions import SecurityConfigurationError


def generate_keypair() -> Tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    """Generate a fresh Ed25519 private/public keypair."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key


def private_key_to_pem(private_key: Ed25519PrivateKey) -> bytes:
    """Serialize an Ed25519 private key to PKCS#8 PEM bytes."""
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def public_key_to_pem(public_key: Ed25519PublicKey) -> bytes:
    """Serialize an Ed25519 public key to SubjectPublicKeyInfo PEM bytes."""
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def load_private_key_pem(data: Union[bytes, str, Ed25519PrivateKey]) -> Ed25519PrivateKey:
    """Load an Ed25519 private key from PEM bytes or string."""
    if isinstance(data, Ed25519PrivateKey):
        return data
    if isinstance(data, str):
        data = data.encode("utf-8")
    try:
        key = serialization.load_pem_private_key(data, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise SecurityConfigurationError("Loaded key is not an Ed25519 private key")
        return key
    except Exception as e:
        raise SecurityConfigurationError(f"Failed to load Ed25519 private key: {e}") from None


def load_public_key_pem(data: Union[bytes, str, Ed25519PublicKey]) -> Ed25519PublicKey:
    """Load an Ed25519 public key from PEM bytes or string."""
    if isinstance(data, Ed25519PublicKey):
        return data
    if isinstance(data, str):
        data = data.encode("utf-8")
    try:
        key = serialization.load_pem_public_key(data)
        if not isinstance(key, Ed25519PublicKey):
            raise SecurityConfigurationError("Loaded key is not an Ed25519 public key")
        return key
    except Exception as e:
        raise SecurityConfigurationError(f"Failed to load Ed25519 public key: {e}") from None


def derive_public_key_fingerprint(public_key: Union[bytes, str, Ed25519PublicKey]) -> str:
    """Derive deterministic SHA-256 fingerprint for key identification (kid)."""
    if isinstance(public_key, Ed25519PublicKey):
        pem_bytes = public_key_to_pem(public_key)
    elif isinstance(public_key, str):
        pem_bytes = public_key.encode("utf-8")
    else:
        pem_bytes = public_key
    # Normalize by loading and re-encoding standard SubjectPublicKeyInfo PEM
    try:
        pub = load_public_key_pem(pem_bytes)
        canonical_pem = public_key_to_pem(pub)
        return hashlib.sha256(canonical_pem).hexdigest()[:16]
    except Exception:
        return hashlib.sha256(pem_bytes).hexdigest()[:16]


def init_issuer_keys(output_dir: Union[str, Path], overwrite: bool = False) -> Tuple[Path, Path]:
    """
    Initialize issuer Ed25519 keypair and write private.pem and public.pem.
    Sets restrictive file permissions where supported.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    priv_file = out_path / "private.pem"
    pub_file = out_path / "public.pem"

    if (priv_file.exists() or pub_file.exists()) and not overwrite:
        raise FileExistsError(f"Key files already exist in {out_path}. Use overwrite=True to replace.")

    private_key, public_key = generate_keypair()
    priv_pem = private_key_to_pem(private_key)
    pub_pem = public_key_to_pem(public_key)

    priv_file.write_bytes(priv_pem)
    pub_file.write_bytes(pub_pem)

    # Apply restrictive permissions on POSIX
    try:
        os.chmod(priv_file, 0o600)
        os.chmod(pub_file, 0o644)
    except OSError:
        pass

    return priv_file, pub_file
