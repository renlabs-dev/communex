from enum import Enum
from communex.balance import from_nano
from communex.client import CommuneClient


def get_node_url() -> str:
    return "wss://commune-api-node-1.communeai.net"


def make_client():
    """
    Create a client to the Commune network.
    """

    node_url = get_node_url()
    return CommuneClient(url=node_url, num_connections=1, wait_for_finalization=False)


class BalanceUnit(str, Enum):
    joule = "joule"
    j = "j"
    nano = "nano"
    n = "n"


def format_balance(balance: int, unit: BalanceUnit = BalanceUnit.nano) -> str:
    """
    Formats a balance.
    """

    match unit:
        case BalanceUnit.nano | BalanceUnit.n:
            return f"{balance}"
        case BalanceUnit.joule | BalanceUnit.j:
            in_joules = from_nano(balance)
            round_joules = round(in_joules, 4)
            return f"{round_joules:,} J"
