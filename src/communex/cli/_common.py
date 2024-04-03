from dataclasses import dataclass
from typing import Any, Mapping, Optional

import rich
import typer
from rich.console import Console
from rich.table import Table


@dataclass
class CustomCtx:
    typer_ctx: typer.Context
    console: rich.console.Console
    console_err: rich.console.Console

    def output(self, message: str) -> None:
        self.console.print(message)

    def info(self, message: str) -> None:
        self.console_err.print(message)

    def error(self, message: str) -> None:
        message = f"ERROR: {message}"
        self.console_err.print(message, style="bold red")

    def progress_status(self, message: str):
        return self.console_err.status(message)


def make_custom_context(ctx: typer.Context) -> CustomCtx:
    return CustomCtx(
        typer_ctx=ctx,
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

def create_use_testnet_getter():
    use_testnet = False
    def state_function(testnet: Optional[bool]=None):
        nonlocal use_testnet
        if testnet is not None:
            use_testnet = testnet
        return use_testnet

    return state_function

get_use_testnet = create_use_testnet_getter()