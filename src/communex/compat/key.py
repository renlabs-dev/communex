"""
Key storage compatible with the classic `commune` library.

WIP
"""

from pathlib import Path
from typing import Any, cast

from substrateinterface import Keypair  # type: ignore

from cexpl.types import CommuneKeyDict
from communex.key import is_ss58_address


def check_key_dict(key_dict: Any) -> CommuneKeyDict:
    """
    Validates a given dictionary as a commune key dictionary and returns it.

    This function checks if the provided dictionary adheres to the structure of
    a CommuneKeyDict, that is used by the classic `commune` library and returns
    it if valid.

    Args:
        key_dict: The dictionary to validate.

    Returns:
        The validated commune key dictionary. Same as input.

    Raises:
      AssertionError: If the dictionary does not conform to the expected
        structure.
    """

    assert isinstance(key_dict, dict)
    assert isinstance(key_dict["crypto_type"], int)
    assert isinstance(key_dict["seed_hex"], str)
    assert isinstance(key_dict["derive_path"], str | None)
    assert isinstance(key_dict["path"], str)
    assert isinstance(key_dict["public_key"], str)
    assert isinstance(key_dict["ss58_format"], int)
    assert isinstance(key_dict["ss58_address"], str)
    assert is_ss58_address(key_dict["ss58_address"])
    assert isinstance(key_dict["private_key"], str)
    assert isinstance(key_dict["mnemonic"], str)
    return cast(CommuneKeyDict, key_dict)


def classic_key_path(name: str) -> str:
    """
    Constructs the file path for a key in the classic commune format.

    Args:
        name: The name of the key.

    Returns:
        The file path for the key.
    """

    home = Path.home()
    root_path = home / '.commune' / "key"
    name = name + ".json"
    return str(root_path / name)


def classic_store_key(keypair: Keypair, name: str) -> None:
    """
    Stores the given keypair on a disk under the given name.
    """
    raise NotImplementedError()


def classic_load_key(name: str) -> Keypair:
    """
    Loads the keypair with the given name from a disk.
    """
    raise NotImplementedError()
