# from threading import Lock
import binascii
import hashlib
import math
import multiprocessing
import multiprocessing.queues
import multiprocessing.synchronize
import os
import random
import threading
from abc import abstractmethod
from dataclasses import dataclass
from queue import Empty
from time import sleep
from typing import Generic, Optional, TypeVar, cast

from Crypto.Hash import keccak
from substrateinterface import Keypair

from communex.client import CommuneClient
from communex.util.mutex import MutexBox

SEAL_LIMIT = 2**256 - 1  # U256_MAX
DIFFICULTY = 1_000_000


T = TypeVar("T")


@dataclass
class BlockInfo:
    block_number: int
    curr_block: bytes
    old_block: int | None
    new_info: bool = False
    block_hash: str | None = None


class GenericQueue(Generic[T]):
    # SUPER HUGE GAMBIARRA, but needed for typing without driving me crazy
    """A generic queue class that wraps the multiprocessing.Queue.

    This class provides a type-safe interface for putting and getting items from
    a multiprocessing.Queue. It supports blocking and non-blocking operations.

    Attributes:
        _queue: The underlying multiprocessing.Queue instance.

    Args:
        Generic[T]: The type parameter specifying the type of items in the queue.
    """

    def __init__(self):
        self._queue = multiprocessing.Queue()  # type: ignore

    def put(
        self, item: T, block: bool = True, timeout: float | None = None
    ) -> None:
        self._queue.put(item, block, timeout)  # type: ignore

    def get(self, block: bool = True, timeout: float | None = None) -> T | None:
        return self._queue.get(block, timeout)  # type: ignore

    def __getattr__(self, name: str):
        return getattr(self._queue, name)  # type: ignore

    def put_nowait(self, item: T):
        self._queue.put_nowait(item)  # type: ignore


def _terminate_workers_and_wait_for_exit(
    workers: list[multiprocessing.Process],
) -> None:
    """Terminates the worker processes and waits for them to exit.

    This function is used to gracefully terminate a list of worker processes
    and wait for them to exit.

    Args:
        workers: A list of multiprocessing.Process instances representing the worker processes.

    Returns:
        None
    """
    for worker in workers:
        worker.terminate()
        worker.join()


@dataclass
class POWSolution:
    """A solution to the registration PoW problem."""

    nonce: int
    block_number: int
    seal: bytes
    block_hash: str

    def is_stale(self, current_block: int) -> bool:
        """
        Returns True if the POW is stale.
        This means the block the POW is solved for is within 3 blocks of the current block.
        """
        return self.block_number < current_block - 3


class _SolverBase(multiprocessing.Process):
    """
    Base class for solver processes.

    This abstract class provides a base implementation for solver processes
    that solve proof-of-work (POW) problems. It inherits from multiprocessing.Process
    and defines common attributes and methods used by solver processes.

    Attributes:
        proc_num: The unique identifier of the solver process.
        num_proc: The total number of solver processes.
        update_interval: The interval at which the solver process updates its progress.
        solution_queue: A queue to store the found solutions.
        newBlockEvent: An event to signal the arrival of a new block.
        block_info_box: A synchronization primitive to access block information.
        stopEvent: An event to signal the solver process to stop.
        limit: The maximum number of solutions to find.
        key: The keypair used for generating solutions.

    Args:
        proc_num: The unique identifier of the solver process.
        num_proc: The total number of solver processes.
        update_interval: The interval at which the solver process updates its progress.
        solution_queue: A queue to store the found solutions.
        stopEvent: An event to signal the solver process to stop.
        block_info_box: A synchronization primitive to access block information.
        limit: The maximum number of solutions to find.
        key: The keypair used for generating solutions.
    """

    def __init__(
        self,
        proc_num: int,
        num_proc: int,
        update_interval: int,
        solution_queue: GenericQueue[POWSolution],
        stopEvent: multiprocessing.synchronize.Event,
        block_info_box: MutexBox[BlockInfo],
        limit: int,
        key: Keypair,
        node_url: str,
    ):
        """
        Initializes a new instance of the _SolverBase class.

        Args:
            proc_num: The unique identifier of the solver process.
            num_proc: The total number of solver processes.
            update_interval: The interval at which the solver process updates its progress.
            solution_queue: A queue to store the found solutions.
            stopEvent: An event to signal the solver process to stop.
            block_info_box: A synchronization primitive to access block information.
            limit: The maximum number of solutions to find.
            key: The keypair used for generating solutions.
        """
        multiprocessing.Process.__init__(self, daemon=True)
        self.proc_num = proc_num
        self.num_proc = num_proc
        self.update_interval = update_interval
        self.solution_queue = solution_queue
        self.newBlockEvent = multiprocessing.Event()  # type: ignore
        self.newBlockEvent.clear()
        self.block_info_box = block_info_box
        self.stopEvent = stopEvent
        self.limit = limit
        self.key = key
        self.node_url = node_url

    @abstractmethod
    def run(self) -> None:
        """
        Abstract method to be implemented by derived classes.

        This method contains the main logic of the solver process.

        Raises:
            NotImplementedError: If the method is not implemented in the derived class.
        """
        raise NotImplementedError("_SolverBase is an abstract class")


