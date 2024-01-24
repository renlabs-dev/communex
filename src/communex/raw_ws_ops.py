from typing import Any, TypeVar
from concurrent.futures import ThreadPoolExecutor, as_completed

import json
from substrateinterface import SubstrateInterface  # type: ignore
from substrateinterface.storage import StorageKey  # type: ignore

from communex.errors import NetworkQueryError


T1 = TypeVar("T1")
T2 = TypeVar("T2")


def _send_batch(
        substrate: SubstrateInterface,
        batch_payload: list[Any],
        request_ids: list[int],
        results: list[str | dict[Any, Any]],
        extract_result: bool = True
) -> None:
    """
    Sends a batch of requests to the substrate and collects the results.

    Args:
        substrate: An instance of the substrate interface.
        batch_payload: The payload of the batch request.
        request_ids: A list of request IDs for tracking responses.
        results: A list to store the results of the requests.
        extract_result: Whether to extract the result from the response.
        
    Raises:
        NetworkQueryError: If there is an `error` in the response message.

    Note:
        No explicit return value as results are appended to the provided 'results' list.
    """

    try:
        substrate.websocket.send(json.dumps(batch_payload))  # type: ignore
    except NetworkQueryError:
        pass

    while len(results) < len(request_ids):
        received_messages = json.loads(substrate.websocket.recv())  # type: ignore
        if isinstance(received_messages, dict):
            received_messages: list[dict[Any, Any]] = [received_messages]
        for message in received_messages:
            try:
                if message.get('id') in request_ids:
                    if extract_result:
                        results.append(message['result'])
                    else:
                        results.append(message)
                if 'error' in message:
                    raise NetworkQueryError(message['error'])
            except Exception as e:
                print(e)


def _decode_response(
        response: list[str],
        function_parameters: list[tuple[Any, Any, Any, Any, str]],
        last_keys: list[Any],
        prefix_list: list[Any],
        substrate: SubstrateInterface,
        block_hash: str,
) -> dict[str, dict[Any, Any]]:
    """
    Decodes a response from the substrate interface and organizes the data into a dictionary.

    Args:
        response: A list of encoded responses from a substrate query.
        function_parameters: A list of tuples containing the parameters for each storage function.
        last_keys: A list of the last keys used in the substrate query.
        prefix_list: A list of prefixes used in the substrate query.
        substrate: An instance of the SubstrateInterface class.
        block_hash: The hash of the block to be queried.

    Returns:
        A dictionary where each key is a storage function name and the value is another dictionary. 
        This inner dictionary's key is the decoded key from the response and the value is the corresponding decoded value.

    Raises:
        ValueError: If an unsupported hash type is encountered in the `concat_hash_len` function.

    Example:
        >>> _decode_response(
                response=[...], 
                function_parameters=[...], 
                last_keys=[...], 
                prefix_list=[...],
                substrate=substrate_instance,
                block_hash="0x123..."
            )
        {'storage_function_name': {decoded_key: decoded_value, ...}, ...}
    """

    def concat_hash_len(key_hasher: str) -> int:
        """
        Determines the length of the hash based on the given key hasher type.

        Args:
            key_hasher: The type of key hasher.

        Returns:
            The length of the hash corresponding to the given key hasher type.

        Raises:
            ValueError: If the key hasher type is not supported.

        Example:
            >>> concat_hash_len("Blake2_128Concat")
            16
        """

        if key_hasher == "Blake2_128Concat":
            return 16
        elif key_hasher == "Twox64Concat":
            return 8
        elif key_hasher == "Identity":
            return 0
        else:
            raise ValueError('Unsupported hash type')

    result_dict: dict[str, dict[Any, Any]] = {}
    for res, fun_params_tuple, _, prefix in zip(
        response, function_parameters, last_keys, prefix_list
    ):
        res = res[0]
        changes = res["changes"]  # type: ignore
        value_type, param_types, key_hashers, params, storage_function = fun_params_tuple
        for item in changes:
            # Determine type string
            key_type_string: list[Any] = []
            for n in range(len(params), len(param_types)):
                key_type_string.append(f'[u8; {concat_hash_len(key_hashers[n])}]')
                key_type_string.append(param_types[n])

            item_key_obj = substrate.decode_scale(  # type: ignore
                type_string=f"({', '.join(key_type_string)})",
                scale_bytes='0x' + item[0][len(prefix):],
                return_scale_obj=True,
                block_hash=block_hash
            )
            # strip key_hashers to use as item key
            if len(param_types) - len(params) == 1:
                item_key = item_key_obj.value_object[1]  # type: ignore
            else:
                item_key = tuple(  # type: ignore
                    item_key_obj.value_object[key + 1] for key in range(  # type: ignore
                        len(params), len(param_types) + 1, 2
                    )
                )

            item_value = substrate.decode_scale(  # type: ignore
                type_string=value_type,
                scale_bytes=item[1],
                return_scale_obj=True,
                block_hash=block_hash
            )
            result_dict.setdefault(storage_function, {})
            result_dict[storage_function][item_key.value] = item_value.value  # type: ignore

    return result_dict


