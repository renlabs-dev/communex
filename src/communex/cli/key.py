import json
from typing import cast

import typer
from rich.console import Console
from typer import Context

from cexpl.commune.key import Key
from communex.compat.key import classic_key_path, local_key_addresses
from communex.compat.storage import classic_load
from communex.misc import (local_keys_allbalance, local_keys_to_freebalance,
                           local_keys_to_stakedbalance)

from ._common import (BalanceUnit, format_balance, make_client,
                      make_custom_context, print_table_from_plain_dict)

key_app = typer.Typer()

# TODO: refactor `Key` out


@key_app.command()
def create(ctx: Context, name: str):
    """
    Generates a new key and stores it on a disk with the given name.
    """
    context = make_custom_context(ctx)

    key = Key.generate(name)
    key_address = key.keypair.ss58_address
    context.info(f"Generated key with public address '{key_address}'.")
    key.commune_store()
    context.info(f"Key successfully stored with name '{name}'.")


@key_app.command(name="regen")
def save(ctx: Context, name: str, mnemonic: str):
    """
    Stores the given key on a disk. Works with private key or mnemonic.
    """
    # TODO: secret input from env var and stdin
    context = make_custom_context(ctx)

    key = Key.from_mnemonic(name, mnemonic)
    key_address = key.keypair.ss58_address
    context.info(f"Loaded key with public address `{key_address}`.")
    key.commune_store()
    context.info(f"Key stored with name `{name}` successfully.")


@key_app.command()
def show(key: str, private: bool = False):
    console = Console()

    path = classic_key_path(key)
    key_dict_json = classic_load(path)
    key_dict = json.loads(key_dict_json)

    if private is not True:
        key_dict["private_key"] = "[SENSITIVE-MODE]"
        key_dict["seed_hex"] = "[SENSITIVE-MODE]"
        key_dict["mnemonic"] = "[SENSITIVE-MODE]"

    print_table_from_plain_dict(key_dict, ["Key", "Value"], console)


@key_app.command(name='list')
def inventory(
    ctx: Context,
    # netuid: int = 0,
    # balances: bool = False,
    # sort_balance: SortBalanceOptions = SortBalanceOptions.all,
    # unit: BalanceUnit = BalanceUnit.joule
):
    """
    Lists all keys stored on disk, optionally with balances.
    """
    context = make_custom_context(ctx)

    # if not balances:

    key_to_address = local_key_addresses()
    general_key_to_address: dict[str, str] = cast(dict[str, str], key_to_address)
    print_table_from_plain_dict(general_key_to_address, ["Key", "Address"], context.console)

    # else:
    #     client = make_client()
    #     with context.console.status("Getting balances of all keys, this might take a while..."):
    #         key2freebalance, key2stake = local_key2allbalances(client, netuid)
    #     key_to_freebalance = {k: format_balance(v, unit) for k, v in key2freebalance.items()}
    #     key_to_stake = {k: format_balance(v, unit) for k, v in key2stake.items()}

    #     key2balance = {k: v + key2stake[k] for k, v in key2freebalance.items()}
    #     key_to_balance = {k: format_balance(v, unit) for k, v in key2balance.items()}

    #     if sort_balance == SortBalanceOptions.all:
    #         sorted_bal = {k: v for k, v in sorted(
    #             key2balance.items(), key=lambda item: item[1], reverse=True)}
    #     elif sort_balance == SortBalanceOptions.free:
    #         sorted_bal = {k: v for k, v in sorted(
    #             key2freebalance.items(), key=lambda item: item[1], reverse=True)}
    #     elif sort_balance == SortBalanceOptions.stake:
    #         sorted_bal = {k: v for k, v in sorted(
    #             key2stake.items(), key=lambda item: item[1], reverse=True)}
    #     else:
    #         raise ValueError("Invalid sort balance option")

    #     stake: list[str] = []
    #     all_balance: list[str] = []
    #     free: list[str] = []
    #     keys: list[str] = []

    #     for key, _ in sorted_bal.items():
    #         keys.append(key)
    #         free.append(key_to_freebalance[key])
    #         stake.append(key_to_stake[key])
    #         all_balance.append(key_to_balance[key])

    #     pretty_dict = {
    #         "key": keys,
    #         "free": free,
    #         "staked": stake,
    #         "all": all_balance,
    #     }

    #     general_dict: dict[str, list[Any]] = cast(dict[str, list[Any]], pretty_dict)
    #     print_table_standardize(general_dict, context.console)


@key_app.command()
def stakefrom(key: str, netuid: int = 0, unit: BalanceUnit = BalanceUnit.joule):
    """
    Gets what keys is key staked from.
    """

    console = Console()
    client = make_client()

    key_address = Key.resolve_key_ss58(key)

    with console.status(f"Getting stake-from map for {key_address}..."):
        result = client.get_stakefrom(key_addr=key_address, netuid=netuid)

    result = {k: format_balance(v, unit) for k, v in result.items()}

    print_table_from_plain_dict(result, ["Key", "Stake"], console)


@key_app.command()
def staketo(key: str, netuid: int = 0, unit: BalanceUnit = BalanceUnit.joule):
    """
    Gets stake to a key.
    """

    console = Console()
    client = make_client()

    key_address = Key.resolve_key_ss58(key)

    with console.status(f"Getting stake-to of {key_address}..."):
        result = client.get_staketo(key_addr=key_address, netuid=netuid)

    result = {k: format_balance(v, unit) for k, v in result.items()}

    # Table
    print_table_from_plain_dict(result, ["Key", "Stake"], console)


@key_app.command()
def total_free_balance(unit: BalanceUnit = BalanceUnit.joule):
    """
    Returns total balance of all keys on a disk
    """

    console = Console()
    client = make_client()

    with console.status("Getting total free balance of all keys..."):
        key2balance: dict[str, int] = local_keys_to_freebalance(client)

        balance_sum = sum(key2balance.values())

        console.print(format_balance(balance_sum, unit=unit))


@key_app.command()
def total_staked_balance(unit: BalanceUnit = BalanceUnit.joule, netuid: int = 0):
    """
    Returns total stake of all keys on a disk
    """

    console = Console()
    client = make_client()

    with console.status("Getting total staked balance of all keys..."):
        key2stake: dict[str, int] = local_keys_to_stakedbalance(client, netuid=netuid)

        stake_sum = sum(key2stake.values())

        console.print(format_balance(stake_sum, unit=unit))


@key_app.command()
def total_balance(unit: BalanceUnit = BalanceUnit.joule, netuid: int = 0):
    """
    Returns total tokens of all keys on a disk
    """

    console = Console()
    client = make_client()

    with console.status("Getting total tokens of all keys..."):
        key2balance, key2stake = local_keys_allbalance(client, netuid=netuid)
        key2tokens = {k: v + key2stake[k] for k, v in key2balance.items()}
        tokens_sum = sum(key2tokens.values())

        console.print(format_balance(tokens_sum, unit=unit))
