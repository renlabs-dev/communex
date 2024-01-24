from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

import rich
import typer
from rich.console import Console
from rich.table import Table

from communex.client import CommuneClient
from communex.balance import from_nano


class BalanceUnit(str, Enum):
    joule = "joule"
    j = "j"
    nano = "nano"
    n = "n"


@dataclass
class CustomCtx:
    typer_ctx: typer.Context
    console: rich.console.Console
    console_err: rich.console.Console

    def output(self, message: str) -> None:
        self.console.print(message)

    def info(self, message: str) -> None:
        self.console_err.print(message)


def make_custom_context(ctx: typer.Context) -> CustomCtx:
    return CustomCtx(
        typer_ctx=ctx,
        console=Console(),
        console_err=Console(stderr=True),
    )


# Client

def get_node_url() -> str:
    return "wss://commune-node-0.agicommies.org"


def make_client():
    """
    Create a client to the Commune network.
    """

    node_url = get_node_url()
    return CommuneClient(url=node_url, num_connections=1, wait_for_finalization=False)

# Formatting


def eprint(e: Any) -> None:
    """
    Pretty prints an error.
    """

    console = Console()

    console.print(f"[bold red]ERROR: {e}", style="italic")


def format_balance(balance: int, unit: BalanceUnit = BalanceUnit.nano) -> str:
    """
    Formats a balance.
    """

    match unit:
        case BalanceUnit.nano | BalanceUnit.n:
            return f"{balance}"
        case BalanceUnit.joule | BalanceUnit.j:
            in_joules = from_nano(balance)
            round_joules = round(in_joules, 4)
            return f"{round_joules:,} J"


def print_table_from_plain_dict(result: Mapping[str, str | int], column_names: list[str], console: Console) -> None:
    """
    Creates a table for a plain dictionary.
    """

    table = Table(show_header=True, header_style="bold magenta")

    for name in column_names:
        table.add_column(name, style="dim")

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
        table.add_column(key, style="dim")
    rows = [*result.values()]
    zipped_rows = [list(column) for column in zip(*rows)]
    for row in zipped_rows:
        table.add_row(*row, style="dim")

    console.print(table)
