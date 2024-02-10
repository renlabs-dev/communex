from typing import Any, Optional, cast

import typer
from rich.console import Console

import communex.balance as c_balance
from communex.compat.key import classic_load_key, classic_store_key
from communex.errors import ChainTransactionError
from communex.key import generate_keypair
from communex.misc import get_map_modules
from communex.util import is_ip_valid

from ._common import make_client, print_table_from_plain_dict

module_app = typer.Typer()


@module_app.command()
def register(name: str, ip: str, port: int, key: Optional[str] = None, subnet: str = "commune", stake: float = 100):
    """
    Registers a module.

    Asks to generate a key if not provided.
    """

    console = Console()
    client = make_client()

    stake_nano = c_balance.to_nano(stake)

    if key is not None:
        resolved_key = classic_load_key(key)
    else:
        console.print("Do you want to generate a key for the module? (y/n)")

        answer = input()
        if answer == "y":  # TODO: refactor prompt
            keypair = generate_keypair()
            classic_store_key(keypair, name)
        else:
            console.print("You need to provide or generate a key.")
            exit(1)

        resolved_key = classic_load_key(name)
        console.print(
            f"Created key {name} with address {resolved_key.ss58_address}", style="bold green")

    if not is_ip_valid(ip):
        raise ValueError("Invalid ip address")

    address = f"{ip}:{port}"

    with console.status(f"Registering Module on a subnet '{subnet}' ..."):
        response = (client.register_module(resolved_key, name=name,
                                           address=address, subnet=subnet, min_stake=stake_nano))

    if response.is_success:
        console.print(f"Module {name} registered")
    else:
        raise ChainTransactionError(response.error_message)  # type: ignore


@module_app.command()
def update(key: str, name: str, ip: str, port: int, delegation_fee: int = 20, netuid: int = 0):
    """
    Update module with custom parameters.
    """

    console = Console()
    resolved_key = classic_load_key(key)
    client = make_client()

    if not is_ip_valid(ip):
        raise ValueError("Invalid ip address")

    address = f"{ip}:{port}"

    with console.status(f"Updating Module on a subnet with netuid '{netuid}' ..."):
        response = (client.update_module(resolved_key, name,
                                         address, delegation_fee, netuid=netuid))

    if response.is_success:
        console.print(f"Module {key} updated")
    else:
        raise ChainTransactionError(response.error_message)  # type: ignore


@module_app.command()
def serve(name: str, type: str, key: str):
    # TODO implement
    # -[x] make better serve and register module UI
    pass


@module_app.command()
def info(name: str, balance: bool = False, netuid: int = 0):
    """
    Gets module info
    """

    console = Console()
    client = make_client()

    with console.status(f"Getting Module {name} on a subnet with netuid '{netuid}' ..."):
        modules = (get_map_modules(client, netuid=netuid, include_balances=balance))
        modules_to_list = [value for _, value in modules.items()]

        module = next((item for item in modules_to_list if item["name"] == name), None)

    if module is None:
        raise ValueError("Module not found")

    general_module = cast(dict[str, Any], module)
    print_table_from_plain_dict(general_module, ["Params", "Values"], console)


@module_app.command(name="list")
def inventory(balances: bool = False, netuid: int = 0):
    """
    Modules stats on the network.
    """

    console = Console()
    client = make_client()

    with console.status(f"Getting Modules on a subnet with netuid '{netuid}' ..."):
        modules = (get_map_modules(client, netuid=netuid, include_balances=balances))
        modules_to_list = [value for _, value in modules.items()]

    for index, item in enumerate(modules_to_list, start=1):
        console.print(f"module {index}:", style="bold underline")
        for key, value in item.items():
            console.print(f"{key}: {value}")
        console.print("-" * 40)
