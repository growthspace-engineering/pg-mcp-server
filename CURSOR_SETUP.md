# Adding PG-MCP Server to Cursor

After running the Docker container, you can add this MCP server to Cursor.

## Step 1: Run the Container

```bash
# Pull and run the container
docker pull ghcr.io/growthspace-engineering/pg-mcp-server:latest
docker run -d \
  --name pg-mcp \
  -p 8000:8000 \
  -e LOG_LEVEL=DEBUG \
  ghcr.io/growthspace-engineering/pg-mcp-server:latest
```

### Environment Variables

The server supports the following environment variables:

- **`LOG_LEVEL`** (optional): Set the logging level. Defaults to `DEBUG`. Valid values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

**Important**: The server does **not** require `DATABASE_URL`. Database connections are made dynamically through the `connect` tool after the server is running. You'll provide your PostgreSQL connection string when you use the `connect` tool in Cursor.

Example with custom log level:

```bash
docker run -d \
  --name pg-mcp \
  -p 8000:8000 \
  -e LOG_LEVEL=INFO \
  ghcr.io/growthspace-engineering/pg-mcp-server:latest
```

## Step 2: Configure Cursor

1. Open Cursor Settings (Cmd/Ctrl + ,)
2. Navigate to **Features** → **Model Context Protocol** (or search for "MCP")
3. Click **"Add Server"** or **"Edit Config"**
4. Choose one of the following transport options:

### Option A: SSE Transport (Docker/Server Mode)

#### Using Cursor UI
- **Server Name**: `pg-mcp-server`
- **Transport Type**: `SSE` (Server-Sent Events)
- **URL**: `http://localhost:8000/sse`

#### Manual Configuration File

If you need to edit the config file directly, it's typically located at:

**macOS/Linux**: `~/.cursor/mcp.json` or `~/.config/cursor/mcp.json`  
**Windows**: `%APPDATA%\Cursor\mcp.json`

Add this entry:

```json
{
  "mcpServers": {
    "pg-mcp-server": {
      "url": "http://localhost:8000/sse",
      "transport": "sse",
      "env": {
        "LOG_LEVEL": "DEBUG"
      }
    }
  }
}
```

### Option B: Stdio Transport (Recommended for Local Development)

Stdio mode runs the server directly without needing Docker or a separate server process. This is the simplest setup and doesn't require authentication.

#### Prerequisites

- Python 3.13+ installed
- `uv` package manager installed (for `uvx`)

Install `uv` if you don't have it:
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with Homebrew
brew install uv
```

#### Configuration

Add this entry to your `mcp.json`:

```json
{
  "mcpServers": {
    "pg-mcp-server": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/growthspace-engineering/pg-mcp-server.git",
        "python",
        "-m",
        "server.stdio"
      ],
      "env": {
        "LOG_LEVEL": "DEBUG"
      }
    }
  }
}
```

**Note**: To pin to a specific version, use a tag:
```json
"git+https://github.com/growthspace-engineering/pg-mcp-server.git@v0.1.1"
```

**Benefits of stdio mode**:
- ✅ No Docker required
- ✅ No separate server process needed
- ✅ No authentication required (for public repos)
- ✅ Automatic dependency management via `uvx`
- ✅ Works immediately after pushing to GitHub

**Note about environment variables**: 
- **Docker setup (SSE)**: Pass environment variables to the Docker container using `-e` flags (see Step 1 above)
- **Stdio mode**: Environment variables in the `env` section of MCP config will be passed to the server process
- **SSE transport**: When using SSE transport with a URL, the `env` section in MCP config typically won't affect the server since Cursor is connecting to an already-running process. Set environment variables on the server side instead.

## Step 3: Restart Cursor

After adding the configuration, restart Cursor for the changes to take effect.

## Step 4: Connect to Your Database

Once the MCP server is connected in Cursor, you can use it to:

1. **Connect to a PostgreSQL database** using the `connect` tool with your connection string
2. **Query your database** using the `pg_query` tool
3. **Explore schema** via resources like `pgmcp://{conn_id}/schemas`
4. **Get query explanations** using the `pg_explain` tool

### Connecting to Your Database

To connect to a PostgreSQL database, use the `connect` tool with your connection string. You can do this by:

- **Asking Cursor**: "Connect to my database at `postgresql://user:password@host:port/database`"
- **Using the tool directly**: The `connect` tool accepts a `connection_string` parameter

**Example connection string format**:
```
postgresql://username:password@localhost:5432/mydatabase
```

The server will return a `conn_id` that you'll use for subsequent queries and operations.

### Example Usage in Cursor

After connecting, you can ask Cursor things like:
- "Show me all tables in the public schema"
- "What columns does the users table have?"
- "Query the top 10 customers by revenue"
- "Explain the execution plan for this query"

## Troubleshooting

- **Connection refused**: Make sure the Docker container is running (`docker ps`)
- **Port already in use**: Change the port mapping: `-p 8001:8000` and update the URL to `http://localhost:8001/sse`
- **Can't connect from Cursor**: Ensure the container is accessible from your host machine

## Remote Server

If the server is running on a remote machine, replace `localhost` with the server's IP address or hostname:

```json
{
  "mcpServers": {
    "pg-mcp-server": {
      "url": "http://your-server-ip:8000/sse",
      "transport": "sse"
    }
  }
}
```

