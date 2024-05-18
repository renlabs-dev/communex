import typer
from typer import Context
from typing import Optional

from communex._common import BalanceUnit, format_balance
from communex.balance import to_nano
from communex.cli._common import (make_custom_context,
                                  print_table_from_plain_dict)
from communex.compat.key import try_classic_load_key, resolve_key_ss58_encrypted
from communex.errors import ChainTransactionError

balance_app = typer.Typer(no_args_is_help=True)


@balance_app.command()
def show(
    ctx: Context, key: str, 
    unit: BalanceUnit = BalanceUnit.joule,
    password: Optional[str] = None
):
    """
    Gets the balances of a key.
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    key_address = resolve_key_ss58_encrypted(key, context, password)

    with context.progress_status(f"Getting balance of key {key_address}..."):
        subnets = client.query_map_subnet_names()
        netuids = list(subnets.keys())
        balance = client.get_balance(key_address)

        stakes: list[int] = []
        for uid in netuids:
            staketo = client.get_staketo(key_addr=key_address, netuid=uid)
            stakes.append(sum(staketo.values()))

        string_stakes = [format_balance(stake, unit) for stake in stakes]
        netuids = [str(uid) for uid in netuids]
        stake_dict = dict(zip(netuids, string_stakes))

        total = balance + sum(stakes)
        free, total = format_balance(
            balance, unit), format_balance(total, unit)

        print_table_from_plain_dict(
            stake_dict, ["Netuid", "Staked"], context.console)
        print_table_from_plain_dict({"Free": free, "Total": total}, [
                                    "Result", "Amount"], context.console)


@balance_app.command()
def free_balance(
    ctx: Context, key: str, 
    unit: BalanceUnit = BalanceUnit.joule,
    password: Optional[str] = None
):
    """
    Gets free balance of a key.
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    key_address = resolve_key_ss58_encrypted(key, context, password)
    
    with context.progress_status(f"Getting free balance of key {key_address}..."):
        balance = client.get_balance(key_address)

    context.output(format_balance(balance, unit))


@balance_app.command()
def staked_balance(
    ctx: Context, key: str, 
    netuid: int = 0, unit: BalanceUnit = BalanceUnit.joule,
    password: Optional[str] = None
):
    """
    Gets the balance staked on the key itself.
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    key_address = resolve_key_ss58_encrypted(key, context, password)

    with context.progress_status(f"Getting staked balance of key {key_address}..."):
        staketo = client.get_staketo(key_addr=key_address, netuid=netuid)

    result = sum(staketo.values())

    context.output(format_balance(result, unit))


@balance_app.command()
def all_balance(
    ctx: Context, key: str, netuid: int = 0, 
    unit: BalanceUnit = BalanceUnit.joule,
    password: Optional[str] = None,
    ):
    """
    Gets entire balance of a key (free balance + staked balance).
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    key_address = resolve_key_ss58_encrypted(key, context, password)

    with context.progress_status(f"Getting value of key {key_address}..."):
        staketo = client.get_staketo(key_address, netuid=netuid)
        stake_sum = sum(staketo.values())
        balance = client.get_balance(key_address)
        result = balance + stake_sum

    context.output(format_balance(result, unit))


@balance_app.command()
def get_staked(
    ctx: Context, key: str, netuid: int = 0, 
    unit: BalanceUnit = BalanceUnit.joule,
    password: Optional[str] = None,
    ):
    """
    Gets total stake of a key it delegated across other keys.
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    key_address = resolve_key_ss58_encrypted(key, context, password)

    with context.progress_status(f"Getting stake of {key_address}..."):
        result = client.get_stake(key=key_address, netuid=netuid)

    context.output(format_balance(result, unit))


@balance_app.command()
def transfer(ctx: Context, key: str, amount: float, dest: str):
    """
    Transfer amount to destination using key
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    nano_amount = to_nano(amount)
    resolved_key = try_classic_load_key(key, context)
    resolved_dest = resolve_key_ss58_encrypted(dest, context)

    if not context.confirm(f"Are you sure you want to transfer {amount} tokens to {dest}?"):
        raise typer.Abort()

    with context.progress_status(f"Transferring {amount} tokens to {dest}..."):
        response = client.transfer(
            key=resolved_key, amount=nano_amount, dest=resolved_dest)

    if response.is_success:
        context.info(f"Transferred {amount} tokens to {dest}")
    else:
        raise ChainTransactionError(response.error_message)  # type: ignore


@balance_app.command()
def transfer_stake(ctx: Context, key: str, amount: float, from_key: str, dest: str, netuid: int = 0):
    """
    Transfers stake of key from point A to point B
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    resolved_from = resolve_key_ss58_encrypted(from_key, context)
    resolved_dest = resolve_key_ss58_encrypted(dest, context)
    resolved_key = try_classic_load_key(key, context)
    nano_amount = to_nano(amount)

    with context.progress_status(
        f"Transferring {amount} tokens from {from_key} to {dest} on a subnet with netuid '{netuid}' ..."
    ):
        response = client.transfer_stake(
            key=resolved_key,
            amount=nano_amount,
            from_module_key=resolved_from,
            dest_module_address=resolved_dest,
            netuid=netuid,
        )

    if response.is_success:
        context.info(f"Transferred {amount} tokens from {from_key} to {dest}")
    else:
        raise ChainTransactionError(response.error_message)  # type: ignore


@balance_app.command()
def stake(
    ctx: Context, key: str, amount: float, 
    dest: str, netuid: int = 0,
    ):
    """
    Stake amount to destination using key
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    nano_amount = to_nano(amount)
    resolved_key = try_classic_load_key(key, context)
    resolved_dest = resolve_key_ss58_encrypted(dest, context)

    with context.progress_status(f"Staking {amount} tokens to {dest} on a subnet with netuid '{netuid}'..."):
        response = client.stake(
            key=resolved_key, amount=nano_amount, dest=resolved_dest, netuid=netuid)

    if response.is_success:
        context.info(f"Staked {amount} tokens to {dest}")
    else:
        raise ChainTransactionError(response.error_message)  # type: ignore


@balance_app.command()
def unstake(ctx: Context, key: str, amount: float, dest: str, netuid: int = 0):
    """
    Unstake amount from destination using key
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    nano_amount = to_nano(amount)
    resolved_key = try_classic_load_key(key, context)
    resolved_dest = resolve_key_ss58_encrypted(dest, context)

    with context.progress_status(f"Unstaking {amount} tokens from {dest} on a subnet with netuid '{netuid}'..."):
        response = client.unstake(
            key=resolved_key, amount=nano_amount, dest=resolved_dest, netuid=netuid) # TODO: is it right?

    if response.is_success:
        context.info(f"Unstaked {amount} tokens from {dest}")
    else:
        raise ChainTransactionError(response.error_message)  # type: ignore
