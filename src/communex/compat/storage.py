"""
Data storage compatible with the `commune` library.
"""

# TODO: encryption

import json
import os.path
import time
from typing import Any

from cexpl.util import ensure_parent_dir_exists

COMMUNE_HOME = "~/.commune"


def classic_load(path: str, mode: str = "json") -> Any:
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
