from typing import NewType, TypedDict


Ss58Address = NewType("Ss58Address", str)


# TODO: replace with dataclasses(?)


class NetworkParams(TypedDict):
    max_allowed_subnets: int
    max_allowed_modules: int
    max_registrations_per_block: int
    unit_emission: int
    tx_rate_limit: int
    vote_threshold: int
    vote_mode: str
    max_proposals: int
    max_name_length: int


class SubnetParams(TypedDict):
    name: str
    founder: Ss58Address
    founder_share: int
    immunity_period: int
    incentive_ratio: int
    max_allowed_uids: int
    max_allowed_weights: int
    min_allowed_weights: int
    max_stake: int
    min_stake: int
    tempo: int
    self_vote: bool
    trust_ratio: int
    vote_mode: str
    vote_threshold: int


class SubnetParamsWithEmission(SubnetParams):
    emission: int
