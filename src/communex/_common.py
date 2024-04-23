import random
from enum import Enum
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

from communex.balance import from_nano


class ComxSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COMX_")
    # TODO: improve node lists
    NODE_URLS: list[str] = ["wss://commune-api-node-1.communeai.net"]
    TESTNET_NODE_URLS: list[str] = ["wss://testnet-commune-api-node-0.communeai.net"]

      
def get_node_url(comx_settings: ComxSettings | None = None, *, use_testnet: bool = False) -> str:

    comx_settings = comx_settings or ComxSettings()
    match use_testnet:
        case True:
            node_url = random.choice(comx_settings.TESTNET_NODE_URLS)
        case False:
            node_url = random.choice(comx_settings.NODE_URLS)
    return node_url

  
def get_available_nodes(
        comx_settings: ComxSettings | None = None, *, use_testnet: bool = False
    ) -> list[str]:
    comx_settings = comx_settings or ComxSettings()

    match use_testnet:
        case True:
            node_urls = comx_settings.TESTNET_NODE_URLS
        case False:
            node_urls = comx_settings.NODE_URLS
    return node_urls

  
def make_client(node_url: str | None = None):
    """
    Create a client to the Commune network.
    """
    if not node_url:
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
