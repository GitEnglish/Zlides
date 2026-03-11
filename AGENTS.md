# AGENTS.md - Zlides Development Guide

This file provides guidance for AI agents working on the Zlides codebase.

## Global Skills

This project uses Claude Code with global skills. Before starting work, check relevant skills:
- `skill-developer` - For creating/modifying skills
- `systematic-debugging` - For debugging issues
- `verification-before-completion` - For running verification commands
- `clean-code` - For code quality standards

Run skill lookup to find relevant skills for your task.

---

## Build, Lint, and Test Commands

### Environment Setup
```bash
# Export your Z.AI API key (get it from your Z.AI account)
export ZAI_API_KEY="your-api-key-here"

# Install/sync dependencies
uv sync
```

### Running the Application
```bash
uv run python slide_server.py
uv run uvicorn slide_server:app --host 0.0.0.0 --port 8766
```

### Running Tests
```bash
uv run pytest
uv run pytest tests/test_slide_server.py
uv run pytest tests/test_slide_server.py::test_extract_html_success -v
uv run pytest -v -s
```

### Linting and Type Checking
```bash
uv run ruff check .
uv run ruff check . --fix
uv run ruff format .
```

---

## Code Style Guidelines

### General Principles
- Write clean, readable Python code
- Keep functions small and focused (under 50 lines)
- Use async/await for I/O-bound operations (httpx, FastAPI)

### Imports (Order Matters)
```python
import os
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
```

### Naming Conventions
- **Variables/functions**: `snake_case` (e.g., `session_store`, `extract_html_from_response`)
- **Classes**: `PascalCase` (e.g., `ChatRequest`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `ZAI_ENDPOINT`)
- **Files**: `snake_case.py`

### Type Annotations
- Use type hints for all function parameters and return values
- Use `Optional[T]` instead of `T | None` for compatibility

### Error Handling
```python
if response.status_code != 200:
    raise HTTPException(status_code=500, detail="Z.AI API Error")
```
- Use FastAPI's `HTTPException` for HTTP-level errors
- Return meaningful error messages to clients

### FastAPI Patterns
- Use Pydantic `BaseModel` for request/response schemas
- Use async route handlers for I/O operations
- Define routes in `slide_server.py`

### Configuration
- Environment variables for secrets (e.g., `ZAI_API_KEY`)
- Use `os.getenv()` with clear variable names

---

## Architecture

### Request Flow
1. User sends command in frontend (`index.html`)
2. Frontend POSTs to `/command` with message
3. Backend proxies to Z.AI API with session context
4. Backend extracts HTML from nested response
5. Frontend renders HTML in preview iframe

### Session Management
- `session_store` maintains `conversation_id` in-memory
- Always reuse conversation ID to preserve agent context
- Enables edit commands ("make font bigger") to apply to same slide

### CORS
- Current: allows all origins (`*`) for local development

---

## Development Tasks

### Adding a New API Endpoint
1. Define request model with Pydantic in `slide_server.py`
2. Add async route handler with proper type hints
3. Follow error handling patterns

### Adding Dependencies
```bash
uv add <package>
uv add --dev <package>
```

### Frontend Development
- Edit `index.html` directly - no build step
- Backend must be running for full functionality
- Frontend connects to `http://localhost:8000/command`

---

## Testing Guidelines

- Create `tests/` directory in project root
- Use `pytest` as test runner
- Follow naming: `test_*.py` for files, `test_*` for functions
- Mock external API calls with `unittest.mock` or `pytest-mock`
- See `tests/test_slide_server.py` for examples

---

## Project Structure
```
/Users/safeSpacesBro/zlides/
├── slide_server.py    # FastAPI backend (main entry point)
├── index.html        # Frontend chat interface
├── pyproject.toml    # Project dependencies
├── tests/            # Test files (create this directory)
└── AGENTS.md         # This file
```
