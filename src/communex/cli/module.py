import importlib.util
from typing import Any, Optional, cast

import typer
import uvicorn
from typer import Context

import communex.balance as c_balance
from communex.cli._common import make_custom_context, print_module_info, print_table_from_plain_dict
from communex.compat.key import classic_load_key
from communex.errors import ChainTransactionError
from communex.misc import get_map_modules
from communex.module.server import ModuleServer
from communex.module._rate_limiters.limiters import IpLimiterParams, StakeLimiterParams
from communex.util import is_ip_valid
from communex._common import intersection_update

module_app = typer.Typer(no_args_is_help=True)


# TODO: refactor module register CLI
# - module address should be a single (arbitrary) parameter
# - key can be infered from name or vice-versa?
@module_app.command()
def register(
    ctx: Context,
    name: str,
    key: str,
    ip: Optional[str] = None,
    port: Optional[int] = None,
    netuid: Optional[int] = None,
    stake: Optional[float] = None,
    metadata: Optional[str] = None,
    new_subnet_name: Optional[str] = None,
):
    """
    Registers a module on the Commune network.
    """
    context = make_custom_context(ctx)
    client = context.com_client()
    if metadata and len(metadata) > 59:
        raise ValueError("Metadata must be less than 60 characters")

    match (netuid, new_subnet_name):
        case (None, None):
            raise ValueError(
                "`--netuid` or `--new_subnet_name` argument must be passed into the CLI command \n"
                "f.e comx module register <name> <ip> <port> <key> --netuid <netuid>"
            )
        case (netuid, None):
            assert netuid is not None
            subnet_name = client.get_subnet_name(netuid)
            burn = client.get_burn(netuid)
        case (None, new_subnet_name):
            subnet_name = new_subnet_name
            burn = client.get_min_burn()
        case (_, _):
            raise ValueError(
                "`--netuid` and `--new_subnet_name` cannot be provided at the same time"
            )

    do_burn = context.confirm(
        f"{c_balance.from_nano(burn)} $COMAI will be permanently burned. Do you want to continue?"
    )

    if not do_burn:
        print("Not registering")
        raise typer.Abort()

    with context.progress_status(f"Registering Module {name}..."):
        if stake is not None:
            stake_nano = c_balance.to_nano(stake)
        else:
            min_stake = client.get_min_stake(netuid) if netuid is not None else 0
            stake_nano = (
                min_stake + burn + c_balance.to_nano(0.1)
            )  # 0.1 extra needed for the call to succeed

        resolved_key = classic_load_key(key)

        address = f"{ip}:{port}"

        response = client.register_module(
            resolved_key,
            name=name,
            address=address,
            subnet=subnet_name,
            min_stake=stake_nano,
            metadata=metadata,
        )

        if response.is_success:
            context.info(f"Module {name} registered")
        else:
            raise ChainTransactionError(response.error_message)  # type: ignore


@module_app.command()
def update(
    ctx: Context,
    key: str,
    name: Optional[str] = None,
    ip: Optional[str] = None,
    port: Optional[int] = None,
    delegation_fee: int = 20,
    netuid: int = 0,
    metadata: Optional[str] = None,
):
    """
    Update module with custom parameters.
    """

    context = make_custom_context(ctx)
    client = context.com_client()
    if metadata and len(metadata) > 59:
        raise ValueError("Metadata must be less than 60 characters")
    resolved_key = classic_load_key(key)

    if ip and not is_ip_valid(ip):
        raise ValueError("Invalid ip address")
    modules = get_map_modules(client, netuid=netuid, include_balances=False)
    modules_to_list = [value for _, value in modules.items()]

    module = next(
        (
            item for item in modules_to_list if item["key"] == resolved_key.ss58_address
        ), 
            None
    )

    if module is None:
        raise ValueError(f"Module {name} not found")
    module_params = {
        "name": name,
        "ip": ip,
        "port": port,
        "delegation_fee": delegation_fee,
        "metadata": metadata,
    }
    to_update = {
        key: value for key, value in module_params.items() if value is not None
    }
    current_ip, current_port = module["address"].split(":")
    new_ip = to_update.get("ip", current_ip)
    new_port = to_update.get("port", current_port)
    address = f"{new_ip}:{new_port}"
    to_update["address"] = address
    updated_module = intersection_update(dict(module), to_update)
    module.update(updated_module) # type: ignore
    with context.progress_status(
        f"Updating Module on a subnet with netuid '{netuid}' ..."
    ):
        response = client.update_module(
            key=resolved_key,
            name=module["name"],
            address=module["address"],
            delegation_fee=module["delegation_fee"],
            netuid=netuid,
            metadata=module["metadata"],
        )

    if response.is_success:
        context.info(f"Module {key} updated")
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
    ip_blacklist: Optional[list[str]] = None,
    test_mode: Optional[bool] = False,
    request_staleness: int = typer.Option(120),
    use_ip_limiter: Optional[bool] = typer.Option(
        False, help=("If this value is passed, the ip limiter will be used")
    ),
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
                raise ValueError(
                    f"Invalid class path: `{class_path}`, module name is missing"
                )
            if not class_name:
                raise ValueError(
                    f"Invalid class path: `{class_path}`, class name is missing"
                )
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
    if test_mode:
        subnets_whitelist = None
    limiter_params = IpLimiterParams() if use_ip_limiter else StakeLimiterParams()
    server = ModuleServer(
        class_obj(), keypair, 
        whitelist=whitelist, blacklist=blacklist, 
        subnets_whitelist=subnets_whitelist, 
        max_request_staleness=request_staleness,
        limiter=limiter_params,
        ip_blacklist=ip_blacklist,
        
    )
    app = server.get_fastapi_app()
    host = ip or "127.0.0.1"
    uvicorn.run(app, host=host, port=port)  # type: ignore


@module_app.command()
def info(ctx: Context, name: str, balance: bool = False, netuid: int = 0):
    """
    Gets module info
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    with context.progress_status(
        f"Getting Module {name} on a subnet with netuid {netuid}…"
    ):
        modules = get_map_modules(client, netuid=netuid, include_balances=balance)
        modules_to_list = [value for _, value in modules.items()]

        module = next((item for item in modules_to_list if item["name"] == name), None)

    if module is None:
        raise ValueError("Module not found")

    general_module = cast(dict[str, Any], module)
    print_table_from_plain_dict(general_module, ["Params", "Values"], context.console)


@module_app.command(name="list")
def inventory(ctx: Context, balances: bool = False, netuid: int = 0):
    """
    Modules stats on the network.
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    # with context.progress_status(
    #     f"Getting Modules on a subnet with netuid {netuid}..."
    # ):
    modules = cast(dict[str, Any], get_map_modules(
        client, netuid=netuid, include_balances=balances))

    # Convert the values to a human readable format
    modules_to_list = [value for _, value in modules.items()]

    miners: list[Any] = []
    validators: list[Any] = []
    inactive: list[Any] = []

    for module in modules_to_list:
        if module["incentive"] == module["dividends"] == 0:
            inactive.append(module)
        elif module["incentive"] > module["dividends"]:
            miners.append(module)
        else:
            validators.append(module)

    print_module_info(client, miners, context.console, netuid, "miners")
    print_module_info(client, validators, context.console, netuid, "validators")
    print_module_info(client, inactive, context.console, netuid, "inactive")
