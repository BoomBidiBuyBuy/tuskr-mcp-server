# tuskr-mcp-server

Implements a Model Context Protocol (MCP) HTTP server for the [Tuskr REST API](https://tuskr.app/kb/latest/api)

Built on the FastMCP Python SDK.  
Supports access token authentication.

## Installation

### Environment variables / `.env` file

Set up environment variables or configure the `.env` file using the `.env.example` template.

The following environment variables are supported:

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

## Connect from client

Use the following template to connect the server

```
{
  "mcpServers": {
    "tuskr": {
      "transport": "http",
      "url": "http://<your-mcp-dns-or-ip>/mcp/",
      "headers": {
        "Authorization": "Bearer <your access token>",
        "Account-ID": "<your-tuskr-account-id>"
      }
    }
  }
}
```


The `Authorization` is mandatory.

The `Account-ID` is not required and can be set on the server side using the `TUSKR_ACCOUNT_ID` env variable. It's convenient in case you have single MCP Server for organization.


## Development

### Setup

1. Clone repo
2. Install development dependencies:
`uv sync --dev`
3. Create `.env` from `.env.example`

### Running MCP service

```
uv run --env-file .env src/main.py
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
