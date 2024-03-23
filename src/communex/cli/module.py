import importlib.util
from typing import Any, Optional, cast

import typer
import uvicorn
from rich.console import Console

import communex.balance as c_balance
from communex.compat.key import classic_load_key, classic_store_key
from communex.errors import ChainTransactionError
from communex.key import generate_keypair
from communex.misc import get_map_modules
from communex.module.server import ModuleServer
from communex.util import is_ip_valid

from ._common import (make_client, make_custom_context,
                      print_table_from_plain_dict)

module_app = typer.Typer()


@module_app.command()
def register(
    name: str, ip: str, port: int, key: Optional[str] = None, 
    subnet: str = "commune", stake: Optional[float] = None, netuid: int = 0
    ):
    """
    Registers a module.

    Asks to generate a key if not provided.
    """

    console = Console()
    client = make_client()

    if stake is None:
        stake = client.get_min_stake(netuid)

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
def serve(
    ctx: typer.Context,
    class_path: str,
    port: int,
    key: str,
    subnets: list[int],
    ip: Optional[str]=None, whitelist: Optional[list[str]]=None, 
    blacklist: Optional[list[str]]=None,
    ):
    """
    Serves a module on `127.0.0.1` on port `port`. `class_path` should specify
    the dotted path to the module class e.g. `module.submodule.ClassName`.
    """

    context = make_custom_context(ctx)

    path_parts = class_path.split(".")
    match path_parts:
        case [*module_parts, class_name]: 
            module_path = ".".join(module_parts)
            if not module_path:
                # This could do some kind of relative import somehow?
                raise ValueError(f"Invalid class path: `{class_path}`, module name is missing")
            if not class_name:
                raise ValueError(f"Invalid class path: `{class_path}`, class name is missing")
        case _:
            # This is impossible
            raise Exception(f"Invalid class path: `{class_path}`")

    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError:
        context.error(f"Module `{module_path}` not found")
        raise typer.Exit(code=1)

    try:
        class_obj = getattr(module, class_name)
    except AttributeError:
        context.error(f"Class `{class_name}` not found in module `{module}`")
        raise typer.Exit(code=1)

    keypair = classic_load_key(key)
    server = ModuleServer(
        class_obj(), keypair, 
        whitelist=whitelist, blacklist=blacklist, subnets=subnets
        )
    app = server.get_fastapi_app()
    host = ip or "127.0.0.1"
    uvicorn.run(app, host=host, port=port) #type: ignore


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