def unbox_block_info(block_info_box: MutexBox[BlockInfo]):
    """
    Unboxes the block information from the MutexBox.

    This function retrieves the block information from the MutexBox in a blocking manner.

    Args:
        block_info_box: A MutexBox containing the block information.

    Returns:
        A tuple containing the block number, block and key hash bytes, and block hash.
    """
    with block_info_box as block_info:
        block_number = block_info.block_number
        block_and_key_hash_bytes = bytes(block_info.curr_block)  # type: ignore
        block_hash = block_info.block_hash
        block_info.new_info = False
    return block_number, block_and_key_hash_bytes, block_hash


class _Solver(_SolverBase):
    """Solver class that extends _SolverBase.

    This class implements the actual solver logic by overriding the run method.
    """

    def run(self):
        """
        Main solver logic.

        This method runs the solver process, continuously solving for nonce blocks
        until the stop event is set.

        The solver retrieves block information from the block_info_box, updates the
        current block information in a separate thread, and solves for nonce blocks
        within a specified range. If a solution is found, it is put into the solution
        queue.
        """
        block_number: int
        nonce_limit = int(math.pow(2, 64)) - 1
        solution = None
        node = self.node_url
        client = CommuneClient(node)
        block_info_box = self.block_info_box

        self.c_client = client
        block_number, block_and_key_hash_bytes, block_hash = unbox_block_info(
            block_info_box
        )

        _ = threading.Thread(
            target=_update_curr_block_worker,
            args=(block_info_box, self.c_client, self.key.public_key),
        ).start()
        # Start at random nonce
        nonce_start = random.randint(0, nonce_limit)
        nonce_end = nonce_start + self.update_interval
        while not self.stopEvent.is_set():
            # Do a block of nonces

            with block_info_box as block_info:
                if block_info.new_info:
                    (block_number, block_and_key_hash_bytes, block_hash) = (
                        unbox_block_info(block_info_box)
                    )

            solution = _solve_for_nonce_block(
                nonce_start,
                nonce_end,
                block_and_key_hash_bytes,  # type: ignore
                block_number,  # type: ignore
                block_hash,  # type: ignore
            )

            if solution is not None:
                self.solution_queue.put(solution)
                solution = None

            nonce_start = random.randint(0, nonce_limit)
            nonce_start = nonce_start % nonce_limit
            nonce_end = nonce_start + self.update_interval


def _hash_block_with_key(block_bytes: bytes, key_bytes: bytes) -> bytes:
    """
    Hashes the block with the key using Keccak-256 to get 32 bytes.

    Args:
        block_bytes: The block bytes to be hashed.
        key_bytes: The key bytes to be hashed with the block.

    Returns:
        The 32-byte hash of the block and key.
    """

    kec = keccak.new(digest_bits=256)
    kec = kec.update(bytearray(block_bytes + key_bytes))
    block_and_key_hash_bytes = kec.digest()
    return block_and_key_hash_bytes


