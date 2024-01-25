from typing import Any

from cexpl.types import ModuleWithOptionalBalance
from communex.client import CommuneClient
from communex.key import check_ss58_address
from communex.raw_ws_ops import query_batch, query_batch_map
from communex.types import NetworkParams, Ss58Address, SubnetParamsWithEmission
from communex.compat.key import local_key_addresses


def get_map_modules(
    client: CommuneClient,
    netuid: int = 0,
    include_balances: bool = False,
) -> dict[str, ModuleWithOptionalBalance]:
    """
    Gets all modules info on the network
    """
    with client.get_conn() as substrate:

        request_dict: dict[Any, Any] = {
            "SubspaceModule": [
                ("StakeFrom", [netuid]),
                ("Keys", [netuid]),
                ("Name", [netuid]),
                ("Address", [netuid]),
                ("RegistrationBlock", [netuid]),
                ('DelegationFee', [netuid]),
                ('Emission', []),
                ('Incentive', []),
                ("Dividends", []),
                ('LastUpdate', []),
            ],
        }
    if include_balances:
        request_dict["System"] = [("Account", [])]

    bulk_query = query_batch_map(substrate, request_dict)
    ss58_to_stakefrom, uid_to_key, uid_to_name, uid_to_address, uid_to_regblock, \
        ss58_to_delegationfee, uid_to_emission, uid_to_incentive, uid_to_dividend, \
        uid_to_lastupdate, ss58_to_balances = (
            bulk_query["StakeFrom"],
            bulk_query["Keys"],
            bulk_query["Name"],
            bulk_query["Address"],
            bulk_query["RegistrationBlock"],
            bulk_query["DelegationFee"],
            bulk_query["Emission"],
            bulk_query["Incentive"],
            bulk_query["Dividends"],
            bulk_query["LastUpdate"],
            bulk_query.get("Account", None),
        )

    result_modules: dict[str, ModuleWithOptionalBalance] = {}

    for uid, key in uid_to_key.items():
        key = check_ss58_address(key)

        name = uid_to_name[uid]
        address = uid_to_address[uid]
        emission = uid_to_emission[netuid][uid]
        incentive = uid_to_incentive[netuid][uid]
        dividend = uid_to_dividend[netuid][uid]
        regblock = uid_to_regblock[uid]
        stake_from = ss58_to_stakefrom.get(key, [])
        last_update = uid_to_lastupdate[netuid][uid]
        delegation_fee = ss58_to_delegationfee.get(key, 20)  # 20% default delegation fee

        balance = None
        if include_balances and ss58_to_balances is not None:
            balance_dict = ss58_to_balances.get(key, None)
            if balance_dict is not None:
                assert isinstance(balance_dict['data'], dict)
                balance = balance_dict['data']['free']
            else:
                balance = 0
        stake = sum(stake for _, stake in stake_from)

        module: ModuleWithOptionalBalance = {
            "uid": uid,
            "key": key,
            "name": name,
            "address": address,
            "emission": emission,
            "incentive": incentive,
            "dividends": dividend,
            "stake_from": stake_from,
            "regblock": regblock,
            "last_update": last_update,
            "balance": balance,
            "stake": stake,
            "delegation_fee": delegation_fee,
        }

        result_modules[key] = module
    return result_modules


