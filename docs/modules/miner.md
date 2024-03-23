# Miner Guide

## Description

The `comx module serve` command is a powerful tool that allows you to effortlessly deploy your modules and embark on an exciting journey with Commune. By leveraging this command, you can quickly set up and expose your module's endpoints, making it accessible to others within the Commune ecosystem.

## Installation

To install the Communex CLI, run the following command:

```sh
pip install communex
```

## Usage

To serve a Python module, ensure that it's a class inheriting from our `Module` class. Then, use our `endpoint` decorator on the methods that you want to expose as endpoints. You can refer to the `example` folder to see this being done.

With a class that inherits from `Module` and the communex CLI installed, you can simply run:

```
comx module serve <qualified_path> <port> <key> <subnets>
```

- `qualified_path`: The dotted path to the class that should be served. For example, `communex.module.example.openai.OpenAI`.
- `port`: The port that the API should run on your computer.
- `key`: The name of the key file of your module.
- `subnets`: The subnets that your module will serve. Calls from keys of any other subnet will be refused.

Additionally, you can optionally pass the following arguments:

- `whitelist`: A list of `SS58Address`. The API will only answer calls signed with the key referring to this address.
- `blacklist`: A list of `SS58Address` that you won't answer to.
- `ip`: The IP address on which the API should be served. By default, it's `127.0.0.1`.

## Running openai example

First make sure to set the environment variable `OPENAI_API_KEY` with your OpenAI API key. And you are in the Communex root folder.

```sh
cd src/communex
export OPENAI_API_KEY=your_openai_api_key
```

Then run the following command:

```sh
comx module serve communex.module.example.gpt.OpenAIModule <port> <key> <subnets>
```

To run module using pm2, install it globally:

```sh
npm install -g pm2
```

Then run the following command:

```sh
pm2 start "comx module serve communex.module.example.gpt.OpenAIModule <port> <key> <subnets>" --name "openai"
```

## Communication

In Communex, we provide the `ModuleClient` class that you can use to communicate with APIs served using this command. However, if you prefer, you can implement your own. Just make sure that you sign the request using your private key and pass the following fields as headers:

- `X-Signature`: The signature as a hexadecimal.
- `X-Key`: Your public key as a hexadecimal.
- `X-Crypto`: The crypto type of the signature.
