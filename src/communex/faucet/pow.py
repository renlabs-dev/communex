import os
from typing import Optional, Any, cast, Generic, TypeVar, Callable, Tuple, List
import math
import random
import multiprocessing
import threading
from multiprocessing.sharedctypes import SynchronizedArray, Synchronized
from threading import Lock
from multiprocessing import Array
from communex.client import CommuneClient
from substrateinterface import Keypair
import time

import binascii
import hashlib
from dataclasses import dataclass
from queue import Empty, Full

from Crypto.Hash import keccak


SEAL_LIMIT = 2 ** 256 - 1 # U256_MAX
DIFFICULTY = 1_000_000



T = TypeVar('T')

def _get_block_with_retry(
    c_client: CommuneClient, netuid: int
) -> Tuple[int, bytes]:
    block_info = c_client.get_block()
    if not block_info:
        raise ValueError("Could not retrieve block info")
    block_hash: str = block_info["header"]["hash"]
    block_number = block_info["header"]["number"]
    return block_number, block_hash


def _terminate_workers_and_wait_for_exit(
    workers: List[multiprocessing.Process],
) -> None:
    for worker in workers:
        worker.terminate()
        worker.join()


class SynchronizedGeneric(Synchronized, Generic[T]): # type: ignore
    @property
    def value(self):
        v = self.value  # type: ignore
        v = cast(T, v)
        return v


class _SolverBase(multiprocessing.Process):
    """
    A process that solves the registration PoW problem.

    Args:
        proc_num: int
            The number of the process being created.
        num_proc: int
            The total number of processes running.
        update_interval: int
            The number of nonces to try to solve before checking for a new block.
        finished_queue: multiprocessing.Queue
            The queue to put the process number when a process finishes each update_interval.
            Used for calculating the average time per update_interval across all processes.
        solution_queue: multiprocessing.Queue
            The queue to put the solution the process has found during the pow solve.
        newBlockEvent: multiprocessing.Event
            The event to set by the main process when a new block is finalized in the network.
            The solver process will check for the event after each update_interval.
            The solver process will get the new block hash and difficulty and start solving for a new nonce.
        stopEvent: multiprocessing.Event
            The event to set by the main process when all the solver processes should stop.
            The solver process will check for the event after each update_interval.
            The solver process will stop when the event is set.
            Used to stop the solver processes when a solution is found.
        curr_block: multiprocessing.Array
            The array containing this process's current block hash.
            The main process will set the array to the new block hash when a new block is finalized in the network.
            The solver process will get the new block hash from this array when newBlockEvent is set.
        curr_block_num: multiprocessing.Value
            The value containing this process's current block number.
            The main process will set the value to the new block number when a new block is finalized in the network.
            The solver process will get the new block number from this value when newBlockEvent is set.
        curr_diff: multiprocessing.Array
            The array containing this process's current difficulty.
            The main process will set the array to the new difficulty when a new block is finalized in the network.
            The solver process will get the new difficulty from this array when newBlockEvent is set.
        check_block: multiprocessing.Lock
            The lock to prevent this process from getting the new block data while the main process is updating the data.
        limit: int
            The limit of the pow solve for a valid solution.
    """

    proc_num: int
    num_proc: int
    update_interval: int
    finished_queue: Any
    solution_queue: Any
    newBlockEvent: threading.Event
    stopEvent: threading.Event
    hotkey_bytes: bytes
    curr_block: SynchronizedArray # type: ignore
    curr_block_num: SynchronizedGeneric[int]
    check_block: Lock
    limit: int

    def __init__(
        self,
        proc_num: int,
        num_proc: int,
        update_interval: int,
        finished_queue,
        solution_queue,
        stopEvent: threading.Event,
        curr_block: SynchronizedArray, # type: ignore
        curr_block_num: SynchronizedGeneric[int],
        check_block: Lock,
        limit: int,
    ):
        multiprocessing.Process.__init__(self, daemon=True)
        self.proc_num = proc_num
        self.num_proc = num_proc
        self.update_interval = update_interval
        self.finished_queue = finished_queue
        self.solution_queue = solution_queue
        self.newBlockEvent = multiprocessing.Event() # type: ignore
        self.newBlockEvent.clear()
        self.curr_block = curr_block
        self.curr_block_num = curr_block_num
        self.check_block = check_block
        self.stopEvent = stopEvent
        self.limit = limit

    def run(self):
        raise NotImplementedError("_SolverBase is an abstract class")

    @staticmethod
    def create_shared_memory() -> tuple[
        Array, SynchronizedGeneric[int] # type: ignore
    ]:
        """Creates shared memory for the solver processes to use."""
        curr_block = multiprocessing.Array("h", 32, lock=True)  # byte array
        curr_block_num: SynchronizedGeneric[int] = multiprocessing.Value("i", 0, lock=True)  # type: ignore

        return curr_block, curr_block_num
    