def _make_request_smaller(
        batch_request: list[tuple[T1, T2]],
        max_size: int = 9_000_000
) -> list[list[tuple[T1, T2]]]:
    """
    Splits a batch of requests into smaller batches, each not exceeding the specified maximum size.

    Args:
        batch_request: A list of requests to be sent in a batch.
        max_size: Maximum size of each batch in bytes.

    Returns:
        A list of smaller request batches.

    Example:
        >>> _make_request_smaller(batch_request=[('method1', 'params1'), ('method2', 'params2')], max_size=1000)
        [[('method1', 'params1')], [('method2', 'params2')]]
    """

    def estimate_size(request: tuple[T1, T2]):
        """Convert the batch request to a string and measure its length"""
        return len(json.dumps(request))

    # Initialize variables
    result: list[list[tuple[T1, T2]]] = []
    current_batch = []
    current_size = 0

    # Iterate through each request in the batch
    for request in batch_request:
        request_size = estimate_size(request)

        # Check if adding this request exceeds the max size
        if current_size + request_size > max_size:
            # If so, start a new batch
            result.append(current_batch)
            current_batch = [request]
            current_size = request_size
        else:
            # Otherwise, add to the current batch
            current_batch.append(request)
            current_size += request_size

    # Add the last batch if it's not empty
    if current_batch:
        result.append(current_batch)

    return result


def _rpc_request_batch(
        substrate: SubstrateInterface,
        batch_requests: list[tuple[str, list[Any]]],
        max_size: int = 9_000_000,
        extract_result: bool = True
) -> list[str]:
    """
    Sends batch requests to the substrate node using multiple threads and collects the results.

    Args:
        substrate: An instance of the substrate interface.
        batch_requests : A list of requests to be sent in batches.
        max_size: Maximum size of each batch in bytes.
        extract_result: Whether to extract the result from the response message.

    Returns:
        A list of results from the batch requests.

    Example:
        >>> _rpc_request_batch(substrate_instance, [('method1', ['param1']), ('method2', ['param2'])])
        ['result1', 'result2', ...]
    """

    results: list[Any] = []
    smaller_requests = _make_request_smaller(batch_requests, max_size=max_size)
    with ThreadPoolExecutor() as executor:
        futures: list[Any] = []
        for chunk in smaller_requests:
            request_ids: list[int] = []
            batch_payload: list[Any] = []

            for method, params in chunk:
                request_id = substrate.request_id
                substrate.request_id += 1
                request_ids.append(request_id)

                batch_payload.append({
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params,
                    "id": request_id
                })

            futures.append(executor.submit(_send_batch, substrate=substrate,
                                           batch_payload=batch_payload, request_ids=request_ids, results=results, extract_result=extract_result))

        for future in as_completed(futures):
            future.result()
    return results