def _update_curr_block_worker(
    block_info_box: MutexBox[BlockInfo],
    c_client: CommuneClient,
    key_bytes: bytes,
    sleep_time: int = 16,
):
    """
    Updates the current block information in a separate thread.

    This function continuously retrieves the latest block information from the
    Commune client and updates the block_info_box with the new block number,
    block hash, and block bytes hashed with the key.

    Args:
        block_info_box: A MutexBox containing the block information.
        c_client: The CommuneClient instance used to retrieve block information.
        key_bytes: The key bytes to be hashed with the block.
        sleep_time: The time (in seconds) to sleep between block updates.
    """
    while True:
        new_block = c_client.get_block()
        new_block_number = cast(int, new_block["header"]["number"])  # type: ignore
        new_block_hash = new_block["header"]["hash"]  # type: ignore
        new_block_bytes = bytes.fromhex(new_block_hash[2:])  # type: ignore

        with block_info_box as block_info:
            old_block = block_info.block_number
        if new_block_number == old_block:
            pass
        else:
            with block_info_box as block_info:
                block_info.block_number = new_block_number
                # Hash the block with the key
                block_and_key_hash_bytes = _hash_block_with_key(
                    new_block_bytes, key_bytes
                )
                byte_list = []
                for i in range(32):
                    byte_list: list[int] = []
                    byte = block_and_key_hash_bytes[i]
                    byte_list.append(byte)
                block_info.curr_block = byte_list  # type: ignore
                block_info.new_info = True
        sleep(sleep_time)


def _update_curr_block(
    block_info: BlockInfo,
    c_client: CommuneClient,
    key_bytes: bytes,
):
    """
    Updates the current block information.

    This function retrieves the latest block information from the Commune client
    and updates the block_info object with the new block number, block hash, and
    block bytes hashed with the key.

    Args:
        block_info: The BlockInfo object to be updated.
        c_client: The CommuneClient instance used to retrieve block information.
        key_bytes: The key bytes to be hashed with the block.

    Returns:
        A tuple containing a boolean indicating if the block information was updated
        and the new block number.
    """

    # while True:
    new_block = c_client.get_block()
    new_block_number = cast(int, new_block["header"]["number"])  # type: ignore
    new_block_hash = new_block["header"]["hash"]  # type: ignore
    new_block_bytes = bytes.fromhex(new_block_hash[2:])  # type: ignore

    old_block = block_info.block_number
    if new_block_number == old_block:
        return False, old_block

    block_and_key_hash_bytes = _hash_block_with_key(new_block_bytes, key_bytes)

    byte_list = block_and_key_hash_bytes[:32]
    block_info.block_number = new_block_number
    block_info.curr_block = byte_list
    block_info.block_hash = new_block_hash
    return True, new_block_number


def _hex_bytes_to_u8_list(hex_bytes: bytes):
    """
    Converts hex bytes to a list of unsigned 8-bit integers.

    Args:
        hex_bytes: The hex bytes to be converted.

    Returns:
        A list of unsigned 8-bit integers.
    """
    hex_chunks = [
        int(hex_bytes[i : i + 2], 16) for i in range(0, len(hex_bytes), 2)
    ]
    return hex_chunks


def _create_seal_hash(block_and_key_hash_bytes: bytes, nonce: int) -> bytes:
    """
    Creates the seal hash using the block and key hash bytes and the nonce.

    Args:
        block_and_key_hash_bytes: The hash bytes of the block and key.
        nonce: The nonce value.

    Returns:
        The seal hash as bytes.
    """

    nonce_bytes = binascii.hexlify(nonce.to_bytes(8, "little"))
    pre_seal = nonce_bytes + binascii.hexlify(block_and_key_hash_bytes)[:64]
    seal_sh256 = hashlib.sha256(
        bytearray(_hex_bytes_to_u8_list(pre_seal))
    ).digest()
    kec = keccak.new(digest_bits=256)
    seal = kec.update(seal_sh256).digest()
    return seal


def _seal_meets_difficulty(seal: bytes):
    """
    Checks if the seal meets the required difficulty.

    Args:
        seal: The seal hash as bytes.

    Returns:
        True if the seal meets the difficulty, False otherwise.
    """

    seal_number = int.from_bytes(seal, "big")
    product = seal_number * DIFFICULTY
    return product < SEAL_LIMIT


