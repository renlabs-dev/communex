from dataclasses import dataclass
from typing import Any, Mapping, cast

import rich
import typer
from rich.console import Console
from rich.table import Table
from typer import Context

from communex._common import get_node_url
from communex.client import CommuneClient


@dataclass
class ExtraCtxData:
    output_json: bool
    use_testnet: bool


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
                    self._com_client = CommuneClient(url=node_url, num_connections=1, wait_for_finalization=False)
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
