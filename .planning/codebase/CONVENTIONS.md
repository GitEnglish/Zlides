# CONVENTIONS.md - Code Conventions

**Last Updated:** 2026-03-31

## Python Style

### Formatting

- **No formal linter configured** (no ruff, black, or pylint in dev deps)
- **Mixed indentation styles** observed:
  - Most code uses 4-space indentation
  - Some trailing whitespace
- **Line length:** No strict limit observed

### Naming

| Type | Convention | Example |
|------|------------|---------|
| Functions | `snake_case` | `extract_html_from_response()` |
| Variables | `snake_case` | `accumulated_html`, `last_data` |
| Constants | `UPPER_SNAKE_CASE` | `VERSION`, `Z_AI_API_KEY`, `SAVED_SLIDES_DIR` |
| Classes | `PascalCase` | `ChatRequest` (Pydantic model) |
| Endpoints | `kebab-case` | `/command`, `/upload`, `/style` |

### Docstrings

- **Minimal docstrings** — no function documentation observed
- **Comments:** Sparse, mostly for section headers (`# ── Helpers ──`)

## Error Handling

### Pattern

```python
try:
    # Operation
except Exception as e:
    print(f"[Error] {traceback.format_exc()}")
    yield error SSE event
```

### Characteristics

- **Broad exception handling** — `except Exception` commonly used
- **Print-based logging** — No structured logging
- **SSE error propagation** — Errors sent as `{"type": "error", "text": "..."}`

### HTTP Errors

- **FastAPI HTTPException** for bad requests (422, 400, 401)
- **Status codes:** 200 (success), 422 (validation), 400 (bad file type), 401 (no API key)

## Type Hints

| Status | Usage |
|--------|-------|
| **Function signatures** | ✅ Present (`async def send_command(request: ChatRequest)`) |
| **Return types** | ⚠️ Missing (`def generate():` instead of `-> AsyncGenerator`) |
| **Variable annotations** | ❌ Rare |
| **Pydantic models** | ✅ Fully typed (`ChatRequest`) |

## Async Patterns

- **AsyncIO used throughout:**
  - `async def` for endpoint handlers
  - `async with httpx.AsyncClient()` for API calls
  - `async for` in SSE streaming
- **No sync/async mixing** — all I/O is async

## Frontend Conventions

### JavaScript Style

- **Vanilla JS** — No framework, no build step
- **Global variables** for state (`currentSlides`, `currentSlideIdx`)
- **Event handlers** in `onclick` attributes
- **Fetch API** for HTTP requests
- **AbortController** for request cancellation

### CSS Organization

- **Single `<style>` block** in `<head>`
- **Scoped selectors** (e.g., `#sidebar .msg`)
- **Color variables:** Not used (hardcoded hex values)

## API Contract

### Request Format

```python
class ChatRequest(BaseModel):
    message: str              # Required
    system_prompt: str = ""   # Optional
    page_count: int | None = None
    slide_type: str = "slides"
    layout: str = ""
    theme: str = ""
    language: str = "en"
    web_search: bool = True
```

### Response Format (SSE)

```javascript
data: {"type": "thinking", "text": "..."}
data: {"type": "answer", "text": "..."}
data: {"type": "final_html", "html": "<!DOCTYPE html>...", "saved_to": "path"}
data: {"type": "error", "text": "..."}
```

## Testing Conventions

| Framework | pytest |
| Test file location | `tests/` directory |
| Test naming | `test_<function>_<scenario>()` |
| Fixtures | Used for client and env vars |
| Coverage | No coverage tracking configured |

## File Organization

- **Single-file modules** preferred
- **No package structure** (flat `*.py` files at root)
- **All frontend code** in one `index.html` file

## Constants

- **Module-level constants** at top of files
- **Environment-derived:** Loaded via `os.getenv()` with defaults
- **No config files** other than `.env`

## Import Order

```python
# Standard library
import os
import time
from datetime import datetime

# Third-party
import httpx
from fastapi import ...
from pydantic import ...

# Local (none in this project — single file)
```