def _registration_diff_unpack(packed_diff: SynchronizedArray) -> int: # type: ignore
    """Unpacks the packed two 32-bit integers into one 64-bit integer. Little endian."""
    return int(packed_diff[0] << 32 | packed_diff[1]) # type: ignore


class _Solver(_SolverBase):
    def run(self):
        block_number: int
        block_and_hotkey_hash_bytes: bytes
        nonce_limit = int(math.pow(2, 64)) - 1

        # Start at random nonce
        nonce_start = random.randint(0, nonce_limit)
        nonce_end = nonce_start + self.update_interval
        while not self.stopEvent.is_set():
            if self.newBlockEvent.is_set():
                with self.check_block:
                    block_number = self.curr_block_num.value
                    block_and_hotkey_hash_bytes = bytes(self.curr_block) # type: ignore

                self.newBlockEvent.clear()

            # Do a block of nonces
            solution = _solve_for_nonce_block(
                nonce_start,
                nonce_end,
                block_and_hotkey_hash_bytes,
                block_number,
            )
            if solution is not None:
                self.solution_queue.put(solution)

            try:
                # Send time
                self.finished_queue.put_nowait(self.proc_num)
            except Full:
                pass

            nonce_start = random.randint(0, nonce_limit)
            nonce_start = nonce_start % nonce_limit
            nonce_end = nonce_start + self.update_interval


def _hash_block_with_hotkey(block_bytes: bytes, hotkey_bytes: bytes) -> bytes:
    """Hashes the block with the hotkey using Keccak-256 to get 32 bytes"""
    kec = keccak.new(digest_bits=256)
    kec = kec.update(bytearray(block_bytes + hotkey_bytes))
    block_and_hotkey_hash_bytes = kec.digest()
    return block_and_hotkey_hash_bytes


def _registration_diff_pack(diff: int, packed_diff: multiprocessing.Array):
    """Packs the difficulty into two 32-bit integers. Little endian."""
    packed_diff[0] = diff >> 32
    packed_diff[1] = diff & 0xFFFFFFFF  # low 32 bits


def _update_curr_block(
    curr_block: multiprocessing.Array,
    curr_block_num: multiprocessing.Value,
    block_number: int,
    block_bytes: bytes,
    hotkey_bytes: bytes,
    lock: multiprocessing.Lock,
):
    with lock:
        curr_block_num.value = block_number
        # Hash the block with the hotkey
        block_and_hotkey_hash_bytes = _hash_block_with_hotkey(block_bytes, hotkey_bytes)
        for i in range(32):
            curr_block[i] = block_and_hotkey_hash_bytes[i]


