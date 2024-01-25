# Running a Commune Node

## Requirements

- [Docker](https://docs.docker.com/get-docker/)
- [`yq`](https://mikefarah.gitbook.io/yq/)

Installing on Ubuntu:

```sh
sudo apt install docker.io
sudo apt install yq
```

## Docker Image

We provide the laster Docker image for the Commune node in [this Github
package][docker-package] at the [`latest` tag][docker-image]. You can pull the
image with the command:

```sh
docker pull ghcr.io/agicommies/subspace:latest
```

## Chain specs

You can get the chain specs file from the [`main/specs/main.json` file] at
`github.com/commune-ai/subspace`:

```sh
wget https://raw.githubusercontent.com/commune-ai/subspace/main/specs/main.json
```

## Getting bootnodes

You can get the bootnodes list from the `bootnodes` field at the
[`commune/modules/subspace/chain/chain.yaml` file] in
`github.com/commune-ai/commune`.

```sh
wget https://raw.githubusercontent.com/commune-ai/commune/main/commune/modules/subspace/chain/chain.yaml
yq '.chain_info.main.boot_nodes[]' chain.yaml -r > bootnodes.txt
```

## Deploying the config

Pick a directory to store the node data, and copy the chain specs and bootnodes:

```sh
export COMMUNE_NODE_DIR="/commune-node"

mkdir -p "$COMMUNE_NODE_DIR/specs"
cp main.json "$COMMUNE_NODE_DIR/specs/main.json"
cp bootnodes.txt "$COMMUNE_NODE_DIR/bootnodes.txt"
cp node-start.sh "$COMMUNE_NODE_DIR/node-start.sh"
```

---

[docker-package]: https://github.com/orgs/agicommies/packages/container/package/subspace
[docker-image]: https://github.com/orgs/agicommies/packages/container/subspace/164109015?tag=latest

[`commune/modules/subspace/chain/chain.yaml` file]: https://github.com/commune-ai/commune/blob/main/commune/modules/subspace/chain/chain.yaml
[`main/specs/main.json` file]: https://github.com/commune-ai/subspace/blob/main/specs/main.json
