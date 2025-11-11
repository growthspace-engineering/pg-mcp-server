# server/tools/query.py
from server.config import mcp
from mcp.server.fastmcp import Context
from server.logging_config import get_logger
from sqlglot import parse_one, exp
from typing import Dict, List, Set, Any

logger = get_logger("pg-mcp.tools.query")

def extract_table_names(sql_query: str) -> Set[tuple]:
    """
    Extract table names (schema, table) from a SQL query.
    Handles both direct table references and information_schema queries.
    
    Returns:
        Set of tuples (schema_name, table_name). Schema defaults to 'public' if not specified.
    """
    tables = set()
    try:
        ast = parse_one(sql_query, dialect="postgres")
        if not ast:
            return tables
        
        # Check if this is an information_schema query
        is_information_schema = False
        for node in ast.walk():
            if isinstance(node, exp.Table):
                table_name = node.name.lower() if node.name else ""
                schema = node.db.lower() if node.db else ""
                if "information_schema" in schema or "information_schema" in table_name:
                    is_information_schema = True
                    break
        
        # If it's an information_schema query, extract table names from WHERE clause
        if is_information_schema:
            table_schema = 'public'  # default
            table_name = None
            
            # Walk the AST to find WHERE conditions
            for node in ast.walk():
                if isinstance(node, exp.EQ):
                    # Check for table_schema = 'value' or table_name = 'value'
                    left = node.left
                    right = node.right
                    
                    if isinstance(left, exp.Column):
                        col_name = left.name.lower() if left.name else ""
                        # Handle different literal types
                        if isinstance(right, exp.Literal):
                            # Get the literal value
                            value = right.this
                            # Convert to string and remove quotes if present
                            if value is not None:
                                value = str(value).strip("'\"")
                                
                                if col_name == "table_schema":
                                    table_schema = value
                                elif col_name == "table_name":
                                    table_name = value
                        elif isinstance(right, exp.Identifier):
                            # Handle unquoted identifiers
                            value = right.name if hasattr(right, 'name') else str(right)
                            if col_name == "table_schema":
                                table_schema = value
                            elif col_name == "table_name":
                                table_name = value
            
            if table_name:
                tables.add((table_schema, table_name))
        else:
            # Regular query - extract table names from FROM/JOIN clauses
            for node in ast.walk():
                if isinstance(node, exp.Table):
                    # In sqlglot, for PostgreSQL: schema.table format
                    # node.db is the schema (or database), node.name is the table
                    # If schema is not specified, it defaults to 'public'
                    schema = node.db if node.db else 'public'
                    table = node.name
                    if table and table.lower() not in ['information_schema', 'pg_catalog']:
                        tables.add((schema, table))
    except Exception as e:
        logger.debug(f"Could not parse SQL to extract table names: {e}")
        # If parsing fails, the query will still execute but without metadata
        # This is acceptable - metadata is a nice-to-have feature
        pass
    
    return tables

async def get_table_comments(conn, schema: str, table: str) -> Dict[str, Any]:
    """
    Get table and column comments for a specific table.
    
    Returns:
        Dictionary with 'table_comment' and 'columns' (dict of column_name -> comment)
    """
    result = {
        "table_comment": None,
        "columns": {}
    }
    
    try:
        # Get table comment
        table_comment_query = """
            SELECT obj_description(c.oid, 'pg_class') as comment
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = $1 AND c.relname = $2
        """
        table_comment = await conn.fetchval(table_comment_query, schema, table)
        if table_comment:
            result["table_comment"] = table_comment
        
        # Get column comments
        column_comments_query = """
            SELECT 
                a.attname AS column_name,
                col_description(a.attrelid, a.attnum) AS comment
            FROM pg_catalog.pg_attribute a
            JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = $1 
              AND c.relname = $2
              AND a.attnum > 0
              AND NOT a.attisdropped
            ORDER BY a.attnum
        """
        column_rows = await conn.fetch(column_comments_query, schema, table)
        for row in column_rows:
            if row['comment']:
                result["columns"][row['column_name']] = row['comment']
    except Exception as e:
        logger.debug(f"Error fetching comments for {schema}.{table}: {e}")
    
    return result

async def get_query_metadata(conn, sql_query: str) -> Dict[str, Any]:
    """
    Get table and column comments for all tables referenced in the query.
    
    Returns:
        Dictionary mapping "schema.table" -> {table_comment, columns: {col_name: comment}}
    """
    tables = extract_table_names(sql_query)
    metadata = {}
    
    for schema, table in tables:
        key = f"{schema}.{table}"
        metadata[key] = await get_table_comments(conn, schema, table)
    
    return metadata

async def execute_query(query: str, conn_id: str, params=None, ctx=Context, include_metadata: bool = False):
    """
    Execute a read-only SQL query against the PostgreSQL database.
    
    Args:
        query: The SQL query to execute (must be read-only)
        conn_id: Connection ID (required)
        params: Parameters for the query (optional)
        ctx: Optional request context
        include_metadata: If True, include table/column comments in response
        
    Returns:
        Query results as a list of dictionaries, or dict with 'data' and 'metadata' if include_metadata=True
    """
    
    db = mcp.state["db"]
    if not db:
        raise ValueError("Database connection not available in MCP state.")
        
    logger.info(f"Executing query on connection ID {conn_id}: {query}")
    
    async with db.get_connection(conn_id) as conn:
        # Ensure we're in read-only mode
        await conn.execute("SET TRANSACTION READ ONLY")
        
        # Execute the query
        try:
            records = await conn.fetch(query, *(params or []))
            data = [dict(record) for record in records]
            
            # If metadata is requested, fetch table and column comments
            if include_metadata:
                metadata = await get_query_metadata(conn, query)
                return {
                    "data": data,
                    "metadata": metadata
                }
            
            return data
        except Exception as e:
            # Log the error but don't couple to specific error types
            logger.error(f"Query execution error: {e}")
            raise

def register_query_tools():
    """Register database query tools with the MCP server."""
    logger.debug("Registering query tools")
    
    @mcp.tool()
    async def pg_query(query: str, conn_id: str, params=None):
        """
        Execute a read-only SQL query against the PostgreSQL database.
        Automatically includes table and column comments as metadata.
        
        Args:
            query: The SQL query to execute (must be read-only)
            conn_id: Connection ID previously obtained from the connect tool
            params: Parameters for the query (optional)
            
        Returns:
            Dictionary with 'data' (query results) and 'metadata' (table/column comments).
            Metadata is organized by table as "schema.table" -> {table_comment, columns: {col_name: comment}}
        """
        # Execute the query with metadata included
        return await execute_query(query, conn_id, params, include_metadata=True)
        
    @mcp.tool()
    async def pg_explain(query: str, conn_id: str, params=None):
        """
        Execute an EXPLAIN (FORMAT JSON) query to get PostgreSQL execution plan.
        
        Args:
            query: The SQL query to analyze
            conn_id: Connection ID previously obtained from the connect tool
            params: Parameters for the query (optional)
            
        Returns:
            Complete JSON-formatted execution plan
        """
        # Prepend EXPLAIN to the query
        explain_query = f"EXPLAIN (FORMAT JSON) {query}"
        
        # Execute the explain query
        result = await execute_query(explain_query, conn_id, params)
        
        # Return the complete result
        return result