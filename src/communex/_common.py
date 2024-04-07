import random
from enum import Enum
from typing import Optional

from pydantic_settings import BaseSettings

from communex.balance import from_nano
from communex.client import CommuneClient


class ComxSettings(BaseSettings):
    NODE_URLS: list[str] = ["wss://commune-api-node-1.communeai.net"]
    TESTNET_NODE_URLS: list[str] = ["wss://testnet-commune-api-node-0.communeai.net"]

    class Config:
        env_prefix = "COMX_"


def create_use_testnet_getter():
    use_testnet = False
    def state_function(testnet: Optional[bool]=None):
        nonlocal use_testnet
        if testnet is not None:
            use_testnet = testnet
        return use_testnet

    return state_function

get_use_testnet = create_use_testnet_getter()


def get_node_url(comx_settings: ComxSettings | None = None) -> str:
    comx_settings = comx_settings or ComxSettings()
    match get_use_testnet():
        case True:
            node_url = random.choice(comx_settings.TESTNET_NODE_URLS)
        case False:
            node_url = random.choice(comx_settings.NODE_URLS)
    print(f"Using node: {node_url}")
    return node_url


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
