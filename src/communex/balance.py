DECIMALS = 9
HORUS_DECIMALS = 11


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


def from_horus(amount: int) -> float:
    """
    Converts from horus to j
    """

    return amount / (10**HORUS_DECIMALS)


def repr_j(amount: int):
    """
    Given an amount in nano, returns a representation of it in tokens/J.

    E.g. "103.2J".
    """

    return f"{from_nano(amount)}J"
