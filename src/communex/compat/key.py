"""
Key storage compatible with the classic `commune` library.

WIP
"""

from typing import Any, cast

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
