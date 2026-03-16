# Agent Architecture

## Overview

This agent is a CLI tool that uses an LLM to answer questions about the project documentation and system. It has an **agentic loop** that allows it to use tools to read files, explore the project structure, and query the live backend API.

## Architecture

```
User Question → System Prompt + Tools → LLM → Tool Calls? → Execute Tools → Results → LLM → Final Answer
```

### Components

1. **Environment Loading**: Loads LLM credentials from `.env.agent.secret` and backend API key from `.env.docker.secret`
2. **Tool Definitions**: `read_file`, `list_files`, and `query_api` with JSON schemas
3. **Agentic Loop**: Iteratively calls LLM, executes tools, and feeds results back
4. **JSON Output**: Structured response with answer, source, and tool_calls

## Tools

The agent has three tools for navigating the project repository and querying the system:

### `read_file`

Reads the contents of a file from the project repository.

**Parameters:**
- `path` (string, required): Relative path from project root (e.g., `wiki/git-workflow.md`, `backend/app/main.py`)

**Returns:** File contents as a string, or an error message if the file doesn't exist.

**Security:** Rejects paths containing `..` (path traversal) or absolute paths.

**When to use:** Questions about documentation, source code, static facts (framework, ports, architecture).

### `list_files`

Lists files and directories at a given path.

**Parameters:**
- `path` (string, required): Relative directory path from project root (e.g., `wiki`, `backend/app`)

**Returns:** Newline-separated listing of entries (directories first, then files), or an error message.

**Security:** Rejects paths containing `..` (path traversal) or absolute paths.

**When to use:** Discovering what files exist in a directory before reading specific files.

### `query_api`

Queries the live backend API to get current data from the system.

**Parameters:**
- `method` (string, required): HTTP method (GET, POST, PUT, DELETE)
- `path` (string, required): API endpoint path (e.g., `/items/`, `/analytics/completion-rate`)
- `body` (string, optional): JSON request body for POST/PUT requests

**Returns:** JSON string with `status_code` and `body`, or an error message.

**Authentication:** Uses `LMS_API_KEY` from environment with `Authorization: Bearer <key>` header.

**When to use:** Questions about live data (item counts, scores, analytics), current system state, statistics.

## Environment Variables

The agent reads all configuration from environment variables:

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for query_api auth | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for backend (optional) | `.env.agent.secret` or default |

**Default:** `AGENT_API_BASE_URL` defaults to `http://localhost:42002` if not set.

**Important:** The autochecker injects its own values for these variables during evaluation. Never hardcode credentials.

## Agentic Loop

The agentic loop enables the agent to iteratively gather information before answering:

```python
while tool_call_count < MAX_TOOL_CALLS:
    1. Send messages + tool schemas to LLM
    2. If LLM returns tool_calls:
       - Execute each tool
       - Append results as 'tool' role messages
       - Continue loop
    3. If LLM returns text (no tool_calls):
       - This is the final answer
       - Extract answer and source
       - Output JSON and exit
```

### Message Format

Messages sent to the LLM follow the OpenAI chat format:

```python
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": "How do you resolve a merge conflict?"},
    # After tool calls:
    {"role": "assistant", "content": None, "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "call_1", "content": "file contents..."},
    # ... more iterations
]
```

### Maximum Tool Calls

The loop stops after 10 tool calls maximum to prevent infinite loops.

## System Prompt Strategy

The system prompt is critical for guiding the LLM to use the right tools. It explicitly tells the LLM:

1. **When to use read_file/list_files:**
   - Questions about documentation (git workflow, merge conflicts)
   - Questions about system architecture (framework, ports, status codes)
   - Questions about source code structure
   - Static facts that don't change

2. **When to use query_api:**
   - Questions about live data (how many items, scores)
   - Questions requiring current system state
   - Analytics and statistics
   - Any question asking "how many", "what is the count"

3. **How to cite sources:**
   - Wiki files: `wiki/filename.md#section-anchor`
   - API queries: `API: GET /items/`
   - Source code: `backend/app/main.py`

### Tool Selection Logic

The LLM decides which tool to use based on the question type:

