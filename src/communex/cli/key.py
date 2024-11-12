import re
from enum import Enum
from typing import Any, Optional, cast

import typer
from substrateinterface import Keypair
from typeguard import check_type
from typer import Context

import communex.compat.key as comx_key
from communex._common import BalanceUnit, format_balance
from communex.cli._common import (
    make_custom_context,
    print_table_from_plain_dict,
    print_table_standardize,
)
from communex.compat.key import (
    classic_store_key,
    local_key_addresses,
)
from communex.key import check_ss58_address, generate_keypair, is_ss58_address
from communex.misc import (
    local_keys_allbalance,
    local_keys_to_freebalance,
    local_keys_to_stakedbalance,
)

key_app = typer.Typer(no_args_is_help=True)


class SortBalance(str, Enum):
    all = "all"
    free = "free"
    staked = "staked"


@key_app.command()
def create(ctx: Context, name: str, password: str = typer.Option(None)):
    """
    Generates a new key and stores it on a disk with the given name.
    """
    context = make_custom_context(ctx)

    keypair = generate_keypair()
    address = keypair.ss58_address

    context.info(f"Generated key with public address '{address}'.")

    classic_store_key(keypair, name, password)

    context.info(f"Key successfully stored with name '{name}'.")


@key_app.command()
def regen(
    ctx: Context, name: str, key_input: str, password: Optional[str] = None
):
    """
    Stores the given key on a disk. Works with private key or mnemonic.
    """
    context = make_custom_context(ctx)
    # TODO: secret input from env var and stdin

    # Determine the input type based on the presence of spaces.
    if re.search(r"\s", key_input):
        # If mnemonic (contains spaces between words).
        keypair = Keypair.create_from_mnemonic(key_input)
        key_type = "mnemonic"
    else:
        # If private key (assumes no spaces).
        keypair = Keypair.create_from_private_key(key_input, ss58_format=42)
        key_type = "private key"
        # Substrate does not return these.
        keypair.mnemonic = ""  # type: ignore
        keypair.seed_hex = ""

    address = keypair.ss58_address
    context.info(f"Loaded {key_type} with public address `{address}`.")

    classic_store_key(keypair, name, password)

    context.info(f"Key stored with name `{name}` successfully.")


@key_app.command()
def show(
    ctx: Context,
    key: str,
    show_private: bool = False,
    password: Optional[str] = None,
):
    """
    Show information about a key.
    """
    context = make_custom_context(ctx)

    keypair = context.load_key(key, password)
    key_dict = comx_key.to_classic_dict(keypair, path=key)

    if show_private is not True:
        key_dict["private_key"] = "[SENSITIVE-MODE]"
        key_dict["seed_hex"] = "[SENSITIVE-MODE]"
        key_dict["mnemonic"] = "[SENSITIVE-MODE]"

    key_dict = check_type(key_dict, dict[str, Any])

    print_table_from_plain_dict(key_dict, ["Key", "Value"], context.console)


@key_app.command()
def balances(
    ctx: Context,
    unit: BalanceUnit = BalanceUnit.joule,
    sort_balance: SortBalance = SortBalance.all,
):
    """
    Gets balances of all keys.
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    local_keys = local_key_addresses(context.password_manager)
    with context.console.status(
        "Getting balances of all keys, this might take a while..."
    ):
        key2freebalance, key2stake = local_keys_allbalance(client, local_keys)
    key_to_freebalance = {
        k: format_balance(v, unit) for k, v in key2freebalance.items()
    }
    key_to_stake = {k: format_balance(v, unit) for k, v in key2stake.items()}

    key2balance = {k: v + key2stake[k] for k, v in key2freebalance.items()}
    key_to_balance = {
        k: format_balance(v, unit) for k, v in key2balance.items()
    }

    if sort_balance == SortBalance.all:
        sorted_bal = {
            k: v
            for k, v in sorted(
                key2balance.items(), key=lambda item: item[1], reverse=True
            )
        }
    elif sort_balance == SortBalance.free:
        sorted_bal = {
            k: v
            for k, v in sorted(
                key2freebalance.items(), key=lambda item: item[1], reverse=True
            )
        }
    elif sort_balance == SortBalance.staked:
        sorted_bal = {
            k: v
            for k, v in sorted(
                key2stake.items(), key=lambda item: item[1], reverse=True
            )
        }
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


@key_app.command(name="list")
def inventory(
    ctx: Context,
):
    """
    Lists all keys stored on disk.
    """
    context = make_custom_context(ctx)

    key_to_address = local_key_addresses(context.password_manager)
    general_key_to_address: dict[str, str] = cast(
        dict[str, str], key_to_address
    )
    print_table_from_plain_dict(
        general_key_to_address, ["Key", "Address"], context.console
    )


@key_app.command()
def stakefrom(
    ctx: Context,
    key: str,
    unit: BalanceUnit = BalanceUnit.joule,
    password: Optional[str] = None,
):
    """
    Gets what keys is key staked from.
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    if is_ss58_address(key):
        key_address = key
    else:
        keypair = context.load_key(key, password)
        key_address = keypair.ss58_address
        key_address = check_ss58_address(key_address)
    with context.progress_status(
        f"Getting stake-from map for {key_address}..."
    ):
        result = client.get_stakefrom(key=key_address)

    result = {k: format_balance(v, unit) for k, v in result.items()}

    print_table_from_plain_dict(result, ["Key", "Stake"], context.console)


