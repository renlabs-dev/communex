import random
from enum import Enum

from pydantic_settings import BaseSettings

from communex.balance import from_nano


class ComxSettings(BaseSettings):
    # TODO: improve node lists
    NODE_URLS: list[str] = ["wss://commune-api-node-1.communeai.net"]
    TESTNET_NODE_URLS: list[str] = ["wss://testnet-commune-api-node-0.communeai.net"]

    class Config:
        env_prefix = "COMX_"


def get_node_url(comx_settings: ComxSettings | None = None, *, use_testnet: bool = False) -> str:
    comx_settings = comx_settings or ComxSettings()
    match use_testnet:
        case True:
            node_url = random.choice(comx_settings.TESTNET_NODE_URLS)
        case False:
            node_url = random.choice(comx_settings.NODE_URLS)
    return node_url


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
