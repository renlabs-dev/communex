import typer
from typer import Context
from rich.progress import track


from communex.cli._common import make_custom_context, print_table_from_plain_dict
from communex.compat.key import classic_load_key, resolve_key_ss58
from communex.misc import get_global_params, local_keys_to_stakedbalance
from communex.types import NetworkParams, SubnetParams


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
    max_allowed_subnets: int,
    max_allowed_modules: int,
    max_registrations_per_block: int,
    target_registrations_interval: int,
    target_registrations_per_interval: int,
    unit_emission: int,
    tx_rate_limit: int,
    vote_threshold: int,
    vote_mode: str,
    max_proposals: int,
    max_name_length: int,
    burn_rate: int,
    min_burn: int,
    max_burn: int,
    burn: int,
    min_stake: int,
    min_weight_stake: int,
    adjustment_alpha: int,
    floor_delegation_fee: int,
):
    """
    Adds a global proposal to the network.
    """
    context = make_custom_context(ctx)
    client = context.com_client()

    resolved_key = classic_load_key(key)

    proposal: NetworkParams = {
        "max_allowed_subnets": max_allowed_subnets,
        "max_allowed_modules": max_allowed_modules,
        "max_registrations_per_block": max_registrations_per_block,
        "target_registrations_interval": target_registrations_interval,
        "target_registrations_per_interval": target_registrations_per_interval,
        "unit_emission": unit_emission,
        "tx_rate_limit": tx_rate_limit,
        "vote_threshold": vote_threshold,
        "vote_mode": vote_mode,
        "max_proposals": max_proposals,
        "max_name_length": max_name_length,
        "burn_rate": burn_rate,
        "min_burn": min_burn,
        "max_burn": max_burn,
        "burn": burn,
        "min_stake": min_stake,
        "min_weight_stake": min_weight_stake,
        "adjustment_alpha": adjustment_alpha,
        "floor_delegation_fee": floor_delegation_fee,
    }

    with context.progress_status("Adding a proposal..."):
        client.add_global_proposal(resolved_key, proposal)


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
    if proposal.get('SubnetParams'):
        proposal_netuid = proposal["SubnetParams"]["netuid"]
    proposal_netuid = 0

    keys_stake = local_keys_to_stakedbalance(client, proposal_netuid) if all_keys else {key: 5}
    keys_stake = {key: stake for key, stake in keys_stake.items() if stake >= 5}

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