@key_app.command()
def staketo(
    ctx: Context,
    key: str,
    unit: BalanceUnit = BalanceUnit.joule,
    password: Optional[str] = None,
):
    """
    Gets stake to a key.
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    if is_ss58_address(key):
        key_address = key
    else:
        keypair = context.load_key(key, password)
        key_address = keypair.ss58_address
        key_address = check_ss58_address(key_address)

    with context.progress_status(f"Getting stake-to of {key_address}..."):
        result = client.get_staketo(key=key_address)

    result = {k: format_balance(v, unit) for k, v in result.items()}

    print_table_from_plain_dict(result, ["Key", "Stake"], context.console)


@key_app.command()
def total_free_balance(
    ctx: Context,
    unit: BalanceUnit = BalanceUnit.joule,
    use_universal_password: Optional[str] = typer.Option(
        False,
        help="""
        Password to decrypt all keys.
        This will only work if all encrypted keys uses the same password.
        If this is not the case, leave it blank and you will be prompted to give
        every password.
        """,
    ),
):
    """
    Returns total balance of all keys on a disk
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    local_keys = local_key_addresses(context.password_manager)
    with context.progress_status("Getting total free balance of all keys..."):
        key2balance: dict[str, int] = local_keys_to_freebalance(
            client, local_keys
        )

        balance_sum = sum(key2balance.values())

        context.output(format_balance(balance_sum, unit=unit))


@key_app.command()
def total_staked_balance(
    ctx: Context,
    unit: BalanceUnit = BalanceUnit.joule,
    use_universal_password: bool = typer.Option(
        False,
        help="""
    Password to decrypt all keys.
    This will only work if all encrypted keys uses the same password.
    If this is not the case, leave it blank and you will be prompted to give
    every password.
    """,
    ),
):
    """
    Returns total stake of all keys on a disk
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    local_keys = local_key_addresses(context.password_manager)
    with context.progress_status("Getting total staked balance of all keys..."):
        key2stake: dict[str, int] = local_keys_to_stakedbalance(
            client,
            local_keys,
        )

        stake_sum = sum(key2stake.values())

        context.output(format_balance(stake_sum, unit=unit))


@key_app.command()
def total_balance(
    ctx: Context,
    unit: BalanceUnit = BalanceUnit.joule,
    use_universal_password: bool = typer.Option(
        False,
        help="""
    Password to decrypt all keys.
    This will only work if all encrypted keys uses the same password.
    If this is not the case, leave it blank and you will be prompted to give
    every password.
    """,
    ),
):
    """
    Returns total tokens of all keys on a disk
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    local_keys = local_key_addresses(context.password_manager)
    with context.progress_status("Getting total tokens of all keys..."):
        key2balance, key2stake = local_keys_allbalance(client, local_keys)
        key2tokens = {k: v + key2stake[k] for k, v in key2balance.items()}
        tokens_sum = sum(key2tokens.values())

        context.output(format_balance(tokens_sum, unit=unit))


@key_app.command()
def power_delegation(
    ctx: Context,
    key: Optional[str] = None,
    enable: bool = typer.Option(True, "--disable"),
):
    """
    Gets power delegation of a key.
    """
    context = make_custom_context(ctx)
    client = context.com_client()
    if key is None:
        action = "enable" if enable else "disable"
        confirm_message = (
            f"Key was not set, this will {action} vote power delegation for all"
            " keys on disk. Do you want to proceed?"
        )
        if not typer.confirm(confirm_message):
            context.info("Aborted.")
            exit(0)

        local_keys = local_key_addresses(context.password_manager)
    else:
        local_keys = {key: None}
    for key_name in local_keys.keys():
        keypair = context.load_key(key_name, None)
        if enable is True:
            context.info(
                f"Enabling vote power delegation on key {key_name} ..."
            )
            client.enable_vote_power_delegation(keypair)
        else:
            context.info(
                f"Disabling vote power delegation on key {key_name} ..."
            )
            client.disable_vote_power_delegation(keypair)
