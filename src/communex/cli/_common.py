from dataclasses import dataclass
from getpass import getpass
from typing import Any, Callable, Mapping, TypeVar, cast

import rich
import rich.prompt
import typer
from rich import box
from rich.console import Console
from rich.table import Table
from substrateinterface import Keypair
from typer import Context

from communex._common import ComxSettings, get_node_url
from communex.balance import dict_from_nano, from_horus, from_nano
from communex.client import CommuneClient
from communex.compat.key import resolve_key_ss58_encrypted, try_classic_load_key
from communex.errors import InvalidPasswordError, PasswordNotProvidedError
from communex.types import (
    ModuleInfoWithOptionalBalance,
    NetworkParams,
    Ss58Address,
    SubnetParamsWithEmission,
)


@dataclass
class ExtraCtxData:
    output_json: bool
    use_testnet: bool
    yes_to_all: bool


class ExtendedContext(Context):
    obj: ExtraCtxData


class CliPasswordProvider:
    def __init__(
        self, settings: ComxSettings, prompt_secret: Callable[[str], str]
    ):
        self.settings = settings
        self.prompt_secret = prompt_secret

    def get_password(self, key_name: str) -> str | None:
        key_map = self.settings.KEY_PASSWORDS
        if key_map is not None:
            password = key_map.get(key_name)
            if password is not None:
                return password.get_secret_value()
        # fallback to universal password
        password = self.settings.UNIVERSAL_PASSWORD
        if password is not None:
            return password.get_secret_value()
        else:
            return None

    def ask_password(self, key_name: str) -> str:
        password = self.prompt_secret(
            f"Please provide the password for the key '{key_name}'"
        )
        return password


class CustomCtx:
    ctx: ExtendedContext
    settings: ComxSettings
    console: rich.console.Console
    console_err: rich.console.Console
    password_manager: CliPasswordProvider
    _com_client: CommuneClient | None = None

    def __init__(
        self,
        ctx: ExtendedContext,
        settings: ComxSettings,
        console: rich.console.Console,
        console_err: rich.console.Console,
        com_client: CommuneClient | None = None,
    ):
        self.ctx = ctx
        self.settings = settings
        self.console = console
        self.console_err = console_err
        self._com_client = com_client
        self.password_manager = CliPasswordProvider(
            self.settings, self.prompt_secret
        )

    def get_use_testnet(self) -> bool:
        return self.ctx.obj.use_testnet

    def get_node_url(self) -> str:
        use_testnet = self.get_use_testnet()
        return get_node_url(self.settings, use_testnet=use_testnet)

    def com_client(self) -> CommuneClient:
        if self._com_client is None:
            node_url = self.get_node_url()
            self.info(f"Using node: {node_url}")
            for _ in range(5):
                try:
                    self._com_client = CommuneClient(
                        url=node_url,
                        num_connections=1,
                        wait_for_finalization=False,
                    )
                except Exception:
                    self.info(f"Failed to connect to node: {node_url}")
                    node_url = self.get_node_url()
                    self.info(f"Will retry with node {node_url}")
                    continue
            if self._com_client is None:
                raise ConnectionError("Could not connect to any node")

        return self._com_client

    def output(
        self,
        message: str,
        *args: tuple[Any, ...],
        **kwargs: dict[str, Any],
    ) -> None:
        self.console.print(message, *args, **kwargs)  # type: ignore

    def info(
        self,
        message: str,
        *args: tuple[Any, ...],
        **kwargs: dict[str, Any],
    ) -> None:
        self.console_err.print(message, *args, **kwargs)  # type: ignore

    def error(
        self,
        message: str,
        *args: tuple[Any, ...],
        **kwargs: dict[str, Any],
    ) -> None:
        message = f"ERROR: {message}"
        self.console_err.print(message, *args, style="bold red", **kwargs)  # type: ignore

    def progress_status(self, message: str):
        return self.console_err.status(message)

    def confirm(self, message: str) -> bool:
        if self.ctx.obj.yes_to_all:
            print(f"{message} (--yes)")
            return True
        return typer.confirm(message, err=True)

    def prompt_secret(self, message: str) -> str:
        return rich.prompt.Prompt.ask(
            message, password=True, console=self.console_err
        )

    def load_key(self, key: str, password: str | None = None) -> Keypair:
        try:
            keypair = try_classic_load_key(
                key, password, password_provider=self.password_manager
            )
            return keypair
        except PasswordNotProvidedError:
            self.error(f"Password not provided for key '{key}'")
            raise typer.Exit(code=1)
        except InvalidPasswordError:
            self.error(f"Incorrect password for key '{key}'")
            raise typer.Exit(code=1)

    def resolve_key_ss58(
        self, key: Ss58Address | Keypair | str, password: str | None = None
    ) -> Ss58Address:
        try:
            address = resolve_key_ss58_encrypted(
                key, password, password_provider=self.password_manager
            )
            return address
        except PasswordNotProvidedError:
            self.error(f"Password not provided for key '{key}'")
            raise typer.Exit(code=1)
        except InvalidPasswordError:
            self.error(f"Incorrect password for key '{key}'")
            raise typer.Exit(code=1)


def make_custom_context(ctx: typer.Context) -> CustomCtx:
    return CustomCtx(
        ctx=cast(ExtendedContext, ctx),  # TODO: better check
        settings=ComxSettings(),
        console=Console(),
        console_err=Console(stderr=True),
    )


# Formatting


def eprint(e: Any) -> None:
    """
    Pretty prints an error.
    """

    console = Console()

    console.print(f"[bold red]ERROR: {e}", style="italic")


