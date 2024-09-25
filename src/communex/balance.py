from typing import Any, TypeVar

DECIMALS = 9
UNIT_NAME = "COMAI"


def from_nano(amount: int) -> float:
    """
    Converts from nano to j
    """

    return amount / (10**DECIMALS)


def to_nano(amount: float) -> int:
    """
    Converts from j to nano
    """

    return int(amount * (10**DECIMALS))


def from_horus(amount: int, subnet_tempo: int = 100) -> float:
    """
    Converts from horus to j
    """

    return amount / (10**DECIMALS * subnet_tempo)


def repr_j(amount: int):
    """
    Given an amount in nano, returns a representation of it in tokens/COMAI.

    E.g. "103.2J".
    """

    return f"{from_nano(amount)} {UNIT_NAME}"


T = TypeVar("T")
def dict_from_nano(dict_data: dict[T, Any], fields_to_convert: list[T]):
    """
    Converts specified fields in a dictionary from nano to J. Only works for
    fields that are integers.
    """
    transformed_dict: dict[T, Any] = {}
    for key in dict_data.keys():
        if key in fields_to_convert:
            value = dict_data.get(key)
            if not isinstance(value, int):
                raise ValueError(
                    f"Field {key} is not an integer in the dictionary."
                )
            transformed_dict[key] = repr_j(dict_data[key])
        else:
            transformed_dict[key] = dict_data[key]

    return transformed_dict


