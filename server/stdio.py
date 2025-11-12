# server/stdio.py
"""
Stdio entry point for the PostgreSQL MCP server.

This module provides a stdio transport interface for the MCP server,
allowing it to be used with tools like Cursor that communicate via
standard input/output streams.
"""
import os
from server.logging_config import configure_logging, get_logger

# Configure logging first thing to capture all subsequent log messages
log_level = os.environ.get("LOG_LEVEL", "DEBUG")
configure_logging(level=log_level)
logger = get_logger("stdio")

# Import MCP instance and register everything
from server.config import mcp, global_db
from server.resources.schema import register_schema_resources
from server.resources.data import register_data_resources
from server.resources.extensions import register_extension_resources
from server.tools.connection import register_connection_tools
from server.tools.query import register_query_tools
from server.tools.viz import register_viz_tools
from server.prompts.natural_language import register_natural_language_prompts
from server.prompts.data_visualization import register_data_visualization_prompts

# Register tools and resources with the MCP server
logger.info("Registering resources and tools")
register_schema_resources()   # Schema-related resources (schemas, tables, columns)
register_extension_resources()
register_data_resources()     # Data-related resources (sample, rowcount, etc.)
register_connection_tools()   # Connection management tools
register_query_tools()
register_viz_tools()         # Visualization tools
register_natural_language_prompts()  # Natural language to SQL prompts
register_data_visualization_prompts() # Data visualization prompts

if __name__ == "__main__":
    logger.info("Starting MCP server with stdio transport")
    # The lifespan context manager in config.py will handle cleanup automatically
    mcp.run()