def _solve_for_nonce_block(
    nonce_start: int,
    nonce_end: int,
    block_and_key_hash_bytes: bytes,
    block_number: int,
    block_hash: str,
) -> POWSolution | None:
    """
    Tries to solve the proof-of-work for a block of nonces.

    This function iterates over a range of nonces and attempts to find a seal
    that meets the required difficulty. If a solution is found, it returns a
    POWSolution object containing the nonce, block number, seal, and block hash.

    Args:
        nonce_start: The starting nonce value.
        nonce_end: The ending nonce value.
        block_and_key_hash_bytes: The hash bytes of the block and key.
        block_number: The block number.
        block_hash: The block hash.

    Returns:
        A POWSolution object if a solution is found, None otherwise.
    """

    for nonce in range(nonce_start, nonce_end):
        seal = _create_seal_hash(block_and_key_hash_bytes, nonce)

        if _seal_meets_difficulty(seal):
            return POWSolution(nonce, block_number, seal, block_hash)

    return None


def get_cpu_count():
    """
    Gets the number of allowed CPU cores for the current process.

    Returns:
        The number of allowed CPU cores.
    """

    try:
        return len(os.sched_getaffinity(0))
    except AttributeError:
        # OSX does not have sched_getaffinity
        count = os.cpu_count()
        count = 1 if count is None else count
        return count


def solve_for_difficulty_fast(
    c_client: CommuneClient,
    key: Keypair,
    node_url: str,
    num_processes: Optional[int] = None,
    update_interval: Optional[int] = None,
):
    """
    Solves the proof-of-work using multiple processes.

    This function creates multiple solver processes to find a solution for the
    proof-of-work. It distributes the work among the processes and waits until
    a solution is found or all processes have finished.

    Args:
        c_client: The CommuneClient instance used to retrieve block information.
        key: The Keypair used for signing.
        num_processes: The number of solver processes to create (default: number of CPU cores).
        update_interval: The interval at which the solvers update their progress (default: 50,000).

    Returns:
        A POWSolution object if a solution is found, None otherwise.
    """

    if num_processes is None:
        # get the number of allowed processes for this process
        num_processes = max(1, get_cpu_count())
    print(f"Running with {num_processes} cores.")
    if update_interval is None:
        update_interval = 50_000

    limit = int(math.pow(2, 256)) - 1

    stopEvent = multiprocessing.Event()
    stopEvent.clear()

    solution_queue: GenericQueue[POWSolution] = GenericQueue[POWSolution]()

    block_info = MutexBox(BlockInfo(-1, b"", None))
    key_bytes = key.public_key
    with block_info as bi:
        _, _ = _update_curr_block(
            bi,
            c_client,
            key_bytes,
        )

    solvers = [
        _Solver(
            i,
            num_processes,
            update_interval,
            solution_queue,
            stopEvent,
            block_info,
            limit,
            key,
            node_url,
        )
        for i in range(num_processes)
    ]

    for worker in solvers:
        worker.start()  # start the solver processes

    solution = None

    while True:
        # Wait until a solver finds a solution
        try:
            solution = solution_queue.get(block=True, timeout=0.25)
            if solution is not None:
                break
        except Empty:
            # No solution found, try again
            pass

    # exited while, solution contains the nonce or wallet is registered
    stopEvent.set()  # stop all other processes
    print("Finished")
    # terminate and wait for all solvers to exit
    _terminate_workers_and_wait_for_exit(solvers)  # type: ignore

    return solution


if __name__ == "__main__":
    import time

    from communex._common import get_node_url
    from communex.compat.key import classic_load_key

    node = get_node_url(use_testnet=True)
    print(node)
    client = CommuneClient(node)
    key = classic_load_key("dev01")
    start_time = time.time()

    solution: POWSolution = solve_for_difficulty_fast(client, key, node)
    print(solution)
    print(f"Took {time.time() - start_time} seconds")
    params = {
        "block_number": solution.block_number,
        "nonce": solution.nonce,
        "work": solution.seal,
    }
    client.compose_call("faucet", params=params, key=key)
