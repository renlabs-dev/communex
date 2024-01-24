"""
Data storage compatible with the *classic* `commune` library.
"""

# TODO: encryption

import json
import os.path
import time
from typing import Any

from communex.util import ensure_parent_dir_exists

COMMUNE_HOME = "~/.commune"
"""
COMMUNE_HOME

    classic commune data storage home directory.
"""


def classic_load(path: str, mode: str = "json") -> Any:
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

    assert isinstance(body, dict)
    assert not body["encrypted"]
    assert isinstance(body["timestamp"], int)
    assert isinstance(body["data"], (dict, list, tuple, set, float, str, int))
    return body["data"]  # type: ignore


def classic_put(path: str, value: Any, mode: str = "json", encrypt: bool = False):
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
    if encrypt:
        raise NotImplementedError("Commune data storage encryption not implemented")

    if not isinstance(value, (dict, list, tuple, set, float, str, int)):
        raise TypeError(f"Invalid type for commune data storage value: {type(value)}")

    timestamp = int(time.time())

    full_path = os.path.expanduser(os.path.join(COMMUNE_HOME, path))

    if os.path.exists(full_path):
        raise FileExistsError(f"Commune data storage file already exists: {full_path}")

    ensure_parent_dir_exists(full_path)

    with open(full_path, "w") as file:
        json.dump({'data': value, 'encrypted': encrypt, 'timestamp': timestamp},
                  file, indent=4)
