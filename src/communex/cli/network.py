import re
from typing import Any, Optional, cast

import typer
from rich.progress import track
from typer import Context

import communex.balance as c_balance
from communex.cli._common import (make_custom_context,
                                  print_table_from_plain_dict,
                                  CustomCtx)
from communex.client import CommuneClient
from communex.compat.key import (classic_load_key, local_key_addresses)
from communex.misc import (IPFS_REGEX, get_global_params,
                           local_keys_to_stakedbalance)
from communex.types import NetworkParams
from communex.util import convert_cid_on_proposal

network_app = typer.Typer(no_args_is_help=True)


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
    print_table_from_plain_dict(
        general_params, ["Global params", "Value"], context.console
    )


@network_app.command()
def list_proposals(ctx: Context, query_cid: bool = typer.Option(True)):
    """
    Gets proposals
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    with context.progress_status("Getting proposals..."):
        try:
            proposals = client.query_map_proposals()
            if query_cid:
                proposals = convert_cid_on_proposal(proposals)
        except IndexError:
            context.info("No proposals found.")
            return

    for proposal_id, batch_proposal in proposals.items():
        print_table_from_plain_dict(
            batch_proposal, [
                f"Proposal id: {proposal_id}", "Params"], context.console
        )


@network_app.command()
def propose_globally(
    ctx: Context,
    key: str,
    max_allowed_modules: int = typer.Option(None),
    max_registrations_per_block: int = typer.Option(None),
    target_registrations_interval: int = typer.Option(None),
    target_registrations_per_interval: int = typer.Option(None),
    unit_emission: int = typer.Option(None),
    max_name_length: int = typer.Option(None),
    burn_rate: int = typer.Option(None),
    min_burn: int = typer.Option(None),
    max_burn: int = typer.Option(None),
    min_stake: int = typer.Option(None),
    min_weight_stake: int = typer.Option(None),
    max_allowed_subnets: int = typer.Option(None),
    adjustment_alpha: int = typer.Option(None),
    floor_delegation_fee: int = typer.Option(None),
    max_allowed_weights: int = typer.Option(None),
    curator: str = typer.Option(None),
    proposal_cost: int = typer.Option(None),
    proposal_expiration: int = typer.Option(None),
    proposal_participation_threshold: int = typer.Option(None),
):
    provided_params = locals().copy()
    provided_params.pop("ctx")
    provided_params.pop("key")
    provided_params = {
        key: value for key, value in provided_params.items() if value is not None
    }
    """
    Adds a global proposal to the network.
    """
    context = make_custom_context(ctx)
    resolved_key = classic_load_key(key)
    client = context.com_client()

    provided_params = cast(NetworkParams, provided_params)
    global_params = get_global_params(client)
    global_params.update(provided_params)
    with context.progress_status("Adding a proposal..."):
        client.add_global_proposal(resolved_key, global_params)


def get_valid_voting_keys(
    ctx: CustomCtx,
    client: CommuneClient,
    proposal: dict[str, Any],
) -> dict[str, int]:
    local_keys = local_key_addresses(ctx=ctx, universal_password=None)
    
    if proposal.get("SubnetParams"):
        proposal_netuid = proposal["SubnetParams"]["netuid"]
        assert(isinstance(proposal_netuid, int))
        keys_stake = local_keys_to_stakedbalance(client, local_keys, netuid=proposal_netuid)
    else:
        keys_stake: dict[str, int] = {}
        subnets = client.query_map_subnet_names()
        for netuid in track(subnets.keys(), description="Checking valid keys..."):
            subnet_stake = local_keys_to_stakedbalance(client, local_keys, netuid=netuid)
            keys_stake = {
                key: keys_stake.get(key, 0) + subnet_stake.get(key, 0)
                for key in set(keys_stake) | set(subnet_stake)
            }
    keys_stake = {key: stake for key,
                  stake in keys_stake.items() if stake >= 5}
    return keys_stake


@network_app.command()
def vote_proposal(
    ctx: Context,
    proposal_id: int,
    key: Optional[str] = None,
    agree: bool = typer.Option(True, "--disagree"),
):
    """
    Casts a vote on a specified proposal. Without specifying a key, all keys on disk will be used.
    """
    context = make_custom_context(ctx)
    client = context.com_client()
    proposals = client.query_map_proposals()
    proposal = proposals[proposal_id]

    if key is None:
        context.info("Voting with all keys on disk...")
        keys_stake = get_valid_voting_keys(context, client, proposal)
    else:
        keys_stake = {key: None}

    for voting_key in track(keys_stake.keys(), description="Voting..."):
        resolved_key = classic_load_key(voting_key)
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
def add_custom_proposal(ctx: Context, key: str, cid: str):
    """
    Adds a custom proposal.
    """
    context = make_custom_context(ctx)
    if not re.match(IPFS_REGEX, cid):
        context.error(f"CID provided is invalid: {cid}")
        exit(1)
    client = context.com_client()

    # append the ipfs hash
    ipfs_prefix = "ipfs://"
    cid = ipfs_prefix + cid

    resolved_key = classic_load_key(key)

    with context.progress_status("Adding a proposal..."):
        client.add_custom_proposal(resolved_key, cid)


@network_app.command()
def registration_burn(
    ctx: Context,
    netuid: int,
):
    """
    Appraises the cost of registering a module on the Commune network.
    """

    context = make_custom_context(ctx)
    client = context.com_client()

    burn = client.get_burn(netuid)
    registration_cost = c_balance.from_nano(burn)
    context.info(
        f"The cost to register on a netuid: {netuid} is: {registration_cost} $COMAI"
    )
