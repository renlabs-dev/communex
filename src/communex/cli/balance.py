import typer
from rich.console import Console

from communex.balance import to_nano
from communex.compat.key import resolve_key_ss58, classic_load_key
from communex.errors import ChainTransactionError

from ._common import BalanceUnit, format_balance, make_client, print_table_from_plain_dict

balance_app = typer.Typer()


@balance_app.command()
def show(key: str, unit: BalanceUnit = BalanceUnit.joule):
    """
    Gets the balances of a key.
    """

    console = Console()
    client = make_client()

    key_address = resolve_key_ss58(key)  # TODO: commune.compat.key.classic_resolve_key_ss58

    with console.status(f"Getting balance of key {key_address}..."):
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
        free, total = format_balance(balance, unit), format_balance(total, unit)

        print_table_from_plain_dict(stake_dict, ["Netuid", "Staked"], console)
        print_table_from_plain_dict({"Free": free, "Total": total}, ["Result", "Amount"], console)


@balance_app.command()
def free_balance(key: str, unit: BalanceUnit = BalanceUnit.joule):
    """
    Gets free balance of a key.
    """

    console = Console()
    client = make_client()

    key_address = resolve_key_ss58(key)

    with console.status(f"Getting free balance of key {key_address}..."):
        balance = client.get_balance(key_address)

    console.print(format_balance(balance, unit))


@balance_app.command()
def staked_balance(key: str, netuid: int = 0, unit: BalanceUnit = BalanceUnit.joule):
    """
    Gets staked balance of key.
    """

    console = Console()
    client = make_client()

    key_address = resolve_key_ss58(key)

    with console.status(f"Getting staked balance of key {key_address}..."):
        staketo = client.get_staketo(key_addr=key_address, netuid=netuid)

    result = sum(staketo.values())

    console.print(format_balance(result, unit))


@balance_app.command()
def all_balance(key: str, netuid: int = 0, unit: BalanceUnit = BalanceUnit.joule):
    """
    Gets entire balance of a key (free balance + staked balance).
    """

    console = Console()
    client = make_client()

    key_address = resolve_key_ss58(key)

    with console.status(f"Getting value of key {key_address}..."):
        staketo = client.get_staketo(key_address, netuid=netuid)
        stake_sum = sum(staketo.values())
        balance = client.get_balance(key_address)
        result = balance + stake_sum

    console.print(format_balance(result, unit))


@balance_app.command()
def get_staked(key: str, netuid: int = 0, unit: BalanceUnit = BalanceUnit.joule):
    """
    Gets total stake of a key.
    """

    console = Console()
    client = make_client()

    key_address = resolve_key_ss58(key)

    with console.status(f"Getting stake of {key_address}..."):
        result = client.get_stake(key=key_address, netuid=netuid)

    console.print(format_balance(result, unit))


# TODO, add all flag
@balance_app.command()
def transfer(key: str, amount: float, dest: str):
    """
    Transfer amount to destination using key
    """

    console = Console()
    client = make_client()

    nano_amount = to_nano(amount)
    resolved_key = classic_load_key(key)
    resolved_dest = resolve_key_ss58(dest)

    transfer = typer.confirm(f"Are you sure you want to transfer {amount} tokens to {dest}?")
    if not transfer:
        print("Not transfering")
        raise typer.Abort()

    with console.status(f"Transferring {amount} tokens to {dest}..."):
        response = client.transfer(key=resolved_key,
                                    amount=nano_amount, dest=resolved_dest)

    if response.is_success:
        console.print(f"Transferred {amount} tokens to {dest}")
    else:
        raise ChainTransactionError(response.error_message)  # type: ignore


@balance_app.command()
def transfer_stake(key: str, amount: float, from_key: str, dest: str, netuid: int = 0):
    """
    Transfers stake of key from point A to point B
    """

    console = Console()
    client = make_client()

    resolved_from = resolve_key_ss58(from_key)
    resolved_dest = resolve_key_ss58(dest)
    resolved_key = classic_load_key(key)
    nano_amount = to_nano(amount)

    with console.status(f"Transferring {amount} tokens from {from_key} to {dest} on a subnet with netuid '{netuid}' ..."):
        response = client.transfer_stake(
            key=resolved_key,
            amount=nano_amount,
            from_module_key=resolved_from,
            dest_module_address=resolved_dest,
            netuid=netuid,
        )

    if response.is_success:
        console.print(
            f"Transferred {amount} tokens from {from_key} to {dest}")
    else:
        raise ChainTransactionError(response.error_message)  # type: ignore


@balance_app.command()
def stake(key: str, amount: float, dest: str, netuid: int = 0):
    """
    Stake amount to destination using key
    """

    console = Console()
    client = make_client()

    nano_amount = to_nano(amount)
    resolved_key = classic_load_key(key)
    resolved_dest = resolve_key_ss58(dest)

    with console.status(f"Staking {amount} tokens to {dest} on a subnet with netuid '{netuid}'..."):

        response = client.stake(key=resolved_key, amount=nano_amount,
                                dest=resolved_dest, netuid=netuid)

    if response.is_success:
        console.print(f"Staked {amount} tokens to {dest}")
    else:
        raise ChainTransactionError(response.error_message)  # type: ignore


@balance_app.command()
def unstake(key: str, amount: float, dest: str, netuid: int = 0):
    """
    Unstake amount from destination using key
    """

    console = Console()
    client = make_client()

    nano_amount = to_nano(amount)
    resolved_key = classic_load_key(key)
    resolved_dest = resolve_key_ss58(dest)

    with console.status(f"Unstaking {amount} tokens from {dest} on a subnet with netuid '{netuid}'..."):

        response = client.unstake(key=resolved_key, amount=nano_amount,
                                  dest=resolved_dest, netuid=netuid)

    if response.is_success:
        console.print(f"Unstaked {amount} tokens from {dest}")
    else:
        raise ChainTransactionError(response.error_message)  # type: ignore