def _check_for_newest_block_and_update(
    c_client: CommuneClient,
    netuid: int,
    old_block_number: int,
    hotkey_bytes: bytes,
    curr_block: multiprocessing.Array,
    curr_block_num: multiprocessing.Value,
    update_curr_block: Callable,
    check_block: "multiprocessing.Lock",
    solvers: List[_Solver],
) -> int:
    """
    Checks for a new block and updates the current block information if a new block is found.

    Args:
        subtensor (:obj:`bittensor.subtensor`, `required`):
            The subtensor object to use for getting the current block.
        netuid (:obj:`int`, `required`):
            The netuid to use for retrieving the difficulty.
        old_block_number (:obj:`int`, `required`):
            The old block number to check against.
        hotkey_bytes (:obj:`bytes`, `required`):
            The bytes of the hotkey's pubkey.
        curr_diff (:obj:`multiprocessing.Array`, `required`):
            The current difficulty as a multiprocessing array.
        curr_block (:obj:`multiprocessing.Array`, `required`):
            Where the current block is stored as a multiprocessing array.
        curr_block_num (:obj:`multiprocessing.Value`, `required`):
            Where the current block number is stored as a multiprocessing value.
        update_curr_block (:obj:`Callable`, `required`):
            A function that updates the current block.
        check_block (:obj:`multiprocessing.Lock`, `required`):
            A mp lock that is used to check for a new block.
        solvers (:obj:`List[_Solver]`, `required`):
            A list of solvers to update the current block for.

    Returns:
        (int) The current block number.
    """
    block_number: int = c_client.get_block()["header"]["number"] # type: ignore
    if block_number != old_block_number:
        old_block_number = cast(int, block_number)
        # update block information
        block_number, block_hash = _get_block_with_retry(
            c_client=c_client, netuid=netuid
        )
        block_bytes = bytes.fromhex(block_hash[2:])

        update_curr_block(
            curr_block,
            curr_block_num,
            block_number,
            block_bytes,
            hotkey_bytes,
            check_block,
        )
        # Set new block events for each solver

        for worker in solvers:
            worker.newBlockEvent.set()

    return old_block_number


def _hex_bytes_to_u8_list(hex_bytes: bytes):
    hex_chunks = [int(hex_bytes[i : i + 2], 16) for i in range(0, len(hex_bytes), 2)]
    return hex_chunks


def _create_seal_hash(block_and_hotkey_hash_bytes: bytes, nonce: int) -> bytes:
    nonce_bytes = binascii.hexlify(nonce.to_bytes(8, "little"))
    pre_seal = nonce_bytes + binascii.hexlify(block_and_hotkey_hash_bytes)[:64]
    seal_sh256 = hashlib.sha256(bytearray(_hex_bytes_to_u8_list(pre_seal))).digest()
    kec = keccak.new(digest_bits=256)
    seal = kec.update(seal_sh256).digest()
    return seal

def _seal_meets_difficulty(seal: bytes):
    seal_number = int.from_bytes(seal, "big")
    product = seal_number * DIFFICULTY
    return product < SEAL_LIMIT


@dataclass
class POWSolution:
    """A solution to the registration PoW problem."""

    nonce: int
    block_number: int
    seal: bytes

    def is_stale(self, current_block: int) -> bool:
        """Returns True if the POW is stale.
        This means the block the POW is solved for is within 3 blocks of the current block.
        """
        return self.block_number < current_block - 3


def _solve_for_nonce_block(
    nonce_start: int,
    nonce_end: int,
    block_and_hotkey_hash_bytes: bytes,
    block_number: int,
) -> Optional[POWSolution]:
    """Tries to solve the POW for a block of nonces (nonce_start, nonce_end)"""
    for nonce in range(nonce_start, nonce_end):
        # Create seal.
        seal = _create_seal_hash(block_and_hotkey_hash_bytes, nonce)

        # Check if seal meets difficulty
        if _seal_meets_difficulty(seal):
            # Found a solution, save it.
            return POWSolution(nonce, block_number, seal)

    return None


def get_cpu_count():
    try:
        return len(os.sched_getaffinity(0))
    except AttributeError:
        # OSX does not have sched_getaffinity
        count = os.cpu_count()
        count = 1 if count is None else count
        return count
    



