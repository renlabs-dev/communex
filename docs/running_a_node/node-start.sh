#!/bin/sh
set -e

NODE_DATA_DIR="${NODE_DATA_DIR:-/node-data}"

BOOTNODES="$(< "$NODE_DATA_DIR/bootnodes.txt" xargs echo)"

# shellcheck disable=SC2086
/subspace/target/release/node-subspace \
    --base-path "$NODE_DATA_DIR" --chain "$NODE_DATA_DIR/specs/main.json" \
    --rpc-external --rpc-cors=all --port 30333 --rpc-port 9944 \
    --bootnodes $BOOTNODES "$@"