def get_map_subnets_params(
    c_client: CommuneClient,
) -> dict[int, SubnetParamsWithEmission]:
    """
    Gets all subnets info on the network
    """

    with c_client.get_conn() as substrate:
        bulk_query = query_batch_map(substrate,
                                     {
                                         "SubspaceModule": [
                                             ("ImmunityPeriod", []),
                                             ("MinAllowedWeights", []),
                                             ("MaxAllowedWeights", []),
                                             ('MinStake', []),
                                             ("Emission", []),
                                             ('MaxStake', []),
                                             ("Tempo", []),
                                             ("MaxAllowedUids", []),
                                             ('Founder', []),
                                             ("FounderShare", []),
                                             ('IncentiveRatio', []),
                                             ('TrustRatio', []),
                                             ('VoteThresholdSubnet', []),
                                             ('VoteModeSubnet', []),
                                             ('SelfVote', []),
                                             ('SubnetNames', []),
                                             ('MaxWeightAge', [])
                                         ],
                                     }
                                     )

        (
            netuid_to_emission, netuid_to_tempo, netuid_to_immunity_period,
            netuid_to_min_allowed_weights, netuid_to_max_allowed_weights,
            netuid_to_max_allowed_uids, netuid_to_min_stake,
            netuid_to_max_stake, netuid_to_founder, netuid_to_founder_share,
            netuid_to_incentive_ratio, netuid_to_trust_ratio,
            netuid_to_vote_treshold_subnet, netuid_to_vote_mode_subnet,
            netuid_to_self_vote, netuid_to_subnet_names,
            netuid_to_weight_age
        ) = (
            bulk_query["Emission"], bulk_query["Tempo"],
            bulk_query["ImmunityPeriod"], bulk_query["MinAllowedWeights"],
            bulk_query["MaxAllowedWeights"], bulk_query["MaxAllowedUids"],
            bulk_query["MinStake"], bulk_query["MaxStake"],
            bulk_query["Founder"], bulk_query["FounderShare"],
            bulk_query["IncentiveRatio"], bulk_query["TrustRatio"],
            bulk_query["VoteThresholdSubnet"], bulk_query["VoteModeSubnet"],
            bulk_query["SelfVote"], bulk_query["SubnetNames"],
            bulk_query["MaxWeightAge"]
        )

    result_subnets: dict[int, SubnetParamsWithEmission] = {}

    for netuid, name in netuid_to_subnet_names.items():
        name = name
        founder = Ss58Address(netuid_to_founder[netuid])
        founder_share = netuid_to_founder_share[netuid]
        immunity_period = netuid_to_immunity_period[netuid]
        incentive_ratio = netuid_to_incentive_ratio[netuid]
        max_allowed_uids = netuid_to_max_allowed_uids[netuid]
        max_allowed_weights = netuid_to_max_allowed_weights[netuid]
        min_allowed_weights = netuid_to_min_allowed_weights[netuid]
        max_stake = netuid_to_max_stake[netuid]
        min_stake = netuid_to_min_stake[netuid]
        tempo = netuid_to_tempo[netuid]
        self_vote = netuid_to_self_vote[netuid]
        trust_ratio = netuid_to_trust_ratio[netuid]
        vote_mode = netuid_to_vote_mode_subnet[netuid]
        vote_threshold = netuid_to_vote_treshold_subnet[netuid]
        emission = sum(netuid_to_emission[netuid])
        max_weight_age = netuid_to_weight_age[netuid]

        subnet: SubnetParamsWithEmission = {
            "name": name,
            "founder": founder,
            "founder_share": founder_share,
            "immunity_period": immunity_period,
            "incentive_ratio": incentive_ratio,
            "max_allowed_uids": max_allowed_uids,
            "max_allowed_weights": max_allowed_weights,
            "min_allowed_weights": min_allowed_weights,
            "max_stake": max_stake,
            "min_stake": min_stake,
            "tempo": tempo,
            "self_vote": self_vote,
            "trust_ratio": trust_ratio,
            "vote_mode": vote_mode,
            "vote_threshold": vote_threshold,
            "emission": emission,
            "max_weight_age": max_weight_age,
        }

        result_subnets[netuid] = subnet

    return result_subnets