def _solve_for_difficulty_fast(
    c_client: CommuneClient,
    key: Keypair,
    netuid: int,
    num_processes: Optional[int] = None,
    update_interval: Optional[int] = None,
    n_samples: int = 10,
    alpha_: float = 0.80,
):
    """
    Solves the POW for registration using multiprocessing.
    Args:
        subtensor
            Subtensor to connect to for block information and to submit.
        wallet:
            wallet to use for registration.
        netuid: int
            The netuid of the subnet to register to.
        output_in_place: bool
            If true, prints the status in place. Otherwise, prints the status on a new line.
        num_processes: int
            Number of processes to use.
        update_interval: int
            Number of nonces to solve before updating block information.
        n_samples: int
            The number of samples of the hash_rate to keep for the EWMA
        alpha_: float
            The alpha for the EWMA for the hash_rate calculation
        log_verbose: bool
            If true, prints more verbose logging of the registration metrics.
    Note: The hash rate is calculated as an exponentially weighted moving average in order to make the measure more robust.
    Note:
    - We can also modify the update interval to do smaller blocks of work,
        while still updating the block information after a different number of nonces,
        to increase the transparency of the process while still keeping the speed.
    """
    if num_processes is None:
        # get the number of allowed processes for this process
        num_processes: int = min(1, get_cpu_count())

    if update_interval is None:
        update_interval = 50_000

    limit = int(math.pow(2, 256)) - 1

    curr_block, curr_block_num = _Solver.create_shared_memory()

    # Establish communication queues
    ## See the _Solver class for more information on the queues.
    stopEvent = multiprocessing.Event()
    stopEvent.clear()

    solution_queue = multiprocessing.Queue()
    finished_queues = [multiprocessing.Queue() for _ in range(num_processes)]
    check_block = multiprocessing.Lock()

    hotkey_bytes = key.public_key
    # Start consumers
    solvers = [
        _Solver(
            i,
            num_processes,
            update_interval,
            finished_queues[i],
            solution_queue,
            stopEvent,
            curr_block,
            curr_block_num,
            check_block,
            limit,
        )
        for i in range(num_processes)
    ]

    # Get first block
    block = c_client.get_block()
    block_number = cast(int, block["header"]["number"])
    block_hash = cast(str, block["header"]["hash"])
    # block_number, difficulty, block_hash = _get_block_with_retry(
    #     subtensor=subtensor, netuid=netuid
    # )

    block_bytes = bytes.fromhex(block_hash[2:])
    old_block_number = block_number
    # Set to current block
    _update_curr_block(
        curr_block,
        curr_block_num,
        block_number,
        block_bytes,
        hotkey_bytes,
        check_block,
    )

    # Set new block events for each solver to start at the initial block
    for worker in solvers:
        worker.newBlockEvent.set()

    for worker in solvers:
        worker.start()  # start the solver processes
    start_time = time.time()  # time that the registration started
    time_last = start_time  # time that the last work blocks completed

    start_time_perpetual = time.time()

    solution = None

    hash_rates = [0] * n_samples  # The last n true hash_rates
    weights = [alpha_**i for i in range(n_samples)]  # weights decay by alpha

    while True:
        # Wait until a solver finds a solution
        try:
            solution = solution_queue.get(block=True, timeout=0.25)
            if solution is not None:
                break
        except Empty:
            # No solution found, try again
            pass

        # check for new block
        old_block_number = _check_for_newest_block_and_update(
            c_client,
            netuid=netuid,
            hotkey_bytes=hotkey_bytes,
            old_block_number=old_block_number,
            curr_block=curr_block,
            curr_block_num=curr_block_num,
            update_curr_block=_update_curr_block,
            check_block=check_block,
            solvers=solvers,
        )

        num_time = 0
        for finished_queue in finished_queues:
            try:
                proc_num = finished_queue.get(timeout=0.1)
                num_time += 1

            except Empty:
                continue

        time_now = time.time()  # get current time
        time_since_last = time_now - time_last  # get time since last work block(s)
        if num_time > 0 and time_since_last > 0.0:
            # create EWMA of the hash_rate to make measure more robust

            hash_rate_ = (num_time * update_interval) / time_since_last
            hash_rates.append(hash_rate_)
            hash_rates.pop(0)  # remove the 0th data point

            # update time last to now
            time_last = time_now


    # exited while, solution contains the nonce or wallet is registered
    stopEvent.set()  # stop all other processes
    print("Finished")
    # terminate and wait for all solvers to exit
    _terminate_workers_and_wait_for_exit(solvers)

    return solution


if __name__ == "__main__":
    from communex._common import get_node_url
    from communex.compat.key import classic_load_key
    node = get_node_url(use_testnet=True)
    client = CommuneClient(node)
    key = classic_load_key("dev01")
    solution: POWSolution = _solve_for_difficulty_fast(client, key, 0)
    print(solution)
    # params = {"block_number": solution.block_number, "nonce": solution.nonce, "work": solution.seal.hex()}
    # client.compose_call("do_faucet", params=params, key=key)
    #solver = _Solver()