- **"What framework does the backend use?"** → `read_file` (static fact, read source code or wiki)
- **"How many items are in the database?"** → `query_api` (live data, requires API call)
- **"What files are in the wiki?"** → `list_files` (discovery)
- **"How do you resolve a merge conflict?"** → `read_file` (documentation lookup)

## Output Format

The agent outputs JSON with three fields:

```json
{
  "answer": "There are 42 items in the database.",
  "source": "API: GET /items/",
  "tool_calls": [
    {
      "tool": "query_api",
      "args": {"method": "GET", "path": "/items/"},
      "result": "{\"status_code\": 200, \"body\": \"[...]\"}"
    }
  ]
}
```

### Fields

- **answer** (string): The LLM's final answer to the question
- **source** (string): Reference to the source (wiki file, API endpoint, or source code)
- **tool_calls** (array): All tool calls made during the conversation

### Source Extraction

The source is extracted by:
1. Looking for explicit `Source: wiki/filename.md#anchor` in the response
2. Looking for `Source: API: GET /path` pattern
3. Falling back to the last tool call (read_file or query_api)

## Path Security

File tools enforce security to prevent accessing files outside the project:

1. **No path traversal**: Paths containing `..` are rejected
2. **No absolute paths**: Paths starting with `/` are rejected
3. **Within project root**: Resolved paths must be within the project directory

```python
def is_safe_path(path: str) -> bool:
    if ".." in path:
        return False
    if os.path.isabs(path):
        return False
    resolved = os.path.normpath(os.path.join(project_root, path))
    return resolved.startswith(project_root)
```

## API Authentication

The `query_api` tool authenticates with the backend using:

```python
headers = {
    "Authorization": f"Bearer {lms_api_key}",
    "Content-Type": "application/json",
}
```

The `LMS_API_KEY` is loaded from `.env.docker.secret` and must be kept secret (gitignored).

## Usage

```bash
# Documentation question
uv run agent.py "How do you resolve a merge conflict?"

# System question
uv run agent.py "What framework does the backend use?"

# Data question
uv run agent.py "How many items are in the database?"
```

## Error Handling

- **Missing credentials**: Exit with error message to stderr
- **File not found**: Return error message as tool result
- **Path traversal attempt**: Return error message as tool result
- **LLM API errors**: Exit with error message to stderr
- **API connection errors**: Return error message with details
- **Max tool calls**: Use whatever answer is available

## Lessons Learned

Building the system agent taught me several important lessons about agentic systems:

1. **Tool descriptions matter**: The LLM relies entirely on tool descriptions to decide which tool to use. Vague descriptions lead to wrong tool selection. For example, initially the LLM would try to use `read_file` for "how many items" questions. Adding explicit guidance like "Use query_api for questions about live data, item counts, analytics" fixed this.

2. **Environment variable separation**: Keeping LLM credentials (`LLM_API_KEY`) separate from backend credentials (`LMS_API_KEY`) is crucial. They serve different purposes and come from different sources. Mixing them up causes authentication failures.

3. **Error messages help debugging**: When a tool fails, returning a descriptive error message (not just "error") helps the LLM understand what went wrong and potentially retry with corrected arguments.

4. **Source tracking is important**: The `source` field isn't just metadata—it's required for verification. The LLM needs explicit instructions to cite sources, and the extraction logic needs to handle multiple source types (wiki, API, source code).

5. **Iteration is necessary**: The first implementation rarely works perfectly. Running the benchmark (`run_eval.py`) reveals edge cases: the LLM might call tools with wrong arguments, miss the right endpoint, or format answers incorrectly. Each failure teaches you how to improve the system prompt or tool schemas.

6. **Security can't be an afterthought**: Path traversal prevention in file tools and restricting API access to a configured base URL are essential security measures. These should be built in from the start, not added later.

## Final Benchmark Score

After iterating on the system prompt and tool implementations, the agent passes all 10 local evaluation questions covering:
- Wiki lookup questions (merge conflicts, git workflow)
- System facts (framework, ports)
- Data queries (item counts, analytics)
- Bug diagnosis
- Reasoning questions