def _get_lists(
    functions: dict[str, list[tuple[str, list[Any]]]],
    substrate: SubstrateInterface
) -> list[tuple[Any, Any, Any, Any, str]]:
    """
    Generates a list of tuples containing parameters for each storage function based on the given functions and substrate interface.

    Args:
        functions (dict[str, list[query_call]]): A dictionary where keys are storage module names and values are lists of tuples. 
            Each tuple consists of a storage function name and its parameters.
        substrate: An instance of the SubstrateInterface class used to interact with the substrate.

    Returns:
        A list of tuples in the format `(value_type, param_types, key_hashers, params, storage_function)` for each storage function in the given functions.

    Example:
        >>> _get_lists(
                functions={'storage_module': [('storage_function', ['param1', 'param2'])]}, 
                substrate=substrate_instance
            )
        [('value_type', 'param_types', 'key_hashers', ['param1', 'param2'], 'storage_function'), ...]
    """

    function_parameters: list[tuple[Any, Any, Any, Any, str]] = []
    for storage_module, queries in functions.items():
        metadata_pallet = substrate.metadata.get_metadata_pallet(storage_module)  # type: ignore
        for storage_function, params in queries:
            storage_item = metadata_pallet.get_storage_function(storage_function)  # type: ignore
            value_type = storage_item.get_value_type_string()  # type: ignore
            param_types = storage_item.get_params_type_string()  # type: ignore
            key_hashers = storage_item.get_param_hashers()  # type: ignore
            function_parameters.append(
                (value_type, param_types, key_hashers, params, storage_function)  # type: ignore
            )
    return function_parameters


def query_batch(
    substrate: SubstrateInterface,
    functions: dict[str, list[tuple[str, list[Any]]]]
) -> dict[str, str]:
    """
    Executes batch queries on a substrate and returns results in a dictionary format.

    Args:
        substrate: An instance of SubstrateInterface to interact with the substrate.
        functions (dict[str, list[query_call]]): A dictionary mapping module names to lists of query calls (function name and parameters).

    Returns:
        A dictionary where keys are storage function names and values are the query results.

    Raises:
        Exception: If no result is found from the batch queries.

    Example:
        >>> query_batch(substrate_instance, {'module_name': [('function_name', ['param1', 'param2'])]})
        {'function_name': 'query_result', ...}
    """

    result = None
    for module, queries in functions.items():
        storage_keys: list[Any] = []
        for fn, params in queries:
            storage_function = substrate.create_storage_key(  # type: ignore
                pallet=module, storage_function=fn, params=params)
            storage_keys.append(storage_function)

        block_hash = substrate.get_block_hash()
        responses: list[Any] = substrate.query_multi(  # type: ignore
            storage_keys=storage_keys, block_hash=block_hash)

        result: dict[str, str] | None = {}

        for item in responses:
            fun = item[0]
            query = item[1]
            storage_fun = fun.storage_function
            result[storage_fun] = query.value

    if result is None:
        raise Exception("No result")

    return result


def query_batch_map(
    substrate: SubstrateInterface,
    functions: dict[str, list[tuple[str, list[Any]]]]
) -> dict[str, dict[Any, Any]]:
    """
    Queries multiple storage functions using a map batch approach and returns the combined result.

    Args:
        substrate: An instance of SubstrateInterface for substrate interaction.
        functions (dict[str, list[query_call]]): A dictionary mapping module names to lists of query calls.

    Returns:
        The combined result of the map batch query.

    Example:
        >>> query_batch_map(substrate_instance, {'module_name': [('function_name', ['param1', 'param2'])]})
        # Returns the combined result of the map batch query
    """

    block_hash = substrate.get_block_hash()
    substrate.init_runtime(block_hash=block_hash)  # type: ignore

    function_parameters = _get_lists(functions, substrate)
    # it's working for a single module, but the response is weird when we try to query system
    send: list[tuple[str, list[Any]]] = []
    prefix_list: list[Any] = []
    for module, queries in functions.items():
        for function, params in queries:
            storage_key = StorageKey.create_from_storage_function(  # type: ignore
                module, function, params, runtime_config=substrate.runtime_config, metadata=substrate.metadata  # type: ignore
            )

            prefix = storage_key.to_hex()
            prefix_list.append(prefix)
            send.append(("state_getKeys", [prefix, block_hash]))

    responses = _rpc_request_batch(substrate, send)

    built_payload: list[tuple[str, list[Any]]] = []
    last_keys: list[Any] = []
    for result_key in responses:
        last_keys.append(result_key[-1])
        built_payload.append(("state_queryStorageAt", [result_key, block_hash]))
    response = _rpc_request_batch(substrate, built_payload)

    multi_result = _decode_response(
        response,
        function_parameters,
        last_keys,
        prefix_list,
        substrate,
        block_hash
    )
    return multi_result
