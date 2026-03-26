#!/usr/bin/env python3
"""
config_manager.py — Encrypt, decrypt, and edit the qudurat-jail YAML config.

Usage:
  python src/config_manager.py encrypt <config.yaml>
      Reads a plaintext YAML, prompts for a password, writes <config.yaml>.enc

  python src/config_manager.py decrypt <config.yaml.enc>
      Prompts for password, prints decrypted YAML to stdout

  python src/config_manager.py edit <config.yaml.enc>
      Decrypts to a temp file, opens $EDITOR, re-encrypts on save
"""

import sys
import os
import getpass
import tempfile
import subprocess
import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


SALT_SIZE = 16
PBKDF2_ITERATIONS = 480_000


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def encrypt_data(plaintext: bytes, password: str) -> bytes:
    salt = os.urandom(SALT_SIZE)
    key = _derive_key(password, salt)
    f = Fernet(key)
    return salt + f.encrypt(plaintext)


def decrypt_data(ciphertext: bytes, password: str) -> bytes:
    salt = ciphertext[:SALT_SIZE]
    token = ciphertext[SALT_SIZE:]
    key = _derive_key(password, salt)
    f = Fernet(key)
    return f.decrypt(token)


def load_secret_file(path: str = "/etc/qudurat-jail/secret") -> str:
    """Read password from secret file (used by systemd service)."""
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("QUDURAT_PASSWORD="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise ValueError(f"QUDURAT_PASSWORD not found in {path}")


def cmd_encrypt(src_yaml: str) -> None:
    with open(src_yaml, "rb") as fh:
        plaintext = fh.read()

    password = getpass.getpass("Enter encryption password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        sys.exit("Passwords do not match.")

    out_path = src_yaml if src_yaml.endswith(".enc") else src_yaml + ".enc"
    # Strip .yaml.enc → keep meaningful name
    if src_yaml.endswith(".yaml"):
        out_path = src_yaml[:-5] + ".yaml.enc"

    ciphertext = encrypt_data(plaintext, password)
    with open(out_path, "wb") as fh:
        fh.write(ciphertext)

    print(f"Encrypted → {out_path}")


def cmd_decrypt(enc_path: str) -> None:
    with open(enc_path, "rb") as fh:
        ciphertext = fh.read()

    password = getpass.getpass("Enter decryption password: ")
    plaintext = decrypt_data(ciphertext, password)
    sys.stdout.buffer.write(plaintext)


def cmd_edit(enc_path: str) -> None:
    with open(enc_path, "rb") as fh:
        ciphertext = fh.read()

    password = getpass.getpass("Enter decryption password: ")
    plaintext = decrypt_data(ciphertext, password)

    editor = os.environ.get("EDITOR", "nano")
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as tmp:
        tmp.write(plaintext)
        tmp_path = tmp.name

    try:
        subprocess.run([editor, tmp_path], check=True)
        with open(tmp_path, "rb") as fh:
            new_plaintext = fh.read()
    finally:
        os.unlink(tmp_path)

    new_ciphertext = encrypt_data(new_plaintext, password)
    with open(enc_path, "wb") as fh:
        fh.write(new_ciphertext)

    print(f"Re-encrypted → {enc_path}")


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    command, path = sys.argv[1], sys.argv[2]

    if command == "encrypt":
        cmd_encrypt(path)
    elif command == "decrypt":
        cmd_decrypt(path)
    elif command == "edit":
        cmd_edit(path)
    else:
        sys.exit(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