def print_table_from_plain_dict(
    result: Mapping[str, str | int | float | dict[Any, Any] | Ss58Address],
    column_names: list[str],
    console: Console,
) -> None:
    """
    Creates a table for a plain dictionary.
    """

    table = Table(show_header=True, header_style="bold magenta")

    for name in column_names:
        table.add_column(name, style="white", vertical="middle")

    # Add non-dictionary values to the table first
    for key, value in result.items():
        if not isinstance(value, dict):
            table.add_row(key, str(value))
    # Add subtables for nested dictionaries.
    # Important to add after so that the display of the table is nicer.
    for key, value in result.items():
        if isinstance(value, dict):
            subtable = Table(
                show_header=False,
                padding=(0, 0, 0, 0),
                border_style="bright_black",
            )
            for subkey, subvalue in value.items():
                subtable.add_row(f"{subkey}: {subvalue}")
            table.add_row(key, subtable)

    console.print(table)


def print_table_standardize(
    result: dict[str, list[Any]], console: Console
) -> None:
    """
    Creates a table for a standardized dictionary.
    """
    table = Table(show_header=True, header_style="bold magenta")

    for key in result.keys():
        table.add_column(key, style="white")
    rows = [*result.values()]
    zipped_rows = [list(column) for column in zip(*rows)]
    for row in zipped_rows:
        table.add_row(*row, style="white")

    console.print(table)


def transform_module_into(
    to_exclude: list[str],
    last_block: int,
    immunity_period: int,
    modules: list[ModuleInfoWithOptionalBalance],
    tempo: int,
):
    mods = cast(list[dict[str, Any]], modules)
    transformed_modules: list[dict[str, Any]] = []
    for mod in mods:
        module = mod.copy()
        module_regblock = module["regblock"]
        module["in_immunity"] = module_regblock + immunity_period > last_block

        for key in to_exclude:
            del module[key]
        module["stake"] = round(from_nano(module["stake"]), 2)  # type: ignore
        module["emission"] = round(from_horus(module["emission"], tempo), 4)  # type: ignore
        if module.get("balance") is not None:
            module["balance"] = from_nano(module["balance"])  # type: ignore
        else:
            # user should not see None values
            del module["balance"]
        transformed_modules.append(module)

    return transformed_modules


def print_module_info(
    client: CommuneClient,
    modules: list[ModuleInfoWithOptionalBalance],
    console: Console,
    netuid: int,
    title: str | None = None,
) -> None:
    """
    Prints information about a module.
    """
    if not modules:
        return

    # Get the current block number, we will need this to caluclate immunity period
    block = client.get_block()
    if block:
        last_block = block["header"]["number"]
    else:
        raise ValueError("Could not get block info")

    # Get the immunity period on the netuid
    immunity_period = client.get_immunity_period(netuid)
    tempo = client.get_tempo(netuid)

    # Transform the module dictionary to have immunity_period
    table = Table(
        show_header=True,
        header_style="bold magenta",
        box=box.DOUBLE_EDGE,
        title=title,
        caption_style="chartreuse3",
        title_style="bold magenta",
    )

    to_exclude = ["stake_from", "last_update", "regblock"]
    tranformed_modules = transform_module_into(
        to_exclude, last_block, immunity_period, modules, tempo
    )

    sample_mod = tranformed_modules[0]
    for key in sample_mod.keys():
        # add columns
        table.add_column(key, style="white")

    total_stake = 0
    total_balance = 0

    for mod in tranformed_modules:
        total_stake += mod["stake"]
        if mod.get("balance") is not None:
            total_balance += mod["balance"]

        row: list[str] = []
        for val in mod.values():
            row.append(str(val))
        table.add_row(*row)

    table.caption = "total balance: " + f"{total_balance + total_stake}J"
    console.print(table)
    for _ in range(3):
        console.print()


def get_universal_password(ctx: CustomCtx) -> str:
    ctx.info("Please provide the universal password for all keys")
    universal_password = getpass()
    return universal_password


def tranform_network_params(params: NetworkParams):
    """Transform network params to be human readable."""
    governance_config = params["governance_config"]
    allocation = governance_config["proposal_reward_treasury_allocation"]
    governance_config = cast(dict[str, Any], governance_config)
    governance_config["proposal_reward_treasury_allocation"] = f"{allocation}%"
    params_ = cast(dict[str, Any], params)
    params_["governance_config"] = governance_config
    general_params = dict_from_nano(
        params_,
        [
            "min_weight_stake",
            "general_subnet_application_cost",
            "subnet_registration_cost",
            "proposal_cost",
            "max_proposal_reward_treasury_allocation",
        ],
    )

    return general_params


T = TypeVar("T")
V = TypeVar("V")


def remove_none_values(data: dict[T, V | None]) -> dict[T, V]:
    """
    Removes key-value pairs from a dictionary where the value is None.
    Works recursively for nested dictionaries.
    """
    cleaned_data: dict[T, V] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            cleaned_value = remove_none_values(value)  # type: ignore
            if cleaned_value is not None:  # type: ignore
                cleaned_data[key] = cleaned_value
        elif value is not None:
            cleaned_data[key] = value
    return cleaned_data


def transform_subnet_params(params: dict[int, SubnetParamsWithEmission]):
    """Transform subnet params to be human readable."""
    params_ = cast(dict[int, Any], params)
    display_params = remove_none_values(params_)
    display_params = dict_from_nano(
        display_params,
        [
            "bonds_ma",
            "min_burn",
            "max_burn",
            "min_weight_stake",
            "proposal_cost",
            "max_proposal_reward_treasury_allocation",
            "min_validator_stake",
        ],
    )
    return display_params
