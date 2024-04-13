from typing import Any, cast
from typeguard import check_type

import typer
from typer import Context
from rich.progress import track

from communex.cli._common import make_custom_context, print_table_from_plain_dict
from communex.compat.key import classic_load_key, resolve_key_ss58
from communex.misc import get_global_params, local_keys_to_stakedbalance
from communex.types import NetworkParams, SubnetParams
from communex.client import CommuneClient


network_app = typer.Typer()


@network_app.command()
def last_block(ctx: Context, hash: bool = False):
    """
    Gets the last block
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    info = "number" if not hash else "hash"

    block = client.get_block()
    block_info = None
    if block:
        block_info = block["header"][info]

    context.output(str(block_info))


@network_app.command()
def params(ctx: Context):
    """
    Gets global params
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    with context.progress_status("Getting global network params ..."):
        global_params = get_global_params(client)

    general_params: dict[str, Any] = cast(dict[str, Any], global_params)
    print_table_from_plain_dict(general_params, ["Global params", "Value"], context.console)


@network_app.command()
def list_proposals(ctx: Context):
    """
    Gets proposals
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    with context.progress_status("Getting proposals..."):
        try:
            proposals = client.query_map_proposals()
        except IndexError:
            context.info("No proposals found.")
            return

    for proposal_id, batch_proposal in proposals.items():
        print_table_from_plain_dict(batch_proposal, [f"Proposal id: {proposal_id}", "Params"], context.console)
            


@network_app.command()
def propose_globally(
    ctx: Context,
    key: str,
    max_allowed_modules: int = typer.Option(None),
    max_registrations_per_block: int = typer.Option(None),
    target_registrations_interval: int = typer.Option(None),
    target_registrations_per_interval: int = typer.Option(None),
    unit_emission: int = typer.Option(None),
    tx_rate_limit: int = typer.Option(None),
    vote_threshold: int = typer.Option(None),
    vote_mode: str = typer.Option(None),
    max_proposals: int = typer.Option(None),
    max_name_length: int = typer.Option(None),
    burn_rate: int = typer.Option(None),
    min_burn: int = typer.Option(None),
    max_burn: int = typer.Option(None),
    burn: int = typer.Option(None),
    min_stake: int = typer.Option(None),
    min_weight_stake: int = typer.Option(None),
    adjustment_alpha: int = typer.Option(None),
    floor_delegation_fee: int = typer.Option(None),
    max_allowed_subnets: int = typer.Option(None),
):
    provided_params = locals().copy()
    provided_params.pop("ctx")
    provided_params.pop("key")
    provided_params = {key: value for key, value in provided_params.items() if value is not None}
    """
    Adds a global proposal to the network.
    """
    context = make_custom_context(ctx)
    resolved_key = classic_load_key(key)
    client = context.com_client()
    
    provided_params = check_type(provided_params, NetworkParams)
    global_params = get_global_params(client)
    global_params.update(provided_params)

    with context.progress_status("Adding a proposal..."):
        client.add_global_proposal(resolved_key, global_params)


# ! THESE ARE BETA COMMANDS (might not have full substrate support)


@network_app.command()
def propose_on_subnet(
    ctx: Context,
    key: str,
    name: str,
    founder: str,
    founder_share: int,
    immunity_period: int,
    incentive_ratio: int,
    max_allowed_uids: int,
    max_allowed_weights: int,
    min_allowed_weights: int,
    max_stake: int,
    min_stake: int,
    tempo: int,
    trust_ratio: int,
    vote_mode: str,
    max_weight_age: int,
):
    """
    Adds a proposal to a specific subnet.
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    resolve_founder = resolve_key_ss58(founder)
    resolved_key = classic_load_key(key)

    proposal: SubnetParams = {
        "name": name,
        "founder": resolve_founder,
        "founder_share": founder_share,
        "immunity_period": immunity_period,
        "incentive_ratio": incentive_ratio,
        "max_allowed_uids": max_allowed_uids,
        "max_allowed_weights": max_allowed_weights,
        "min_allowed_weights": min_allowed_weights,
        "max_stake": max_stake,
        "min_stake": min_stake,
        "tempo": tempo,
        "trust_ratio": trust_ratio,
        "vote_mode": vote_mode,
        "max_weight_age": max_weight_age,
    }

    with context.progress_status("Adding a proposal..."):
        client.add_subnet_proposal(resolved_key, proposal)


def get_valid_voting_keys(client: CommuneClient, proposal: dict[str, Any]) -> dict[str, int]:
    if proposal.get('SubnetParams'):
        proposal_netuid = proposal["SubnetParams"]["netuid"]
        keys_stake = local_keys_to_stakedbalance(client, proposal_netuid)
    else:
        keys_stake: dict[str, int] = {}
        subnets = client.query_map_subnet_names()
        for netuid in track(subnets.keys(), description="Checking valid keys..."):
            subnet_stake = local_keys_to_stakedbalance(client, netuid)
            keys_stake = {
                key: keys_stake.get(key, 0) + subnet_stake.get(key, 0) 
                for key in set(keys_stake) | set(subnet_stake)
                }
    keys_stake = {key: stake for key, stake in keys_stake.items() if stake >= 5}
    return keys_stake

@network_app.command()
def vote_proposal(
    ctx: Context, 
    key: str,
    proposal_id: int, 
    agree: bool = typer.Option(True, "--disagree"),
    all_keys: bool = typer.Option(False, "--all-keys")
    ):

    """
    Casts a vote on a specified proposal.
    """
    context = make_custom_context(ctx)
    client = context.com_client()
    proposals = client.query_map_proposals()
    proposal = proposals[proposal_id]
    keys_stake = get_valid_voting_keys(client, proposal) if all_keys else {key: None}


    for key in track(keys_stake.keys(), description="Voting..."):
        resolved_key = classic_load_key(key)
        try:
            client.vote_on_proposal(resolved_key, proposal_id, agree)
        except Exception as e:
            print(f"Error while voting with key {key}: ", e)
            print("Skipping...")
            continue


@network_app.command()
def unvote_proposal(ctx: Context, key: str, proposal_id: int):
    """
    Retracts a previously cast vote on a specified proposal.
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    resolved_key = classic_load_key(key)
    with context.progress_status(f"Unvoting on a proposal {proposal_id}..."):
        client.unvote_on_proposal(resolved_key, proposal_id)

@network_app.command()
def add_custom_proposal(
    ctx: Context,
    key: str,
    data: str
):
    """
    Adds a proposal to a specific subnet.
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    # _ = resolve_key_ss58(founder)
    resolved_key = classic_load_key(key)

    proposal = {
        "data": data
    }
    
    with context.progress_status("Adding a proposal..."):
        client.add_custom_proposal(resolved_key, proposal)