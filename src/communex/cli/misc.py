import typer
from typer import Context

from communex._common import BalanceUnit, format_balance
from communex.balance import from_nano
from communex.cli._common import make_custom_context
from communex.client import CommuneClient

misc_app = typer.Typer()


def circulating_tokens(c_client: CommuneClient) -> int:
    """
    Gets total circulating supply
    """

    query_all = c_client.query_batch_map(
        {
            "SubspaceModule": [("TotalStake", [])],
            "System": [("Account", [])],
        }
    )

    balances, stake = query_all["Account"], query_all["TotalStake"]
    format_balances: dict[str, int] = {
        key: value["data"]["free"] for key, value in balances.items() if "data" in value and "free" in value["data"]
    }

    total_balance = sum(format_balances.values())
    total_stake = sum(stake.values())

    return total_stake + total_balance


@misc_app.command()
def circulating_supply(ctx: Context, unit: BalanceUnit = BalanceUnit.joule):
    """
    Gets the value of all keys on the network, stake + balances
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    with context.progress_status("Getting circulating supply, across all subnets..."):
        supply = circulating_tokens(client)

    context.output(format_balance(supply, unit))


@misc_app.command()
def apr(ctx: Context, fee: int = 0):
    """
    Gets the current staking APR on validators.
    The miner reinvest rate & fee are specified in percentages.
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    # adjusting the fee to the correct format
    # the default validator fee on the commune network is 20%
    fee_to_float = fee / 100

    # network parameters
    block_time = 8  # seconds
    seconds_in_a_day = 86400
    blocks_in_a_day = seconds_in_a_day / block_time

    with context.progress_status("Getting staking APR..."):
        unit_emission = client.get_unit_emission()
        staked = client.query_batch_map(
            {
                "SubspaceModule": [("TotalStake", [])],
            }
        )["TotalStake"]

        total_staked_tokens = from_nano(sum(staked.values()))

    # 50% of the total emission goes to stakers
    daily_token_rewards = blocks_in_a_day * from_nano(unit_emission) / 2
    _apr = (daily_token_rewards * (1 - fee_to_float) * 365) / total_staked_tokens * 100

    context.output(f"Fee {fee} | APR {_apr:.2f}%")