def get_global_params(c_client: CommuneClient) -> NetworkParams:
    """
    Returns global parameters of the whole commune ecosystem
    """

    with c_client.get_conn() as substrate:

        query_all = query_batch(substrate, {
            "SubspaceModule": [
                ("MaxAllowedSubnets", []),
                ("MaxAllowedModules", []),
                ("MaxRegistrationsPerBlock", []),
                ("UnitEmission", []),
                ("TxRateLimit", []),
                ("GlobalVoteThreshold", []),
                ("VoteModeGlobal", []),
                ("MaxProposals", []),
                ("MaxNameLength", []),
                ("BurnRate", []),
                ("MinBurn", []),
                ("MinStake", []),
                ("MinWeightStake", []),
            ],
        })

    global_params: NetworkParams = {
        "max_allowed_subnets": int(query_all["MaxAllowedSubnets"]),
        "max_allowed_modules": int(query_all["MaxAllowedModules"]),
        "max_registrations_per_block": int(query_all["MaxRegistrationsPerBlock"]),
        "unit_emission": int(query_all["UnitEmission"]),
        "tx_rate_limit": int(query_all["TxRateLimit"]),
        "vote_threshold": int(query_all["GlobalVoteThreshold"]),
        "vote_mode": str(query_all["VoteModeGlobal"]),
        "max_proposals": int(query_all["MaxProposals"]),
        "max_name_length": int(query_all["MaxNameLength"]),
        "burn_rate": int(query_all["BurnRate"]),
        "min_burn": int(query_all["MinBurn"]),
        "min_stake": int(query_all["MinStake"]),
        "min_weight_stake": int(query_all["MinWeightStake"]),
    }

    return global_params



def concat_to_local_keys(balance: dict[str, int]) -> dict[str, int]:

    local_key_info: dict[str, Ss58Address] = local_key_addresses()
    key2: dict[str, int] = {key_name: balance.get(key_address, 0)
                            for key_name, key_address in local_key_info.items()}

    return key2


def local_keys_to_freebalance(c_client: CommuneClient) -> dict[str, int]:
    with c_client.get_conn() as substrate:
        query_all = query_batch_map(substrate,
                                    {
                                        "System": [("Account", [])], })
    balance_map = query_all["Account"]

    format_balances: dict[str, int] = {key: value['data']['free']
                                       for key, value in balance_map.items()
                                       if 'data' in value and 'free' in value['data']}

    key2balance: dict[str, int] = concat_to_local_keys(format_balances)

    return key2balance


def local_keys_to_stakedbalance(c_client: CommuneClient, netuid: int = 0) -> dict[str, int]:
    with c_client.get_conn() as substrate:

        query_all = query_batch_map(substrate,
                                    {
                                        "SubspaceModule": [("StakeTo", [netuid])],
                                    })

        staketo_map = query_all["StakeTo"]

        format_stake: dict[str, int] = {
            key: sum(stake for _, stake in value) for key, value in staketo_map.items()}

        key2stake: dict[str, int] = concat_to_local_keys(format_stake)

    return key2stake


def local_keys_allbalance(c_client: CommuneClient, netuid: int = 0) -> tuple[dict[str, int], dict[str, int]]:
    with c_client.get_conn() as substrate:
        query_all = query_batch_map(substrate,
                                    {
                                        "SubspaceModule": [("StakeTo", [netuid])],
                                        "System": [("Account", [])], })
    staketo_map = query_all["StakeTo"]
    balance_map = query_all["Account"]

    format_balances: dict[str, int] = {key: value['data']['free']
                                       for key, value in balance_map.items()
                                       if 'data' in value and 'free' in value['data']}

    key2balance: dict[str, int] = concat_to_local_keys(format_balances)

    format_stake: dict[str, int] = {
        key: sum(stake for _, stake in value) for key, value in staketo_map.items()}

    key2stake: dict[str, int] = concat_to_local_keys(format_stake)

    key2balance = {k: v for k, v in sorted(
        key2balance.items(), key=lambda item: item[1], reverse=True)}

    key2stake = {k: v for k, v in sorted(
        key2stake.items(), key=lambda item: item[1], reverse=True)}

    return key2balance, key2stake
