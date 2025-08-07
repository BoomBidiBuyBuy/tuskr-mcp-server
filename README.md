# tuskr-mcp-server

Implements Model Conext Protocol (MCP) server for the Tuskr REST API

https://tuskr.app/kb/latest/api


## Install

### Env variables / .env file

Setup environment variables or configure the `.env` file from the `.env.example`

It support the following environment variables

```
TUSKR_ACCOUNT_ID=<your account id>
TUSKR_ACCESS_TOKEN=<your access token>
```
(this doc desc https://tuskr.app/kb/latest/api)

and optionally 
```
MCP_PORT=<port you want to run MCP>
MCP_HOST=0.0.0.0
```

## Development

### Setup

1. Clone repo
2. Install development dependencies:
`uv sync --dev`
3. Create `.env` from `.env.example`

### Running MCP service

```
uv run --env-file .env src/main
```

### Running tests

The project uses pytest for testing. The following command will run all tests

```
uv run pytest -vsx
```

### Running linters

The project uses the `ruff` tool as a linter.

The following command allows to run linter

```
uv run ruff check
```

and this command allow to fix formatting

```
uv run ruff format
```

### Dockerization

The following command allows to build a docker image
```
docker build -t tuskr-mcp .
```

and then you can run it using the
```
docker run -it tuskr-mcp
```
