# tuskr-mcp-server

Implements a Model Context Protocol (MCP) server for the [Tuskr REST API](https://tuskr.app/kb/latest/api)

Built on the FastMCP Python SDK.  
Supports access token authentication.

## Tools

Every tool wraps a single Tuskr REST endpoint, relative to
`https://api.tuskr.live/api/tenant/<tenant-id>/`.

| Tool | Method | Endpoint | Purpose |
| --- | --- | --- | --- |
| `list_projects` | `GET` | `project` | Lists projects, filterable by name and by status (`active` / `archived`). |
| `list_test_cases` | `GET` | `test-case` | Lists a project's test cases, filterable by test suite, section, key, name and custom fields. Use it to discover the case keys a project actually contains before recording results. |
| `list_test_runs` | `GET` | `test-run` | Lists a project's test runs, filterable by name, key, status and assignee. `filter_incomplete=True` walks every page and returns only runs below 100% done. |
| `create_test_run` | `POST` | `test-run` | Creates a test run containing all cases in the project or a named subset. |
| `copy_test_run` | `POST` | `test-run/copy` | Copies an existing run and its case selection within the same project. Results are not carried over; every case starts untested. |
| `add_test_run_results` | `POST` | `test-run-result/bulk` | Records one status against one or many cases in a run. Prefer a single call with a list of cases over repeated single calls. |
| `get_test_run_results` | `GET` | `test-run/<id>/results` | Fetches the cases in a run with their latest result, filterable by status. Pass `status='FAILED'` for a confirmation-test worklist. |
| `get_test_run_details` | `GET` | `test-run/<id>/details` | Fetches a run's metadata plus `firstResultAt`, `lastResultAt` and `durationInMinutes`. Takes the run's ID, not its key. The timestamps are null until a result is recorded, and Tuskr may leave them null for results recorded before it added the endpoint, so a null means unknown, not that the run has no results. |
| `set_test_run_lock` | `POST` | `test-run/set-lock` | Locks a run read-only, or unlocks it. One run per call. |
| `archive_test_runs` | `POST` | `test-run/archive` | Archives one or more runs by ID. The response is a bare boolean, so confirm the new state with `list_test_runs(filter_status='archived')`. Unarchiving is not exposed by the API and has to be done in the Tuskr UI. |

Result status keys such as `PASSED` and `FAILED` are configured per tenant, so use
the keys defined in your own account.

Tuskr rate-limits every plan at 10 requests/second. The bulk tools exist for that
reason: batch where the endpoint allows it.

The server also exposes one resource, `resource://service_description`, which
describes its purpose to the client.

## Installation

### Environment variables / `.env` file

Set up environment variables or configure the `.env` file using the `.env.example` template.

The following environment variables are supported:

```
TUSKR_TENANT_ID=<your tenant id>
TUSKR_ACCESS_TOKEN=<your access token>
```
(this doc desc https://tuskr.app/kb/latest/api)

and optionally 
```
MCP_TRANSPORT=<transport type: http or stdio>
MCP_HOST=<host for HTTP transport>
MCP_PORT=<port for HTTP transport>
```

## Command Line Parameters

The MCP server supports the following command line parameters:

- `--transport`: Transport type for the MCP server. Options: `http` (default) or `stdio`
- `--host`: Host address for HTTP transport (default: `0.0.0.0`)
- `--port`: Port number for HTTP transport (default: `8000`)

**Note**: The `--host` and `--port` parameters are only applicable when using the `http` transport.

### Default Values

- **Transport**: `http` (can be overridden with `MCP_TRANSPORT` environment variable)
- **Host**: `0.0.0.0` (can be overridden with `MCP_HOST` environment variable)
- **Port**: `8000` (can be overridden with `MCP_PORT` environment variable)

## Connect from client

### HTTP Transport (Default)

Use the following template to connect the server via HTTP:

```
{
  "mcpServers": {
    "tuskr": {
      "transport": "http",
      "url": "http://<your-mcp-dns-or-ip>/mcp/",
      "headers": {
        "Authorization": "Bearer <your access token>",
        "Tenant-ID": "<your-tuskr-tenant-id>"
      }
    }
  }
}
```

The `Authorization` is mandatory.

The `Tenant-ID` is not required and can be set on the server side using the `TUSKR_TENANT_ID` env variable. It's convenient in case you have a single MCP Server for your organization.

### Migrating from TUSKR_ACCOUNT_ID

Earlier versions of this server used the env var `TUSKR_ACCOUNT_ID` and the HTTP header
`Account-ID`. These continue to work, but emit a deprecation warning. Tuskr's own
documentation and UI consistently use the term "Tenant ID" (it is part of the REST URL
path: `/api/tenant/<tenant-id>/`), so the preferred names are now `TUSKR_TENANT_ID` and
the `Tenant-ID` HTTP header. Both names will be supported until a future major version
removes the legacy names.

To migrate an existing config, replace `TUSKR_ACCOUNT_ID` with `TUSKR_TENANT_ID`; no
other changes are required.

### stdio Transport (for local development)

For local development and integration with tools like `uvx`, use the `stdio` transport:

```
{
  "mcpServers": {
    "tuskr": {
      "transport": "stdio",
      "command": "uvx",
      "args": ["tuskr-mcp-server", "--transport", "stdio"]
    }
  }
}
```

or use `uv` with source code:

```
{
  "mcpServers": {
    "tuskr": {
      "transport": "stdio",
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/your/tuskr-mcp-server",
        "run",
        "src/main.py",
        "--transport",
        "stdio"
      ]
    }
  }
}
```

## Integrate with Claude

Worked examples for Claude Code and the Claude desktop app. Both name the server
`tuskr`, so its tools appear as `list_projects`, `list_test_runs` and so on.

### Claude Code

Run the server locally over stdio, with credentials passed as environment
variables:

```
claude mcp add --transport stdio tuskr \
  --env TUSKR_TENANT_ID=<your tenant id> \
  --env TUSKR_ACCESS_TOKEN=<your access token> \
  -- uvx tuskr-mcp-server --transport stdio
```

Everything after `--` is the command Claude Code runs to start the server, kept
separate from Claude Code's own flags.

Or connect to a shared instance over HTTP:

```
claude mcp add --transport http tuskr https://<your-mcp-dns-or-ip>/mcp/ \
  --header "Authorization: Bearer <your access token>" \
  --header "Tenant-ID: <your-tuskr-tenant-id>"
```

Drop the `Tenant-ID` header if the instance already sets `TUSKR_TENANT_ID`
server-side.

`claude mcp add` stores the configuration without validating credentials, so a
wrong token is only reported when the server is first contacted. Run `/mcp`
inside a session and check that `tuskr` shows as connected.

Add `--scope project` to write the entry to the repository's `.mcp.json` and
share it with the team. Keep credentials out of a shared file: reference them as
`--env TUSKR_ACCESS_TOKEN=${TUSKR_ACCESS_TOKEN}` and let each developer supply
the value from their own environment.

### Claude desktop app

Edit `claude_desktop_config.json` (Settings, Developer, Edit Config):

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

For a local stdio server:

```
{
  "mcpServers": {
    "tuskr": {
      "command": "uvx",
      "args": ["tuskr-mcp-server", "--transport", "stdio"],
      "env": {
        "TUSKR_TENANT_ID": "<your tenant id>",
        "TUSKR_ACCESS_TOKEN": "<your access token>"
      }
    }
  }
}
```

`command` has to resolve on the app's own `PATH`, which is not the same as your
shell's. If the server fails to start, use the absolute path to `uvx`.

For a shared HTTP instance:

```
{
  "mcpServers": {
    "tuskr": {
      "type": "http",
      "url": "https://<your-mcp-dns-or-ip>/mcp/",
      "headers": {
        "Authorization": "Bearer <your access token>",
        "Tenant-ID": "<your-tuskr-tenant-id>"
      }
    }
  }
}
```

The `type` key is required on any entry that uses `url`; without it the entry is
read as a stdio server and skipped. Restart the app after editing the file.

### Check it works

Ask Claude to list your Tuskr projects. It should call `list_projects` and come
back with project names and IDs. A useful follow-up, since it exercises a filter
and a second tool: ask which test runs in a given project are not yet finished,
which resolves to `list_test_runs` with `filter_incomplete`.

A request such as "mark TC-14 and TC-15 as passed in run TR-3" resolves to a
single `add_test_run_results` call. Bear in mind that several of these tools
write to Tuskr, so point the server at a sandbox project while you are still
exploring.

## Development

### Setup

1. Clone repo
2. Install development dependencies:
`uv sync --dev`
3. Create `.env` from `.env.example`

### Running MCP service

#### HTTP Transport (Default)
```
uv run --env-file .env src/main.py
```

#### stdio Transport (for local development)
```
uv run --env-file .env src/main.py --transport stdio
```

#### Custom Host/Port
```
uv run --env-file .env src/main.py --host 127.0.0.1 --port 9000
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