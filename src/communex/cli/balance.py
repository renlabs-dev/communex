import typer
from rich.console import Console

from communex.balance import to_nano
from cexpl.commune.key import Key
from communex.errors import ChainTransactionError

from ._common import BalanceUnit, format_balance, make_client

balance_app = typer.Typer()


@balance_app.command()
def show(key: str, netuid: int = 0, unit: BalanceUnit = BalanceUnit.joule):
    """
    Gets the balances of a key.
    """

    console = Console()
    client = make_client()

    key_address = Key.resolve_key_ss58(key)  # TODO: commune.compat.key.classic_resolve_key_ss58

    with console.status(f"Getting balance of key {key_address}..."):
        balance = client.get_balance(key_address)
        staketo = client.get_staketo(key_addr=key_address, netuid=netuid)

    staketo_sum = sum(staketo.values())

    total = balance + staketo_sum

    console.print(f"Balances of key {key_address}")
    console.print("Free:  ", format_balance(balance, unit))
    console.print("Staked:", format_balance(staketo_sum, unit))
    console.print("Total: ", format_balance(total, unit))


@balance_app.command()
def free_balance(key: str, unit: BalanceUnit = BalanceUnit.joule):
    """
    Gets free balance of a key.
    """

    console = Console()
    client = make_client()

    key_address = Key.resolve_key_ss58(key)

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

    key_address = Key.resolve_key_ss58(key)

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

    key_address = Key.resolve_key_ss58(key)

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

    key_address = Key.resolve_key_ss58(key)

    with console.status(f"Getting stake of {key_address}..."):
        result = client.get_stake(key=key_address, netuid=netuid)

    console.print(format_balance(result, unit))


@balance_app.command()
def transfer(key: str, amount: float, dest: str):
    """
    Transfer amount to destination using key
    """

    console = Console()
    client = make_client()

    nano_amount = to_nano(amount)
    resolved_key = Key.resolve_key(key)
    resolved_dest = Key.resolve_key_ss58(dest)

    # TODO: refactor yes/no prompts into function
    console.print(
        f"Please confirm that you want to transfer {amount} tokens to {dest} using key {key} (y/n)")

    answer = input().lower()

    if answer == "y":
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

    resolved_from = Key.resolve_key_ss58(from_key)
    resolved_dest = Key.resolve_key_ss58(dest)
    resolved_key = Key.resolve_key(key)
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
    resolved_key = Key.resolve_key(key)
    resolved_dest = Key.resolve_key_ss58(dest)

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
    resolved_key = Key.resolve_key(key)
    resolved_dest = Key.resolve_key_ss58(dest)

    with console.status(f"Unstaking {amount} tokens from {dest} on a subnet with netuid '{netuid}'..."):

        response = client.unstake(key=resolved_key, amount=nano_amount,
                                  dest=resolved_dest, netuid=netuid)

    if response.is_success:
        console.print(f"Unstaked {amount} tokens from {dest}")
    else:
        raise ChainTransactionError(response.error_message)  # type: ignore
