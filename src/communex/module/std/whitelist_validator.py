import time

from substrateinterface import Keypair  # type: ignore

from communex._common import get_node_url
from communex.client import CommuneClient
from communex.compat.key import classic_load_key
from communex.types import Ss58Address

# The netuid of the general subnet.
GENERAL_NETUID = 0


def keys_to_uids(keys: dict[int, Ss58Address], target_keys: list[Ss58Address]) -> list[int]:
    return [k for k, v in keys.items() if v in target_keys]


def validaiton(client: CommuneClient, key: Keypair):
    # Query the modules, nominated by DAO.
    keys = client.query_map_key(netuid=GENERAL_NETUID)
    legit_whitelist = client.query_map(
        "LegitWhitelist", params=[], extract_value=False)["LegitWhitelist"]
    # TODO: test on production query, to verify the format, now I am going to assume it is a dict.
    target_keys = list(legit_whitelist.keys())
    uids_map = keys_to_uids(keys, target_keys)
    # WIP, rigt now assuming same weights
    weights = [1 for _ in uids_map]

    client.vote(key, uids=uids_map, weights=weights, netuid=GENERAL_NETUID)


def main(client: CommuneClient, key: Keypair,):
    while True:
        validaiton(client, key)
        time.sleep(1200)


if __name__ == "__main__":
    client = CommuneClient(get_node_url())
    key = classic_load_key("foo")
    main(client, key)
