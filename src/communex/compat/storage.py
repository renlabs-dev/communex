"""
Data storage compatible with the *classic* `commune` library.
"""

# TODO: encryption

import json
import os.path
import time
from typing import Any
import base64

from nacl.secret import SecretBox
from nacl.utils import random
import hashlib

# from cryptography.fernet import Fernet
# from cryptography.hazmat.primitives import hashes
# from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from communex.util import ensure_parent_dir_exists

COMMUNE_HOME = "~/.commune"
"""
COMMUNE_HOME

    classic commune data storage home directory.
"""


def _derive_key(password: str):
    # Derive a 256-bit key from the password using Blake2b
    key = hashlib.blake2b(password.encode(), digest_size=32).digest()
    return key


def _encrypt_data(password: str, data: Any) -> str:
    key = _derive_key(password)
    box = SecretBox(key)
    nonce = random(SecretBox.NONCE_SIZE)
    raw = json.dumps(data).encode()
    ciphertext = box.encrypt(raw, nonce).ciphertext
    encrypted = nonce + ciphertext
    decoded_data = base64.b64encode(encrypted).decode()
    return decoded_data

def _decrypt_data(password: str, data: str) -> Any:
    key = _derive_key(password)
    box = SecretBox(key)
    encrypted = base64.b64decode(data.encode())
    nonce = encrypted[:SecretBox.NONCE_SIZE]
    ciphertext = encrypted[SecretBox.NONCE_SIZE:]
    raw = box.decrypt(ciphertext, nonce)
    return json.loads(raw.decode())


def classic_load(path: str, mode: str = "json", password: str | None = None) -> Any:
    """
    Load data from commune data storage.

    Args:
        path: Data storage file path.
        mode: Data storage mode.

    Returns:
        Data loaded from the data storage.

    Todo:
        * Other serialization modes support. Only json mode is supported now.

    Raises:
        NotImplementedError: See Todo.
        AssertionError: Raised when the data is not in the classic format.
    """
    if mode != "json":
        raise NotImplementedError("Our commune data storage only supports json mode")

    full_path = os.path.expanduser(os.path.join(COMMUNE_HOME, path))
    with open(full_path, "r") as file:
        body = json.load(file)
        if body["encrypted"] and password is None:
            raise json.JSONDecodeError("Data is encrypted but no password provided", "", 0)
        if body["encrypted"] and password is not None:
            content = _decrypt_data(password, body["data"])
        else:
            content = body["data"]
    assert isinstance(body, dict)
    assert isinstance(body["timestamp"], int)
    assert isinstance(content, (dict, list, tuple, set, float, str, int))
    return content  # type: ignore


def classic_put(
        path: str, value: Any, mode: str = "json", password: str | None = None
    ):
    """
    Put data into commune data storage.

    Args:
        path: Data storage path.
        value: Data to store.
        mode: Data storage mode.
        encrypt: Whether to encrypt the data.

    Todo:
        * Encryption support.
        * Other serialization modes support. Only json mode is supported now.

    Raises:
        NotImplementedError: See Todo.
        TypeError: Raised when value is not a valid type.
        FileExistsError: Raised when the file already exists.
    """
    if mode != "json":
        raise NotImplementedError("Our commune data storage only supports json mode")
    if not isinstance(value, (dict, list, tuple, set, float, str, int)):
        raise TypeError(f"Invalid type for commune data storage value: {type(value)}")
    timestamp = int(time.time())

    full_path = os.path.expanduser(os.path.join(COMMUNE_HOME, path))

    if os.path.exists(full_path):
        raise FileExistsError(f"Commune data storage file already exists: {full_path}")
    
    ensure_parent_dir_exists(full_path)
    
    if password:
        value = _encrypt_data(password, value)
        encrypt = True
    else:
        encrypt = False



    with open(full_path, "w") as file:
        json.dump({'data': value, 'encrypted': encrypt, 'timestamp': timestamp},
                  file, indent=4)

