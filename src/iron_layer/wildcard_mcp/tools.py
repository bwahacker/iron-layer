"""
Tool definitions for the wildcard MCP server.

Names are chosen to match what real agents expose so injection text written
to target real systems will reach for them.
"""
from __future__ import annotations

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "read_file",
        "description": (
            "Read the contents of a file from the local filesystem. "
            "Use this to inspect configuration, source code, or data files."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file.",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file on the local filesystem.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to write to."},
                "content": {"type": "string", "description": "Content to write."},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_directory",
        "description": "List files and directories at a given path.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path to list."}
            },
            "required": ["path"],
        },
    },
    {
        "name": "execute",
        "description": "Execute a shell command and return stdout/stderr.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cmd": {"type": "string", "description": "Shell command to execute."}
            },
            "required": ["cmd"],
        },
    },
    {
        "name": "bash",
        "description": "Run a bash command or script.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Bash command or script."}
            },
            "required": ["command"],
        },
    },
    {
        "name": "fetch",
        "description": "Make an HTTP request and return the response body.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch."},
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE"],
                    "description": "HTTP method.",
                },
                "headers": {
                    "type": "object",
                    "description": "Optional HTTP headers.",
                },
                "body": {
                    "type": "string",
                    "description": "Optional request body.",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "send_email",
        "description": "Send an email message.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address."},
                "subject": {"type": "string", "description": "Email subject."},
                "body": {"type": "string", "description": "Email body."},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "db_query",
        "description": "Execute a SQL query against the database and return results.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "SQL query to execute."}
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_env",
        "description": "Read the value of an environment variable.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "var": {
                    "type": "string",
                    "description": "Environment variable name.",
                }
            },
            "required": ["var"],
        },
    },
    {
        "name": "list_users",
        "description": "List all users in the system.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_api_key",
        "description": "Retrieve an API key for a given service.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "Name of the service (e.g. 'openai', 'stripe').",
                }
            },
            "required": ["service"],
        },
    },
]

# Map name → definition for O(1) lookup
TOOL_BY_NAME: dict[str, dict] = {t["name"]: t for t in TOOL_DEFINITIONS}
