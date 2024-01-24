import queue
from contextlib import contextmanager
from typing import Any

from substrateinterface import (ExtrinsicReceipt, Keypair,  # type: ignore
                                SubstrateInterface)

from communex.errors import ChainTransactionError
from communex.types import NetworkParams, Ss58Address, SubnetParams

# TODO: move within
from communex.raw_ws_ops import query_batch, query_batch_map

# from communex.raw_ws_ops import query_batch, query_batch_map


# TODO: InsufficientBalanceError, MismatchedLengthError etc

class CommuneClient:
    """
    A client for interacting with Commune network nodes, querying storage, 
    submitting transactions, etc.

    Attributes:
        wait_for_finalization: Whether to wait for transaction finalization.

    Example:
    ```py
    client = CommuneClient()
    client.query(name='function_name', params=['param1', 'param2'])
    ```

    Raises:
        AssertionError: If the maximum connections value is less than or equal
          to zero.
    """
    wait_for_finalization: bool
    _num_connections: int
    _connection_queue: queue.Queue[SubstrateInterface]

    def __init__(
            self,
            url: str,
            num_connections: int = 1,
            wait_for_finalization: bool = False,
    ):
        """
        Args:
            url: The URL of the network node to connect to.
            num_connections: The number of websocket connections to be opened.
        """
        assert num_connections > 0
        self._num_connections = num_connections
        self.wait_for_finalization = wait_for_finalization
        self._connection_queue = queue.Queue(num_connections)

        for _ in range(num_connections):
            self._connection_queue.put(SubstrateInterface(url))

    @property
    def connections(self) -> int:
        """
        Gets the maximum allowed number of simultaneous connections to the
        network node.
        """
        return self._num_connections

    @contextmanager
    def get_conn(self, timeout: float | None = None):
        """
        Context manager to get a connection from the pool.

        Tries to get a connection from the pool queue. If the queue is empty,
        it blocks for `timeout` seconds until a connection is available. If
        `timeout` is None, it blocks indefinitely.

        Args:
            timeout: The maximum time in seconds to wait for a connection.

        Yields:
            The connection object from the pool.

        Raises:
            QueueEmptyError: If no connection is available within the timeout
              period.
        """
        conn = self._connection_queue.get(timeout=timeout)
        try:
            yield conn
        finally:
            self._connection_queue.put(conn)

    def query(
        self,
        name: str,
        params: list[Any] = [],
        module: str = 'SubspaceModule',
    ) -> Any:
        """
        Queries a storage function on the network.

        Sends a query to the network and retrieves data from a
        specified storage function.

        Args:
            name: The name of the storage function to query.
            params: The parameters to pass to the storage function.
            module: The module where the storage function is located.

        Returns:
            The result of the query from the network.

        Raises:
            NetworkQueryError: If the query fails or is invalid.
        """

        with self.get_conn() as substrate:
            result = query_batch(substrate, {module: [(name, params)]})

        return result[name]

    def query_map(
        self,
        name: str,
        params: list[Any] = [],
        module: str = 'SubspaceModule',
        extract_value: bool = True,
    ) -> dict[Any, Any]:
        """
        Queries a storage map from a network node.

        Args:
            name: The name of the storage map to query.
            params: A list of parameters for the query.
            module: The module in which the storage map is located.

        Returns:
            A dictionary representing the key-value pairs
              retrieved from the storage map.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        with self.get_conn() as substrate:
            result = query_batch_map(substrate, {module: [(name, params)]})

        if extract_value:
            return {k.value: v.value for k, v in result}  # type: ignore

        return result

    def compose_call(
        self,
        fn: str,
        params: dict[str, Any],
        key: Keypair,
        module: str = 'SubspaceModule',
        wait_for_inclusion: bool = True,
        wait_for_finalization: bool | None = None,
        sudo: bool = False,
    ) -> ExtrinsicReceipt:
        """
        Composes and submits a call to the network node.

        Composes and signs a call with the provided keypair, and submits it to
        the network. The call can be a standard extrinsic or a sudo extrinsic if 
        elevated permissions are required. The method can optionally wait for
        the call's inclusion in a block and/or its finalization.

        Args:
            fn: The function name to call on the network.
            params: A dictionary of parameters for the call.
            key: The keypair for signing the extrinsic.
            module: The module containing the function.
            wait_for_inclusion: Wait for the call's inclusion in a block.
            wait_for_finalization: Wait for the transaction's finalization.
            sudo: Execute the call as a sudo (superuser) operation.

        Returns:
            The receipt of the submitted extrinsic, if
              `wait_for_inclusion` is True. Otherwise, returns a string
              identifier of the extrinsic.

        Raises:
            ChainTransactionError: If the transaction fails.
        """

        with self.get_conn() as substrate:
            if wait_for_finalization is None:
                wait_for_finalization = self.wait_for_finalization

            call = substrate.compose_call(  # type: ignore
                call_module=module,
                call_function=fn,
                call_params=params
            )
            if sudo:
                call = substrate.compose_call(  # type: ignore
                    call_module='Sudo',
                    call_function='sudo',
                    call_params={
                        'call': call.value,  # type: ignore
                    }
                )

            extrinsic = substrate.create_signed_extrinsic(  # type: ignore
                call=call, keypair=key  # type: ignore
            )  # type: ignore
            response = substrate.submit_extrinsic(
                extrinsic=extrinsic,
                wait_for_inclusion=wait_for_inclusion,
                wait_for_finalization=wait_for_finalization,
            )
        if wait_for_inclusion:
            if not response.is_success:
                raise ChainTransactionError(
                    response.error_message, response  # type: ignore
                )

        return response

    def transfer(
            self,
            key: Keypair,
            amount: int,
            dest: Ss58Address,
    ) -> ExtrinsicReceipt:
        """
        Transfers a specified amount of tokens from the signer's account to the
        specified account.

        Args:
            key: The keypair associated with the sender's account.
            amount: The amount to transfer, in nanotokens.
            dest: The SS58 address of the recipient.

        Returns:
            A receipt of the transaction.

        Raises:
            InsufficientBalanceError: If the sender's account does not have
              enough balance.
            ChainTransactionError: If the transaction fails.
        """

        amount = amount - self.get_existential_deposit()

        params = {'dest': dest, 'value': amount}

        return self.compose_call(
            module='Balances',
            fn='transfer',
            params=params,
            key=key
        )

    def transfer_multiple(
        self,
        key: Keypair,
        destinations: list[Ss58Address],
        amounts: list[int],
        netuid: str | int = 0,
    ) -> ExtrinsicReceipt:
        """
        Transfers specified amounts of tokens from the signer's account to
        multiple target accounts.

        The `destinations` and `amounts` lists must be of the same length.

        Args:
            key: The keypair associated with the sender's account.
            destinations: A list of SS58 addresses of the recipients.
            amounts: Amount to transfer to each recipient, in nanotokens.
            netuid: The network identifier.

        Returns:
            A receipt of the transaction.

        Raises:
            InsufficientBalanceError: If the sender's account does not have
              enough balance for all transfers.
            ChainTransactionError: If the transaction fails.
        """

        assert len(destinations) == len(amounts)

        # extract existential deposit from amounts
        amounts = [a - self.get_existential_deposit() for a in amounts]

        params = {
            "netuid": netuid,
            "destinations": destinations,
            "amounts": amounts,
        }

        return self.compose_call(
            module='SubspaceModule',
            fn='transfer_multiple',
            params=params,
            key=key
        )

    def stake(
        self,
        key: Keypair,
        amount: int,
        dest: Ss58Address,
        netuid: int = 0,
    ) -> ExtrinsicReceipt:
        """
        Stakes the specified amount of tokens to a module key address.

        Args:
            key: The keypair associated with the staker's account.
            amount: The amount of tokens to stake, in nanotokens.
            dest: The SS58 address of the module key to stake to.
            netuid: The network identifier.

        Returns:
            A receipt of the staking transaction.

        Raises:
            InsufficientBalanceError: If the staker's account does not have
              enough balance.
            ChainTransactionError: If the transaction fails.
        """

        amount = amount - self.get_existential_deposit()

        params = {
            'amount': amount,
            'netuid': netuid,
            'module_key': dest
        }

        return self.compose_call(fn='add_stake', params=params, key=key)

    def unstake(
        self,
        key: Keypair,
        amount: int,
        dest: Ss58Address,
        netuid: int = 0,
    ) -> ExtrinsicReceipt:
        """
        Unstakes the specified amount of tokens from a module key address.

        Args:
            key: The keypair associated with the unstaker's account.
            amount: The amount of tokens to unstake, in nanotokens.
            dest: The SS58 address of the module key to unstake from.
            netuid: The network identifier.

        Returns:
            A receipt of the unstaking transaction.

        Raises:
            InsufficientStakeError: If the staked key does not have enough
              staked tokens by the signer key.
            ChainTransactionError: If the transaction fails.
        """

        amount = amount - self.get_existential_deposit()

        params = {
            'amount': amount,
            'netuid': netuid,
            'module_key': dest
        }
        return self.compose_call(fn='remove_stake', params=params, key=key)

    def update_module(
        self,
        key: Keypair,
        name: str | None = None,
        address: str | None = None,
        delegation_fee: int = 20,
        netuid: int = 0,
    ) -> ExtrinsicReceipt:
        """
        Updates the parameters of a registered module.

        The delegation fee must be an integer between 0 and 100.

        Args:
            key: The keypair associated with the module's account.
            name: The new name for the module. If None, the name is not updated.
            address: The new address for the module. 
                If None, the address is not updated.
            delegation_fee: The new delegation fee for the module, 
                between 0 and 100.
            netuid: The network identifier.

        Returns:
            A receipt of the module update transaction.

        Raises:
            InvalidParameterError: If the provided parameters are invalid.
            ChainTransactionError: If the transaction fails.
        """

        assert isinstance(delegation_fee, int)

        if not name:
            name = ''
        if not address:
            address = ''
        params = {
            'netuid': netuid,
            'name': name,
            'address': address,
            'delegation_fee': delegation_fee
        }

        response = self.compose_call('update_module', params=params, key=key)

        return response

    def register_module(
        self,
        key: Keypair,
        name: str | None = None,
        address: str | None = None,
        subnet: str = 'commune',
        min_stake: int | None = None,
    ) -> ExtrinsicReceipt:
        """
        Registers a new module in the network.

        Args:
            key: The keypair used for registering the module.
            name: The name of the module. If None, a default or previously 
                set name is used. # How does this work?
            address: The address of the module. If None, a default or 
                previously set address is used. # How does this work?
            subnet: The network subnet to register the module in.
            min_stake: The minimum stake required for the module, in nanotokens. 
                If None, a default value is used.

        Returns:
            A receipt of the registration transaction.

        Raises:
            InvalidParameterError: If the provided parameters are invalid.
            ChainTransactionError: If the transaction fails.
        """

        stake = self.get_min_stake() if min_stake is None else min_stake

        key_addr = key.ss58_address

        params = {
            'network': subnet,
            'address': address,
            'name': name,
            'stake': stake,
            'module_key': key_addr
        }
        response = self.compose_call('register', params=params, key=key)
        return response

    def vote(
        self,
        key: Keypair,
        uids: list[int],
        weights: list[int],
        netuid: int = 0,
    ) -> ExtrinsicReceipt:
        """
        Casts votes on a list of module UIDs with corresponding weights.

        The length of the UIDs list and the weights list should be the same.
        Each weight corresponds to the UID at the same index.

        Args:
            key: The keypair used for signing the vote transaction.
            uids: A list of module UIDs to vote on.
            weights: A list of weights corresponding to each UID.
            netuid: The network identifier.

        Returns:
            A receipt of the voting transaction.

        Raises:
            InvalidParameterError: If the lengths of UIDs and weights lists
                do not match.
            ChainTransactionError: If the transaction fails.
        """

        assert len(uids) == len(weights)

        params = {
            'uids': uids,
            'weights': weights,
            'netuid': netuid,
        }

        response = self.compose_call('set_weights', params=params, key=key)

        return response

    def update_subnet(
        self,
        key: Keypair,
        params: SubnetParams,
        netuid: int = 0,
    ) -> ExtrinsicReceipt:
        """
        Update a subnet's configuration.

        It requires the founder key for authorization. 

        Args:
            key: The founder keypair of the subnet.
            params: The new parameters for the subnet.
            netuid: The network identifier.

        Returns:
            A receipt of the subnet update transaction.

        Raises:
            AuthorizationError: If the key is not authorized.
            ChainTransactionError: If the transaction fails.
        """

        general_params = dict(params)
        general_params['netuid'] = netuid

        response = self.compose_call(
            fn='update_subnet',
            params=general_params,
            key=key,
        )

        return response

    def transfer_stake(
            self,
            key: Keypair,
            amount: int,
            from_module_key: Ss58Address,
            dest_module_address: Ss58Address,
            netuid: int = 0,
    ) -> ExtrinsicReceipt:
        """
        Realocate staked tokens from one staked module to another module.

        Args:
            key: The keypair associated with the account that is delegating the tokens.
            amount: The amount of staked tokens to transfer, in nanotokens.
            from_module_key: The SS58 address of the module you want to transfer from (currently delegated by the key).
            dest_module_address: The SS58 address of the destination (newly delegated key).
            netuid: The network identifier.

        Returns:
            A receipt of the stake transfer transaction.

        Raises:
            InsufficientStakeError: If the source module key does not have
            enough staked tokens. ChainTransactionError: If the transaction
            fails.
        """

        amount = amount - self.get_existential_deposit()

        params = {
            'amount': amount,
            'netuid': netuid,
            'module_key': from_module_key,
            'new_module_key': dest_module_address,
        }

        response = self.compose_call('transfer_stake', key=key, params=params)

        return response

    def multiunstake(
        self,
        key: Keypair,
        keys: list[Ss58Address],
        amounts: list[int],
        netuid: int = 0,
    ) -> ExtrinsicReceipt:
        """
        Unstakes tokens from multiple module keys.

        And the lists `keys` and `amounts` must be of the same length. Each
        amount corresponds to the module key at the same index.

        Args:
            key: The keypair associated with the unstaker's account.
            keys: A list of SS58 addresses of the module keys to unstake from.
            amounts: A list of amounts to unstake from each module key, 
              in nanotokens.
            netuid: The network identifier.

        Returns:
            A receipt of the multi-unstaking transaction.

        Raises:
            MismatchedLengthError: If the lengths of keys and amounts lists do
            not match. InsufficientStakeError: If any of the module keys do not
            have enough staked tokens. ChainTransactionError: If the transaction
            fails.
        """

        assert len(keys) == len(amounts)

        # extract existential deposit from amounts
        amounts = [a - self.get_existential_deposit() for a in amounts]

        params = {
            "netuid": netuid,
            "module_keys": keys,
            "amounts": amounts
        }

        response = self.compose_call(
            'remove_stake_multiple',
            params=params, key=key
        )

        return response

    def multistake(
        self,
        key: Keypair,
        keys: list[Ss58Address],
        amounts: list[int],
        netuid: int = 0,
    ) -> ExtrinsicReceipt:
        """
        Stakes tokens to multiple module keys.

        The lengths of the `keys` and `amounts` lists must be the same. Each
        amount corresponds to the module key at the same index.

        Args:
            key: The keypair associated with the staker's account.
            keys: A list of SS58 addresses of the module keys to stake to.
            amounts: A list of amounts to stake to each module key, 
                in nanotokens.
            netuid: The network identifier.

        Returns:
            A receipt of the multi-staking transaction.

        Raises:
            MismatchedLengthError: If the lengths of keys and amounts lists 
                do not match.
            ChainTransactionError: If the transaction fails.
        """

        assert len(keys) == len(amounts)

        params = {
            'module_keys': keys,
            'amounts': amounts,
            'netuid': netuid,
        }

        response = self.compose_call(
            'add_stake_multiple', params=params, key=key
        )

        return response

    def add_profit_shares(
        self,
        key: Keypair,
        keys: list[Ss58Address],
        shares: list[int],
    ) -> ExtrinsicReceipt:
        """
        Allocates profit shares to multiple keys.

        The lists `keys` and `shares` must be of the same length,
        with each share amount corresponding to the key at the same index.

        Args:
            key: The keypair associated with the account 
                distributing the shares.
            keys: A list of SS58 addresses to allocate shares to.
            shares: A list of share amounts to allocate to each key, 
                in nanotokens.

        Returns:
            A receipt of the profit sharing transaction.

        Raises:
            MismatchedLengthError: If the lengths of keys and shares 
                lists do not match.
            ChainTransactionError: If the transaction fails.
        """

        assert len(keys) == len(shares)

        params = {
            'keys': keys,
            'shares': shares
        }

        response = self.compose_call(
            'add_profit_shares',
            params=params, key=key
        )

        return response

    def add_subnet_proposal(self,
                            key: Keypair,
                            params: SubnetParams,
                            netuid: int = 0
                            ) -> ExtrinsicReceipt:
        """
        Submits a proposal for creating or modifying a subnet within the
        network.

        The proposal includes various parameters like the name, founder, share
        allocations, and other subnet-specific settings.

        Args:
            key: The keypair used for signing the proposal transaction.
            params: The parameters for the subnet proposal.
            netuid: The network identifier.

        Returns:
            A receipt of the subnet proposal transaction.

        Raises:
            InvalidParameterError: If the provided subnet 
                parameters are invalid.
            ChainTransactionError: If the transaction fails.
        """

        general_params = dict(params)
        general_params['netuid'] = netuid

        response = self.compose_call(fn='add_subnet_proposal',
                                     params=general_params,
                                     key=key,)

        return response

    def add_global_proposal(self,
                            key: Keypair,
                            params: NetworkParams,
                            ) -> ExtrinsicReceipt:
        """
        Submits a proposal for altering the global network parameters.

        Allows for the submission of a proposal to 
        change various global parameters
        of the network, such as emission rates, rate limits, and voting 
        thresholds. It is used to
        suggest changes that affect the entire network's operation.

        Args:
            key: The keypair used for signing the proposal transaction.
            params: A dictionary containing global network parameters 
                    like maximum allowed subnets, modules,
                    transaction rate limits, and others.

        Returns:
            A receipt of the global proposal transaction.

        Raises:
            InvalidParameterError: If the provided network 
                parameters are invalid.
            ChainTransactionError: If the transaction fails.
        """

        general_params = dict(params)
        response = self.compose_call(fn='add_global_proposal',
                                     params=general_params,
                                     key=key,)

        return response

    def vote_on_proposal(self,
                         key: Keypair,
                         proposal_id: int,
                         ) -> ExtrinsicReceipt:
        """
        Casts a vote on a specified proposal within the network.

        Args:
            key: The keypair used for signing the vote transaction.
            proposal_id: The unique identifier of the proposal to vote on.

        Returns:
            A receipt of the voting transaction in nanotokens.

        Raises:
            InvalidProposalIDError: If the provided proposal ID does not 
                exist or is invalid.
            ChainTransactionError: If the transaction fails.
        """

        params = {
            'proposal_id': proposal_id
        }

        response = self.compose_call('vote_proposal', key=key, params=params)

        return response

    def unvote_on_proposal(self,
                           key: Keypair,
                           proposal_id: int,
                           ) -> ExtrinsicReceipt:
        """
        Retracts a previously cast vote on a specified proposal.

        Args:
            key: The keypair used for signing the unvote transaction.
            proposal_id: The unique identifier of the proposal to withdraw the 
                vote from.

        Returns:
            A receipt of the unvoting transaction in nanotokens.

        Raises:
            InvalidProposalIDError: If the provided proposal ID does not 
                exist or is invalid.
            ChainTransactionError: If the transaction fails to be processed, or 
                if there was no prior vote to retract.
        """

        params = {
            'proposal_id': proposal_id
        }

        response = self.compose_call('unvote_proposal', key=key, params=params)

        return response

    def query_map_proposals(self) -> dict[int, dict[str, Any]]:
        """
        Retrieves a mappping of proposals from the network.

        Queries the network and returns a mapping of proposal IDs to 
        their respective parameters. 

        Returns:
            A dictionary mapping proposal IDs 
            to dictionaries of their parameters.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map('Proposals',)

    def query_map_key(
            self,
            netuid: int = 0
    ) -> dict[int, Ss58Address]:
        """
        Retrieves a map of keys from the network.

        Fetches a mapping of key UIDs to their associated 
        addresses on the network.
        The query can be targeted at a specific network UID if required.

        Args:
            netuid: The network UID from which to get the keys.

        Returns:
            A dictionary mapping key UIDs to their addresses.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """
        return self.query_map('Keys', [netuid])

    def query_map_address(self, netuid: int = 0) -> dict[int, str]:
        """
        Retrieves a map of key addresses from the network.

        Queries the network for a mapping of key UIDs to their addresses.

        Args:
            netuid: The network UID from which to get the addresses.

        Returns:
            A dictionary mapping key UIDs to their addresses.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map('Address', [netuid])

    def query_map_emission(self) -> dict[int, list[int]]:
        """
        Retrieves a map of emissions for keys on the network.

        Queries the network to get a mapping of 
        key UIDs to their emission values. 

        Returns:
            A dictionary mapping key UIDs to lists of their emission values.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map('Emission',)

    def query_map_incentive(self) -> dict[int, list[int]]:
        """
        Retrieves a mapping of incentives for keys on the network.

        Queries the network and returns a mapping of key UIDs to 
        their respective incentive values.

        Returns:
            A dictionary mapping key UIDs to lists of their incentive values.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map('Incentive',)

    def query_map_dividend(self) -> dict[int, list[int]]:
        """
        Retrieves a mapping of dividends for keys on the network.

        Queries the network for a mapping of key UIDs to 
        their dividend values. 

        Returns:
            A dictionary mapping key UIDs to lists of their dividend values.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map('Dividends',)

    def query_map_regblock(self, netuid: int = 0) -> dict[int, int]:
        """
        Retrieves a mapping of registration blocks for keys on the network.

        Queries the network for a mapping of key UIDs to 
        the blocks where they were registered.

        Args:
            netuid: The network UID from which to get the registration blocks.

        Returns:
            A dictionary mapping key UIDs to their registration blocks.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map('RegistrationBlock', [netuid])

    def query_map_lastupdate(self) -> dict[int, list[int]]:
        """
        Retrieves a mapping of the last update times for keys on the network.

        Queries the network for a mapping of key UIDs to their last update times.

        Returns:
            A dictionary mapping key UIDs to lists of their last update times.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map('LastUpdate',)

    def query_map_stakefrom(self, netuid: int = 0) -> \
            dict[str, list[tuple[str, int]]]:
        """
        Retrieves a mapping of stakes from various sources for keys on the network.

        Queries the network to obtain a mapping of key addresses to the sources 
        and amounts of stakes they have received.

        Args:
            netuid: The network UID from which to get the stakes.

        Returns:
            A dictionary mapping key addresses to lists of tuples 
            (module_key_address, amount).

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map('StakeFrom', [netuid])

    def query_map_staketo(self, netuid: int = 0) -> \
            dict[str, list[tuple[str, int]]]:
        """
        Retrieves a mapping of stakes to destinations for keys on the network.

        Queries the network for a mapping of key addresses to the destinations 
        and amounts of stakes they have made. 

        Args:
            netuid: The network UID from which to get the stakes.

        Returns:
            A dictionary mapping key addresses to lists of tuples 
            (module_key_address, amount).

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map('StakeTo', [netuid])

    def query_map_stake(self, netuid: int = 0) -> dict[str, int]:
        """
        Retrieves a mapping of stakes for keys on the network.

        Queries the network and returns a mapping of key addresses to their 
        respective delegated staked balances amounts.
        The query can be targeted at a specific network UID if required.

        Args:
            netuid: The network UID from which to get the stakes.

        Returns:
            A dictionary mapping key addresses to their stake amounts.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map('Stake', [netuid], extract_value=False)

    def query_map_delegationfee(self, netuid: int = 0) -> dict[str, int]:
        """
        Retrieves a mapping of delegation fees for keys on the network.

        Queries the network to obtain a mapping of key addresses to their 
        respective delegation fees.

        Args:
            netuid: The network UID to filter the delegation fees.

        Returns:
            A dictionary mapping key addresses to their delegation fees.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map('DelegationFee', [netuid])

    def query_map_tempo(self) -> dict[int, int]:
        """
        Retrieves a mapping of tempo settings for the network.

        Queries the network to obtain the tempo (rate of reward distributions) 
        settings for various network subnets. 

        Returns:
            A dictionary mapping network UIDs to their tempo settings.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map("Tempo",)

    def query_map_immunity_period(self) -> dict[int, int]:
        """
        Retrieves a mapping of immunity periods for the network.

        Queries the network for the immunity period settings, 
        which represent the time duration during which modules 
        can not get deregistered. 

        Returns:
            A dictionary mapping network UIDs to their immunity period settings.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map("ImmunityPeriod",)

    def query_map_min_allowed_weights(self) -> dict[int, int]:
        """
        Retrieves a mapping of minimum allowed weights for the network.

        Queries the network to obtain the minimum allowed weights, 
        which are the lowest permissible weight values that can be set by 
        validators. 

        Returns:
            A dictionary mapping network UIDs to 
            their minimum allowed weight values.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map("MinAllowedWeights",)

    def query_map_max_allowed_weights(self) -> dict[int, int]:
        """
        Retrieves a mapping of maximum allowed weights for the network.

        Queries the network for the maximum allowed weights, 
        which are the highest permissible
        weight values that can be set by validators. 

        Returns:
            A dictionary mapping network UIDs to 
            their maximum allowed weight values.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map("MaxAllowedWeights",)

    def query_map_max_allowed_uids(self) -> dict[int, int]:
        """
        Queries the network for the maximum number of allowed user IDs (UIDs) 
        for each network subnet.

        Fetches a mapping of network subnets to their respective 
        limits on the number of user IDs that can be created or used. 

        Returns:
            A dictionary mapping network UIDs (unique identifiers) to their 
            maximum allowed number of UIDs. 
            Each entry represents a network subnet 
            with its corresponding UID limit.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map("MaxAllowedUids",)

    def query_map_min_stake(self) -> dict[int, int]:
        """
        Retrieves a mapping of minimum allowed stake on the network.

        Queries the network to obtain the minimum number of stake, 
        which is represented in nanotokens. 

        Returns:
            A dictionary mapping network UIDs to 
            their minimum allowed stake values.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map("MinStake",)

    def query_map_max_stake(self) -> dict[int, int]:
        """
        Retrieves a mapping of the maximum stake values for the network.

        Queries the network for the maximum stake values across various s
        ubnets of the network.

        Returns:
            A dictionary mapping network UIDs to their maximum stake values.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map("MaxStake",)

    def query_map_founder(self) -> dict[int, str]:
        """
        Retrieves a mapping of founders for the network.

        Queries the network to obtain the founders associated with 
        various subnets.

        Returns:
            A dictionary mapping network UIDs to their respective founders.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map("Founder",)

    def query_map_founder_share(self) -> dict[int, int]:
        """
        Retrieves a mapping of founder shares for the network.

        Queries the network for the share percentages 
        allocated to founders across different subnets.

        Returns:
            A dictionary mapping network UIDs to their founder share percentages.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map("FounderShare",)

    def query_map_incentive_ratio(self) -> dict[int, int]:
        """
        Retrieves a mapping of incentive ratios for the network.

        Queries the network for the incentive ratios, 
        which are the proportions of rewards or incentives
        allocated in different subnets of the network. 

        Returns:
            A dictionary mapping network UIDs to their incentive ratios.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map("IncentiveRatio",)

    def query_map_trust_ratio(self) -> dict[int, int]:
        """
        Retrieves a mapping of trust ratios for the network.

        Queries the network for trust ratios, 
        indicative of the level of trust or credibility assigned
        to different subnets of the network.

        Returns:
            A dictionary mapping network UIDs to their trust ratios.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map("TrustRatio",)

    def query_map_vote_threshold_subnet(self) -> dict[int, int]:
        """
        Retrieves a mapping of vote thresholds for subnets within the network.

        Queries the network for vote thresholds specific to various
        subnets, which are the treshold intervals for setting weights.

        Returns:
            A dictionary mapping network UIDs to their 
            vote thresholds for subnets.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map("VoteThresholdSubnet",)

    def query_map_vote_mode_subnet(self) -> dict[int, str]:
        """
        Retrieves a mapping of vote modes for subnets within the network.

        Queries the network for the voting modes used in different
        subnets, which define the methodology or approach of voting within those
        subnets. 

        Returns:
            A dictionary mapping network UIDs to their vote
            modes for subnets.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map("VoteModeSubnet",)

    def query_map_self_vote(self) -> dict[int, bool]:
        """
        Retrieves a mapping of self-vote settings for the network.

        Queries the network to determine whether self-voting is allowed in 
        different subnets of the network.

        Returns:
            A dictionary mapping network UIDs to their self-vote settings 
            (true or false).

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map("SelfVote",)

    def query_map_subnet_names(self) -> dict[int, str]:
        """
        Retrieves a mapping of subnet names within the network.

        Queries the network for the names of various subnets, 
        providing an overview of the different
        subnets within the network. 

        Returns:
            A dictionary mapping network UIDs to their subnet names.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map("SubnetNames",)

    def query_map_balances(self) -> \
            dict[str, dict['str', int | dict[str, int]]]:
        """
        Retrieves a mapping of account balances within the network.

        Queries the network for the balances associated with different accounts. 
        It provides detailed information including various types of 
        balances for each account. 

        Returns:
            A dictionary mapping account addresses to their balance details.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map('Account', module='System')

    def query_map_registration_blocks(self, netuid: int = 0) -> dict[int, int]:
        """
        Retrieves a mapping of registration blocks for UIDs on the network.

        Queries the network to find the block numbers at which various 
        UIDs were registered.

        Args:
            netuid: The network UID from which to get the registrations.

        Returns:
            A dictionary mapping UIDs to their registration block numbers.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map("RegistrationBlock", [netuid])

    def query_map_name(self, netuid: int = 0) -> dict[int, str]:
        """
        Retrieves a mapping of names for keys on the network.

        Queries the network for the names associated with different keys. 
        It provides a mapping of key UIDs to their registered names.

        Args:
            netuid: The network UID from which to get the names.

        Returns:
            A dictionary mapping key UIDs to their names.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query_map('Name', [netuid])

    #  == QUERY FUNCTIONS == #

    def get_immunity_period(self, netuid: int = 0) -> int:
        """
        Queries the network for the immunity period setting.

        The immunity period is a time duration during which a module 
        can not be deregistered from the network.
        Fetches the immunity period for a specified network subnet.

        Args:
            netuid: The network UID for which to query the immunity period.

        Returns:
            The immunity period setting for the specified network subnet.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query("ImmunityPeriod", params=[netuid],)

    def get_min_allowed_weights(self, netuid: int = 0) -> int:
        """
        Queries the network for the minimum allowed weights setting.

        Retrieves the minimum weight values that are possible to set
        by a validator within a specific network subnet.

        Args:
            netuid: The network UID for which to query the minimum allowed
              weights.

        Returns:
            The minimum allowed weight values for the specified network
              subnet.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query("MinAllowedWeights", params=[netuid],)

    def get_max_allowed_weights(self, netuid: int = 0) -> int:
        """
        Queries the network for the maximum allowed weights setting.

        Retrieves the maximum weight values that are possible to set
        by a validator within a specific network subnet.

        Args:
            netuid: The network UID for which to query the maximum allowed
              weights.

        Returns:
            The maximum allowed weight values for the specified network
              subnet.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query("MaxAllowedWeights", params=[netuid])

    def get_max_allowed_uids(self, netuid: int = 0) -> int:
        """
        Queries the network for the maximum allowed UIDs setting.

        Fetches the upper limit on the number of user IDs that can 
        be allocated or used within a specific network subnet.

        Args:
            netuid: The network UID for which to query the maximum allowed UIDs.

        Returns:
            The maximum number of allowed UIDs for the specified network subnet.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query("MaxAllowedUids", params=[netuid])

    def get_n(self, netuid: int = 0) -> int:
        """
        Queries the network for the 'N' hyperparameter, which represents how
        many modules are on the network.

        Args:
            netuid: The network UID for which to query the 'N' hyperparameter.

        Returns:
            The value of the 'N' hyperparameter for the specified network
              subnet.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query("N", params=[netuid])

    def get_tempo(self, netuid: int = 0) -> int:
        """
        Queries the network for the tempo setting, measured in blocks, for the
        specified subnet.

        Args:
            netuid: The network UID for which to query the tempo.

        Returns:
            The tempo setting for the specified subnet.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query("Tempo", params=[netuid])

    def get_total_stake(self, netuid: int = 0):
        """
        Queries the network for the total stake amount.

        Retrieves the total amount of stake within a specific network subnet.

        Args:
            netuid: The network UID for which to query the total stake.

        Returns:
            The total stake amount for the specified network subnet.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query("TotalStake", params=[netuid],)

    def get_registrations_per_block(self):
        """
        Queries the network for the number of registrations per block.

        Fetches the number of registrations that are processed per 
        block within the network.

        Returns:
            The number of registrations processed per block.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query("RegistrationsPerBlock",)

    def max_registrations_per_block(self, netuid: int = 0):
        """
        Queries the network for the maximum number of registrations per block.

        Retrieves the upper limit of registrations that can be processed in 
        each block within a specific network subnet.

        Args:
            netuid: The network UID for which to query.

        Returns:
            The maximum number of registrations per block for 
            the specified network subnet.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query("MaxRegistrationsPerBlock", params=[netuid],)

    def get_proposal(self, proposal_id: int = 0):
        """
        Queries the network for a specific proposal.

        Args:
            proposal_id: The ID of the proposal to query.

        Returns:
            The details of the specified proposal.

        Raises:
            QueryError: If the query to the network fails, is invalid, 
                or if the proposal ID does not exist.
        """

        return self.query("Proposals", params=[proposal_id],)

    def get_trust(self, netuid: int = 0):
        """
        Queries the network for the trust setting of a specific network subnet.

        Retrieves the trust level or score, which may represent the 
        level of trustworthiness or reliability within a 
        particular network subnet.

        Args:
            netuid: The network UID for which to query the trust setting.

        Returns:
            The trust level or score for the specified network subnet.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query("Trust", params=[netuid],)

    def get_uids(self, key: Ss58Address, netuid: int = 0) -> bool | None:
        """
        Queries the network for module UIDs associated with a specific key.

        Args:
            key: The key address for which to query UIDs.
            netuid: The network UID within which to search for the key.

        Returns:
            A list of UIDs associated with the specified key.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query("Uids", params=[netuid, key],)

    def get_unit_emission(self) -> int:
        """
        Queries the network for the unit emission setting.

        Retrieves the unit emission value, which represents the 
        emission rate or quantity for the $COMAI token.

        Returns:
            The unit emission value in nanos for the network.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query("UnitEmission",)

    def get_tx_rate_limit(self) -> int:
        """
        Queries the network for the transaction rate limit.

        Retrieves the rate limit for transactions within the network, 
        which defines the maximum number of transactions that can be 
        processed within a certain timeframe.

        Returns:
            The transaction rate limit for the network.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query("TxRateLimit",)

    def get_burn_rate(self) -> int:
        """
        Queries the network for the burn rate setting.

        Retrieves the burn rate, which represents the rate at 
        which the $COMAI token is permanently 
        removed or 'burned' from circulation.

        Returns:
            The burn rate for the network.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query("BurnRate", params=[],)

    def get_min_burn(self) -> int:
        """
        Queries the network for the minimum burn setting.

        Retrieves the minimum burn value, indicating the lowest 
        amount of the $COMAI tokens that can be 'burned' or 
        permanently removed from circulation.

        Returns:
            The minimum burn value for the network.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query("MinBurn", params=[],)

    def get_min_weight_stake(self) -> int:
        """
        Queries the network for the minimum weight stake setting.

        Retrieves the minimum weight stake, which represents the lowest 
        stake weight that is allowed for certain operations or 
        transactions within the network.

        Returns:
            The minimum weight stake for the network.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query("MinWeightStake", params=[])

    def get_vote_mode_global(self) -> str:
        """
        Queries the network for the global vote mode setting.

        Retrieves the global vote mode, which defines the overall voting 
        methodology or approach used across the network in default.

        Returns:
            The global vote mode setting for the network.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query("VoteModeGlobal",)

    def get_max_proposals(self) -> int:
        """
        Queries the network for the maximum number of proposals allowed.

        Retrieves the upper limit on the number of proposals that can be 
        active or considered at any given time within the network.

        Returns:
            The maximum number of proposals allowed on the network.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query("MaxProposals",)

    def get_max_registrations_per_block(self) -> int:
        """
        Queries the network for the maximum number of registrations per block.

        Retrieves the maximum number of registrations that can 
        be processed in each block within the network.

        Returns:
            The maximum number of registrations per block on the network.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query("MaxRegistrationsPerBlock", params=[],)

    def get_max_name_length(self) -> int:
        """
        Queries the network for the maximum length allowed for names.

        Retrieves the maximum character length permitted for names 
        within the network. Such as the module names

        Returns:
            The maximum length allowed for names on the network.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query("MaxNameLength", params=[],)

    def get_global_vote_threshold(self) -> int:
        """
        Queries the network for the global vote threshold.

        Retrieves the global vote threshold, which is the critical value or 
        percentage required for decisions in the network's governance process.

        Returns:
            The global vote threshold for the network.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query("GlobalVoteThreshold",)

    def get_max_allowed_subnets(self) -> int:
        """
        Queries the network for the maximum number of allowed subnets.

        Retrieves the upper limit on the number of subnets that can 
        be created or operated within the network.

        Returns:
            The maximum number of allowed subnets on the network.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query("MaxAllowedSubnets", params=[],)

    def get_max_allowed_modules(self) -> int:
        """
        Queries the network for the maximum number of allowed modules.

        Retrieves the upper limit on the number of modules that 
        can be registered within the network.

        Returns:
            The maximum number of allowed modules on the network.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query("MaxAllowedModules", params=[],)

    def get_min_stake(self,
                      netuid: int = 0) -> int:
        """
        Queries the network for the minimum stake required to register a key.

        Retrieves the minimum amount of stake necessary for 
        registering a key within a specific network subnet.

        Args:
            netuid: The network UID for which to query the minimum stake.

        Returns:
            The minimum stake required for key registration in nanos.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query('MinStake', params=[netuid])

    def get_stake(self,
                  key: Ss58Address,
                  netuid: int = 0,
                  ) -> int:
        """
        Queries the network for the stake delegated with a specific key.

        Retrieves the amount of total staked tokens 
        delegated a specific key address

        Args:
            key: The address of the key to query the stake for.
            netuid: The network UID from which to get the query.

        Returns:
            The amount of stake held by the specified key in nanos.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        return self.query("Stake", params=[netuid, key],)

    def get_stakefrom(
        self,
        key_addr: Ss58Address,
        netuid: int = 0,
    ) -> dict[str, int]:
        """
        Retrieves a list of keys from which a specific key address is staked.

        Queries the network for all the stakes received by a 
        particular key from different sources.

        Args:
            key_addr: The address of the key to query stakes from.

            netuid: The network UID from which to get the query.

        Returns:
            A dictionary mapping key addresses to the amount of stake 
            received from each.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """
        result = self.query('StakeFrom', [netuid, key_addr])

        return {k: v for k, v in result}

    def get_staketo(
        self,
        key_addr: Ss58Address,
        netuid: int = 0,
    ) -> dict[str, int]:
        """
        Retrieves a list of keys to which a specific key address stakes to.

        Queries the network for all the stakes made by a particular key to 
        different destinations.

        Args:
            key_addr: The address of the key to query stakes to.

            netuid: The network UID from which to get the query.

        Returns:
            A dictionary mapping key addresses to the 
            amount of stake given to each.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        result = self.query('StakeTo', [netuid, key_addr])

        return {k: v for k, v in result}

    def get_balance(
        self,
        addr: Ss58Address,
    ) -> int:
        """
        Retrieves the balance of a specific key.

        Args:
            addr: The address of the key to query the balance for.

        Returns:
            The balance of the specified key.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        result = self.query('Account', module='System', params=[addr])

        return result["data"]["free"]

    def get_block(self, block_hash: str | None = None) -> dict[Any, Any] | None:
        """
        Retrieves information about a specific block in the network.

        Queries the network for details about a block, such as its number, 
        hash, and other relevant information.

        Returns:
            The requested information about the block, 
            or None if the block does not exist 
            or the information is not available.

        Raises:
            QueryError: If the query to the network fails or is invalid.
        """

        with self.get_conn() as substrate:
            block: dict[Any, Any] | None = substrate.get_block(  # type: ignore
                block_hash  # type: ignore
            )

        return block

    def get_existential_deposit(self, block_hash: str | None = None) -> int:
        """
        Retrieves the existential deposit value for the network.

        The existential deposit is the minimum balance that must be maintained 
        in an account to prevent it from being purged. Denotated in nano units.

        Returns:
            The existential deposit value in nano units. 
        Note:
            The value returned is a fixed value defined in the 
            client and may not reflect changes in the network's configuration.
        """

        with self.get_conn() as substrate:
            result: int = substrate.get_constant(  #  type: ignore
                "Balances", "ExistentialDeposit", block_hash).value  #  type: ignore

        return result
