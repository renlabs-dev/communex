from dataclasses import dataclass
from typing import Any, Mapping, cast

import rich
import typer
from rich import box
from rich.console import Console
from rich.table import Table
from typer import Context

from communex._common import get_node_url
from communex.balance import from_horus, from_nano
from communex.client import CommuneClient
from communex.types import ModuleInfoWithOptionalBalance


@dataclass
class ExtraCtxData:
    output_json: bool
    use_testnet: bool
    yes_to_all: bool


class ExtendedContext(Context):
    obj: ExtraCtxData


@dataclass
class CustomCtx:
    ctx: ExtendedContext
    console: rich.console.Console
    console_err: rich.console.Console
    _com_client: CommuneClient | None = None

    def com_client(self) -> CommuneClient:
        use_testnet = self.ctx.obj.use_testnet
        if self._com_client is None:
            node_url = get_node_url(None, use_testnet=use_testnet)
            self.info(f"Using node: {node_url}")
            for _ in range(5):
                try:
                    self._com_client = CommuneClient(
                        url=node_url, num_connections=1, wait_for_finalization=False)
                except Exception:
                    self.info(f"Failed to connect to node: {node_url}")
                    node_url = get_node_url(None, use_testnet=use_testnet)
                    self.info(f"Will retry with node {node_url}")
                    continue
            if self._com_client is None:
                raise ConnectionError("Could not connect to any node")

        return self._com_client

    def output(self, message: str) -> None:
        self.console.print(message)

    def info(self, message: str) -> None:
        self.console_err.print(message)

    def error(self, message: str) -> None:
        message = f"ERROR: {message}"
        self.console_err.print(message, style="bold red")

    def progress_status(self, message: str):
        return self.console_err.status(message)

    def confirm(self, message: str) -> bool:
        if (self.ctx.obj.yes_to_all):
            print(f"{message} (--yes)")
            return True
        return typer.confirm(message)


def make_custom_context(ctx: typer.Context) -> CustomCtx:
    return CustomCtx(
        ctx=cast(ExtendedContext, ctx),
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
    result: Mapping[str, str | int | float], column_names: list[str], console: Console
) -> None:
    """
    Creates a table for a plain dictionary.
    """

    table = Table(show_header=True, header_style="bold magenta")

    for name in column_names:
        table.add_column(name, style="white")

    # Add rows to the table
    for key, value in result.items():
        table.add_row(key, str(value))

    console.print(table)


def print_table_standardize(result: dict[str, list[Any]], console: Console) -> None:
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


def transform_module_into(to_exclude: list[str], last_block: int, immunity_period: int, modules: list[ModuleInfoWithOptionalBalance]):
    mods = cast(list[dict[str, Any]], modules)
    transformed_modules: list[dict[str, Any]] = []
    for mod in mods:
        module = mod.copy()
        module_regblock = module["regblock"]
        module["in_immunity"] = module_regblock + immunity_period > last_block

        for key in to_exclude:
            del module[key]
        module["stake"] = round(from_nano(module["stake"]), 2)  # type: ignore
        module["emission"] = round(from_horus(
            module["emission"]), 4)  # type: ignore
        if module.get("balance") is not None:
            module["balance"] = from_nano(module["balance"])  # type: ignore
        else:
            # user should not see None values
            del module["balance"]
        transformed_modules.append(module)

    return transformed_modules


def print_module_info(
        client: CommuneClient, modules: list[ModuleInfoWithOptionalBalance], console: Console,
        netuid: int, title: str | None = None,
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

    # Transform the module dictionary to have immunity_period
    table = Table(
        show_header=True, header_style="bold magenta",
        box=box.DOUBLE_EDGE, title=title,
        caption_style="chartreuse3",
        title_style="bold magenta",

    )

    to_exclude = ["stake_from", "metadata", "last_update", "regblock"]
    tranformed_modules = transform_module_into(
        to_exclude, last_block, immunity_period, modules)

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
