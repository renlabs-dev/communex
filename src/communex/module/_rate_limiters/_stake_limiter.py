from asyncio import Lock
from math import ceil, floor
from time import monotonic
from typing import Callable

from communex._common import get_node_url
from communex.balance import to_nano
from communex.client import CommuneClient
from substrateinterface.utils.ss58 import ss58_decode


def keys_to_stakedbalance() -> dict[str, int]:
    url = get_node_url()
    client = CommuneClient(url)
    total_stake: dict[str, int] = {}
    qmap = client.query_map_staketo()
    for key, value in qmap.items():
        key_stake = sum(stake for _, stake in value)
        total_stake.setdefault(key, 0)
        total_stake[key] += key_stake
    return total_stake


def calls_per_epoch(stake: int, multiplier: int = 1) -> float:
    """Gives how many requests per epoch a stake can make"""
    max_ratio = 4
    base_ratio = 89
    if multiplier <= 1 / max_ratio:
        raise ValueError(
            f"Given multiplier {multiplier} would set 0 tokens for all stakes"
        )

    def mult_2(x: int) -> int:
        return x * 2

    if stake < to_nano(10_000):
        return 0
    elif stake < to_nano(500_000):
        return base_ratio * multiplier
    else:
        return mult_2(base_ratio) * multiplier


def build_keys_refill_rate(
    get_refill_rate: Callable[[int], float] = calls_per_epoch,
):
    key_to_stake = keys_to_stakedbalance()
    key_to_ratio = {
        ss58_decode(key): get_refill_rate(stake)
        for key, stake in key_to_stake.items()
    }
    return key_to_ratio


class StakeLimiter:
    def __init__(
        self,
        subnets_whitelist: list[int] | None,
        time_func: Callable[[], float] = monotonic,
        epoch: int = 800,
        get_refill_rate: Callable[[int], float] | None = None,
        max_cache_age: int = 600,
    ):
        self._time = time_func
        if get_refill_rate is None:
            get_refill_rate = calls_per_epoch

        self.refiller_function = get_refill_rate
        self._lock = Lock()

        self.buckets: dict[str, tuple[float, float]] = {}

        self.whitelist = subnets_whitelist
        self.key_ratio = build_keys_refill_rate(
            get_refill_rate=self.refiller_function
        )
        self.key_ratio_age = monotonic()
        self.max_cache_age = max_cache_age

        self.epoch = epoch

    async def _get_key_refresh_ratio(self, key: str) -> float:
        # Every access to key_ratio should pass through here so we
        # can update the cache when its too old.

        if not self.whitelist:
            return 1000
        if monotonic() - self.key_ratio_age > self.max_cache_age:
            self.key_ratio = build_keys_refill_rate(
                get_refill_rate=self.refiller_function,
            )
            self.key_ratio_age = monotonic()
        ratio = self.key_ratio.get(key, 0)
        if ratio == 0:
            return 0
        return ratio / self.epoch

    async def _get_key_ratio_per_epoch(self, key: str) -> float:
        return await self._get_key_refresh_ratio(key) * self.epoch

    async def allow(self, key: str) -> bool:
        if not self.whitelist:
            # basically test mode that disables validation
            return True
        async with self._lock:
            return await self._allow(key)

    async def _allow(self, key: str) -> bool:
        tokens = await self._remaining(key)
        if tokens >= 1:
            self._set_tokens(key, tokens - 1)
            return True
        return False

    def limit(self, key: str) -> int:
        key_rate = self.key_ratio.get(key, 0)
        tokens = max(1, key_rate)
        return int(tokens)

    async def remaining(self, key: str) -> int:
        async with self._lock:
            remaining = await self._remaining(key)
        return floor(remaining)

    async def _remaining(self, key: str) -> float:
        await self._refill(key)
        tokens, _ = self.buckets.get(key, (0, 0))
        return tokens

    async def retry_after(self, key: str) -> int:
        async with self._lock:
            return await self._retry_after(key)

    async def _retry_after(self, key: str) -> int:
        tokens = await self._remaining(key)
        if tokens >= 1:
            return 0
        key_rate = await self._get_key_refresh_ratio(key)
        if key_rate > 0:
            return ceil(1 / key_rate)
        else:
            return self.max_cache_age

    async def _refill(self, key: str) -> None:
        bucket = self.buckets.get(key)
        if bucket is None:  # type: ignore
            await self._fill(key)
            return

        filled_bucket = self.buckets.get(key)
        assert filled_bucket  # type: ignore
        tokens, last_seen = filled_bucket

        key_rate = await self._get_key_refresh_ratio(key)
        new_tokens = floor((monotonic() - last_seen) * key_rate)

        if new_tokens <= 0:
            return

        tokens = min(
            tokens + new_tokens, max(self.key_ratio.values(), default=0)
        )  # sink overflow

        self._set_tokens(
            key, tokens
        )  # has race conditions in multi-threaded environments

    async def _fill(self, key: str) -> None:
        # starts with at least 1 token
        ratio = await self._get_key_ratio_per_epoch(key)
        tokens = max(1, ratio)
        self._set_tokens(key, int(tokens))

    def _set_tokens(self, key: str, tokens: float) -> None:
        self.buckets[key] = (tokens, monotonic())
