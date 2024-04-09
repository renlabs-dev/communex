import importlib.util
from typing import Any, Optional, cast

import typer
import uvicorn
from rich.console import Console
from typer import Context

import communex.balance as c_balance
from communex._common import make_client
from communex.cli._common import (make_custom_context,
                                  print_table_from_plain_dict)
from communex.compat.key import classic_load_key
from communex.errors import ChainTransactionError
from communex.misc import get_map_modules
from communex.module.server import ModuleServer
from communex.util import is_ip_valid

module_app = typer.Typer()


# TODO: refactor CLI
# - module address should be a single (arbitrary) parameter
# - key can be infered from name or vice-versa?
@module_app.command()
def register(
    ctx: Context,
    name: str,
    ip: str,
    port: int,
    key: str,
    netuid: Optional[int] = None,
    stake: Optional[float] = None,
    new_subnet_name: Optional[str] = None,
):
    """
    Registers a module.

    Asks to generate a key if not provided.
    """

    context = make_custom_context(ctx)
    client = make_client()

    match (netuid, new_subnet_name):
        case (None, None):
            raise ValueError("`netuid` or `new_subnet_name` must be provided")
        case (netuid, None):
            assert netuid is not None
            subnet_name = client.get_subnet_name(netuid)
        case (None, new_subnet_name):
            subnet_name = new_subnet_name
        case (_, _):
            raise ValueError("`netuid` and `new_subnet_name` cannot be provided at the same time")

    burn = client.get_burn()

    do_burn = typer.confirm(f"{c_balance.from_nano(burn)} $COMAI will be permanently burned. Do you want to continue?")

    if not do_burn:
        print("Not registering")
        raise typer.Abort()

    with context.progress_status(f"Registering Module {name}..."):
        if stake is not None:
            stake_nano = c_balance.to_nano(stake)
        else:
            min_stake = client.get_min_stake(netuid) if netuid is not None else 0
            stake_nano = min_stake + burn

        resolved_key = classic_load_key(key)

        if not is_ip_valid(ip):
            raise ValueError("Invalid ip address")

        address = f"{ip}:{port}"

        response = client.register_module(
            resolved_key, name=name, address=address, subnet=subnet_name, min_stake=stake_nano
        )

        if response.is_success:
            context.info(f"Module {name} registered")
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
        response = client.update_module(resolved_key, name, address, delegation_fee, netuid=netuid)

    if response.is_success:
        console.print(f"Module {key} updated")
    else:
        raise ChainTransactionError(response.error_message)  # type: ignore


@module_app.command()
def serve(
    ctx: typer.Context,
    class_path: str,
    key: str,
    port: int = 8000,
    ip: Optional[str] = None,
    subnets_whitelist: Optional[list[int]] = [0],
    whitelist: Optional[list[str]] = None,
    blacklist: Optional[list[str]] = None,
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
        class_obj(), keypair, whitelist=whitelist, blacklist=blacklist, subnets_whitelist=subnets_whitelist
    )
    app = server.get_fastapi_app()
    host = ip or "127.0.0.1"
    uvicorn.run(app, host=host, port=port)  # type: ignore


@module_app.command()
def info(name: str, balance: bool = False, netuid: int = 0):
    """
    Gets module info
    """

    console = Console()
    client = make_client()

    with console.status(f"Getting Module {name} on a subnet with netuid '{netuid}' ..."):
        modules = get_map_modules(client, netuid=netuid, include_balances=balance)
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
        modules = get_map_modules(client, netuid=netuid, include_balances=balances)
        modules_to_list = [value for _, value in modules.items()]

    for index, item in enumerate(modules_to_list, start=1):
        console.print(f"module {index}:", style="bold underline")
        for key, value in item.items():
            console.print(f"{key}: {value}")
        console.print("-" * 40)
