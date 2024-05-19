from typing import Callable
from time import monotonic
from math import ceil, floor
from threading import Lock

from keylimiter import KeyLimiter
from substrateinterface.utils.ss58 import ss58_decode # type: ignore

from communex._common import get_node_url
from communex.client import CommuneClient
from communex.balance import to_nano

def local_keys_to_stakedbalance(netuid: list[int]) -> dict[str, int]:
    url = get_node_url()
    client = CommuneClient(url)
    total_stake: dict[str, int] = {}
    for uid in netuid:

        query_all = client.query_batch_map(
            {
                "SubspaceModule": [("StakeFrom", [uid])],
            })

        staketo_map = query_all["StakeFrom"]

        for key, value in staketo_map.items():
            key_stake = sum(stake for _, stake in value)
            if key_stake <= 0:
                print("Zeroed key")
            total_stake.setdefault(key, 0)
            total_stake[key] += key_stake

    return total_stake


def stake_to_ratio(stake: int) -> float:
    if stake < to_nano(10_000):
        return 0
    elif stake < to_nano(100_000):
        return 0.5
    elif stake < to_nano(1_000_000):
        return 1
    else:
        return 2
    

def build_keys_refill_rate(
        netuid: list[int] | None,
        get_refill_rate: Callable[[int], float]=stake_to_ratio
    ):
    if netuid is None:
        empty_dict: dict[str, float] = {}
        return empty_dict
    key_to_stake = local_keys_to_stakedbalance(netuid)
    key_to_ratio = {ss58_decode(key): get_refill_rate(stake) for key, stake in key_to_stake.items()}
    return key_to_ratio


class StakeLimiter(KeyLimiter):
    def __init__(
            self,
            subnets_whitelist: list[int] | None,
            time_func: Callable[[], float]=monotonic,
            epoch: int=800,
            get_refill_rate: Callable[[int], float] | None = None,
            max_cache_age: int = 600,
        ):        
        self._time = time_func
        if get_refill_rate is None:
            get_refill_rate = stake_to_ratio
                
        self.refiller_function = get_refill_rate
        self._lock = Lock()
        
        self.buckets: dict[str, tuple[float, float]] = {}

        self.whitelist = subnets_whitelist
        self.key_ratio = build_keys_refill_rate(
            netuid=subnets_whitelist, get_refill_rate=self.refiller_function
            )
        self.key_ratio_age = monotonic()
        self.max_cache_age = max_cache_age

        self.epoch = epoch
    
    def _get_key_refresh_ratio(self, key: str) -> float:
        # Every access to key_ratio should pass through here so we
        # can update the cache when its too old.
        
        if not self.whitelist:
            return 1000
        if monotonic() - self.key_ratio_age > self.max_cache_age:
            with self._lock:
                self.key_ratio = build_keys_refill_rate(
                    netuid=self.whitelist,
                    get_refill_rate=self.refiller_function,
                )
                self.key_ratio_age = monotonic()
        ratio = self.key_ratio.get(key, 0)
        if ratio == 0:
            return 0
        return ratio/self.epoch

    def _get_key_ratio_per_epoch(self, key: str) -> float:
        return self._get_key_refresh_ratio(key) * self.epoch


    
    def allow(self, key: str) -> bool:
        if not self.whitelist:
            # basically test mode that disables validation
            return True
        with self._lock:
            return self._allow(key)
            
    def _allow(self, key: str) -> bool:
        tokens = self._remaining(key)
        if tokens >= 1:
            self._set_tokens(key, tokens - 1)
            return True
        return False
    
    def limit(self, key: str) -> int:
        key_rate = self.key_ratio.get(key, 0)
        tokens = max(1, key_rate)
        return int(tokens)
    
    def remaining(self, key: str) -> int:
        with self._lock:
            return floor(self._remaining(key))
        
    def _remaining(self, key: str) -> float:
        self._refill(key)
        tokens, _ = self.buckets.get(key, (0, 0))
        return tokens
    
    def retry_after(self, key: str) -> int:
        with self._lock:
            return self._retry_after(key)
            
    def _retry_after(self, key: str) -> int:
            tokens = self._remaining(key)
            if tokens >= 1:
                return 0
            key_rate = self._get_key_refresh_ratio(key)
            assert key_rate > 0
            return ceil(1 / key_rate)
    
    def _refill(self, key: str) -> None:
        bucket = self.buckets.get(key)
        if bucket is None: # type: ignore
            self._fill(key)
            return
        
        filled_bucket = self.buckets.get(key)
        assert filled_bucket # type: ignore
        tokens, last_seen = filled_bucket
        
        key_rate = self._get_key_refresh_ratio(key)
        new_tokens = floor((monotonic() - last_seen) * key_rate)
        
        if new_tokens <= 0:
            return
        
        tokens = min(tokens + new_tokens, max(self.key_ratio.values())) # sink overflow
        
        self._set_tokens(key, tokens) # has race conditions in multi-threaded environments
    
    def _fill(self, key: str) -> None:
        # starts with at least 1 token
        tokens = max(1, self._get_key_ratio_per_epoch(key))
        self._set_tokens(key, int(tokens))
        
    def _set_tokens(self, key: str, tokens: float) -> None:
        self.buckets[key] = (tokens, monotonic())
    
