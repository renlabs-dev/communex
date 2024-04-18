import json
from enum import Enum
from typing import Any, cast

import typer
from substrateinterface import Keypair  # type: ignore
from typer import Context

from communex._common import BalanceUnit, format_balance
from communex.cli._common import (make_custom_context,
                                  print_table_from_plain_dict,
                                  print_table_standardize)
from communex.compat.key import (classic_key_path, classic_store_key,
                                 local_key_addresses, resolve_key_ss58)
from communex.compat.storage import classic_load
from communex.key import generate_keypair
from communex.misc import (local_keys_allbalance, local_keys_to_freebalance,
                           local_keys_to_stakedbalance)

key_app = typer.Typer()


class SortBalance(str, Enum):
    all = "all"
    free = "free"
    staked = "staked"


@key_app.command()
def create(ctx: Context, name: str):
    """
    Generates a new key and stores it on a disk with the given name.
    """
    context = make_custom_context(ctx)

    keypair = generate_keypair()
    address = keypair.ss58_address

    context.info(f"Generated key with public address '{address}'.")

    classic_store_key(keypair, name)

    context.info(f"Key successfully stored with name '{name}'.")


@key_app.command()
def regen(ctx: Context, name: str, mnemonic: str):
    """
    Stores the given key on a disk. Works with private key or mnemonic.
    """
    # TODO: secret input from env var and stdin
    context = make_custom_context(ctx)

    keypair = Keypair.create_from_mnemonic(mnemonic)
    address = keypair.ss58_address

    context.info(f"Loaded key with public address `{address}`.")

    classic_store_key(keypair, name)

    context.info(f"Key stored with name `{name}` successfully.")

@key_app.command()
def show(ctx: Context, key: str, show_private: bool = False):
    """
    Show information about a key.
    """
    context = make_custom_context(ctx)

    path = classic_key_path(key)
    key_dict_json = classic_load(path)
    key_dict = json.loads(key_dict_json)

    if show_private is not True:
        key_dict["private_key"] = "[SENSITIVE-MODE]"
        key_dict["seed_hex"] = "[SENSITIVE-MODE]"
        key_dict["mnemonic"] = "[SENSITIVE-MODE]"

    print_table_from_plain_dict(key_dict, ["Key", "Value"], context.console)


@key_app.command()
def balances(ctx: Context, netuid: int = 0, unit: BalanceUnit = BalanceUnit.joule, sort_balance: SortBalance = SortBalance.all,):
    """
    Gets balances of all keys.
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    with context.console.status("Getting balances of all keys, this might take a while..."):
        key2freebalance, key2stake = local_keys_allbalance(client, netuid)
    key_to_freebalance = {k: format_balance(v, unit) for k, v in key2freebalance.items()}
    key_to_stake = {k: format_balance(v, unit) for k, v in key2stake.items()}

    key2balance = {k: v + key2stake[k] for k, v in key2freebalance.items()}
    key_to_balance = {k: format_balance(v, unit) for k, v in key2balance.items()}

    if sort_balance == SortBalance.all:
        sorted_bal = {k: v for k, v in sorted(
            key2balance.items(), key=lambda item: item[1], reverse=True)}
    elif sort_balance == SortBalance.free:
        sorted_bal = {k: v for k, v in sorted(
            key2freebalance.items(), key=lambda item: item[1], reverse=True)}
    elif sort_balance == SortBalance.staked:
        sorted_bal = {k: v for k, v in sorted(
            key2stake.items(), key=lambda item: item[1], reverse=True)}
    else:
        raise ValueError("Invalid sort balance option")

    stake: list[str] = []
    all_balance: list[str] = []
    free: list[str] = []
    keys: list[str] = []

    for key, _ in sorted_bal.items():
        keys.append(key)
        free.append(key_to_freebalance[key])
        stake.append(key_to_stake[key])
        all_balance.append(key_to_balance[key])

    pretty_dict = {
        "key": keys,
        "free": free,
        "staked": stake,
        "all": all_balance,
    }

    general_dict: dict[str, list[Any]] = cast(dict[str, list[Any]], pretty_dict)
    print_table_standardize(general_dict, context.console)


@key_app.command(name='list')
def inventory(ctx: Context):
    """
    Lists all keys stored on disk.
    """
    context = make_custom_context(ctx)

    key_to_address = local_key_addresses()
    general_key_to_address: dict[str, str] = cast(dict[str, str], key_to_address)
    print_table_from_plain_dict(general_key_to_address, ["Key", "Address"], context.console)


@key_app.command()
def stakefrom(ctx: Context, key: str, netuid: int = 0, unit: BalanceUnit = BalanceUnit.joule):
    """
    Gets what keys is key staked from.
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    key_address = resolve_key_ss58(key)

    with context.progress_status(f"Getting stake-from map for {key_address}..."):
        result = client.get_stakefrom(key_addr=key_address, netuid=netuid)

    result = {k: format_balance(v, unit) for k, v in result.items()}

    print_table_from_plain_dict(result, ["Key", "Stake"], context.console)


@key_app.command()
def staketo(ctx: Context, key: str, netuid: int = 0, unit: BalanceUnit = BalanceUnit.joule):
    """
    Gets stake to a key.
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    key_address = resolve_key_ss58(key)

    with context.progress_status(f"Getting stake-to of {key_address}..."):
        result = client.get_staketo(key_addr=key_address, netuid=netuid)

    result = {k: format_balance(v, unit) for k, v in result.items()}

    print_table_from_plain_dict(result, ["Key", "Stake"], context.console)


@key_app.command()
def total_free_balance(ctx: Context, unit: BalanceUnit = BalanceUnit.joule):
    """
    Returns total balance of all keys on a disk
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    with context.progress_status("Getting total free balance of all keys..."):
        key2balance: dict[str, int] = local_keys_to_freebalance(client)

        balance_sum = sum(key2balance.values())

        context.output(format_balance(balance_sum, unit=unit))


@key_app.command()
def total_staked_balance(ctx: Context, unit: BalanceUnit = BalanceUnit.joule, netuid: int = 0):
    """
    Returns total stake of all keys on a disk
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    with context.progress_status("Getting total staked balance of all keys..."):
        key2stake: dict[str, int] = local_keys_to_stakedbalance(client, netuid=netuid)

        stake_sum = sum(key2stake.values())

        context.output(format_balance(stake_sum, unit=unit))


@key_app.command()
def total_balance(ctx: Context, unit: BalanceUnit = BalanceUnit.joule, netuid: int = 0):
    """
    Returns total tokens of all keys on a disk
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    with context.progress_status("Getting total tokens of all keys..."):
        key2balance, key2stake = local_keys_allbalance(client, netuid=netuid)
        key2tokens = {k: v + key2stake[k] for k, v in key2balance.items()}
        tokens_sum = sum(key2tokens.values())

        context.output(format_balance(tokens_sum, unit=unit))
