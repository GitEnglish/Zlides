# Zlides — Agent Onboarding Guide

## Project Overview

Zlides is a FastAPI web app that generates HTML presentations, worksheets, posters, and reports by streaming prompts to a Z.AI agent (`slides_glm_agent`). It has a vanilla-JS frontend, a style-bank system for visual themes, and exports to HTML/PNG/PDF.

## Essential Commands

| Command | Purpose |
|---------|---------|
| `./launch.sh` | **Primary launch**. Loads `.env`, kills old processes on port 2828, starts server, opens browser. |
| `uv run python slide_server.py` | Start server directly (port 2828). |
| `pytest tests/` | Run test suite. |
| `uv run pytest tests/` | Run tests via uv. |

> **Note**: `main.py` is a stub. The real entry point is **`slide_server.py`**.

## Environment Setup

- Requires Python ≥3.11
- Uses **`uv`** for package management (`pyproject.toml` + `uv.lock`)
- Requires `.env` file with `Z_AI_API_KEY` (format: `key.secret`, split on first dot for JWT)
- `launch.sh` sources `.env` automatically; direct `uv run` does not

## Architecture

```
Frontend (vanilla JS)  ←→  FastAPI (slide_server.py)  ←→  Z.AI API (api.z.ai)
     │                           │
     └─ SSE streaming            ├─ style_bank/*.json
                                 ├─ saved_slides/*.html
                                 └─ session.json
```

### Backend (`slide_server.py`)

- **FastAPI** app on port 2828 with CORS enabled
- Serves `index.html` at `/`, static files under `/frontend`
- All generation goes through `POST /command` which streams SSE to the frontend
- Uploads go to Z.AI's file endpoint (`ZAI_FILES_ENDPOINT`), not local disk
- Generated HTML is saved to `saved_slides/` with timestamped filenames

### Frontend (`frontend/app.js` + `index.html`)

- Vanilla JS, no framework
- Communicates via `fetch()` with SSE parsing
- Preview rendered in a sandboxed `<iframe>` via `srcdoc`
- Supports keyboard shortcuts: `Enter` to send, `Shift+Enter` for newline, `Ctrl+S` for PNG export, arrow keys for slide navigation

### MCP Wrapper (`mcp_wrapper.py`)

- Standalone CLI tool that speaks JSON-RPC over stdin/stdout
- Used externally as an MCP server; not wired into the main app
- Can be ignored for most Zlides development

## API Integration Deep Dive

### Z.AI Streaming Format

The Z.AI API returns **SSE** with `data:` lines. Each line is a JSON chunk. The structure is deeply nested:

```
chunk.choices[0].messages[] → each message has:
  - phase: "thinking" | "answer"
  - content: list of {type, ...}
    - type="text" → thinking/answer text
    - type="object" → tool call output (HTML chunks)
```

**Critical**: The agent outputs HTML via **tool calls** (`type: "object"`), not text. These come in small chunks (~100 chars) with `tool_name` and `position` arrays. The server must:
1. Collect all `type: "object"` chunks into `tool_html_pages`
2. Sort by `position` (tuple of ints)
3. Concatenate and decode `\n` → newline, `\\"` → `"`
4. Fall back to text extraction if no tool outputs found

### HTML Extraction Pipeline (in order of preference)

1. `combine_tool_pages(tool_html_pages)` — concatenate tool outputs
2. `extract_final_html(last_valid_chunk)` — parse the final SSE chunk
3. `clean_agent_output("\n".join(answer_texts))` — clean markdown fences from text
4. Reverse-scan all chunks for any HTML
5. `wrap_in_slide_html(plain_text)` — last-resort markdown→HTML wrapper

### Conversation State

- `session.json` stores `conversation_id` with a **30-minute TTL**
- Edit requests (detected by keywords: `edit`, `change`, `modify`, `update`, `fix`, `adjust`, `reformat`, `layout`) **continue** the conversation
- Non-edit requests start fresh (`conversation_id` cleared)
- **Thinking is disabled for edit requests** (`thinking.type = "disabled"`) to reduce latency

### Request Payload Tuning

The `/command` endpoint sets several non-obvious parameters:
- `max_tokens: 65000` — caps at ~1/3 of 200k context to prevent crashes
- `ctrl_step: 0.7` — whitespace control; balances readability vs richness
- `response_format: {"type": "json_object"}` — forces structured output
- `extra_body.cache_salt` — random token per request for cache busting
- `tool_stream: True` — enables tool call streaming

## Style Bank System

Styles are JSON files in `style_bank/` loaded dynamically at runtime.

### Style Pack Schema

```json
{
  "id": "gitenglish",
  "name": "gitEnglish Hub",
  "brand_png": "gitenglish-brand.png",
  "preview_colors": ["#262424", "#ff6600"],
  "prompt_hint": "...instructions for the AI agent...",
  "css": { "bg": "#262424", "card": "#383535", ... },
  "fonts": { "body": "'Inter', sans-serif", "heading": "'Raleway', sans-serif" },
  "card_style": "neumorphic",
  "print_css": "@media print { ... }"
}
```

**Key behavior**: `prompt_hint` is injected into the system prompt. The AI generates inline CSS based on these instructions. There is no runtime CSS injection — the AI must bake styles into the HTML it generates.

### Formats vs Styles

These are **orthogonal**:
- **Format** (`slides`, `poster`, `worksheet`, `report`, `rr`) → controls structure via system prompt
- **Style** (`auto`, `gitenglish`, `clean`, etc.) → controls visual look via prompt hint

### Print CSS

If a style pack has `print_css`, it gets injected into the final HTML:
- Before `</head>` if present
- Otherwise appended after the last `</style>`

## Frontend SSE Event Types

The frontend expects these `data:` event types from `/command`:

| Type | Meaning |
|------|---------|
| `thinking` | Agent's reasoning text (streamed live) |
| `answer` | Final answer text (not HTML) |
| `slide_page` | HTML chunk from tool call (live preview update) |
| `final_html` | Complete HTML document (end of stream) |
| `error` | Something went wrong |

The frontend maintains `liveHtmlChunks` and re-renders the iframe on each `slide_page` event for a live preview effect.

## File Upload

- `POST /upload` accepts files up to 100MB
- Allowed: `pdf`, `doc`, `xlsx`, `ppt`, `txt`, `jpg`, `jpeg`, `png`, `gif`, `webp`
- Files are forwarded to Z.AI's file endpoint; the returned `id` can be referenced in subsequent requests via `file_ids`
- Upload type `"style"` queues the file ID as `pending_style_image` for the next generation

## Testing

- Uses `pytest` with `fastapi.testclient.TestClient`
- Tests cover: health, upload validation, style CRUD, HTML extraction, prompt building
- No external API calls in tests — all backend logic is tested with mocked data
- Run: `pytest tests/test_slide_server.py`

## Gotchas & Non-Obvious Patterns

### `main.py` is a decoy
The project root has `main.py` with a stub `main()` function. It is **not used**. The actual entry point is `slide_server.py`.

### Port binding with socket reuse
`slide_server.py` creates a raw socket with `SO_REUSEADDR` before starting uvicorn to ensure clean restarts. `launch.sh` aggressively kills processes on port 2828.

### Edit request keyword detection
The list of edit keywords is hardcoded in `slide_server.py:534-546`. Adding a new synonym requires updating this list.

### HTML chunk decoding
API responses escape newlines and quotes in tool outputs. The server decodes `\\n` → `\n` and `\\"` → `"` in **two places**:
1. `combine_tool_pages()` for the final assembly
2. Inline in the SSE generator for each chunk before yielding to frontend

### `clean_agent_output()` edge cases
- Strips markdown fences (```html ... ```)
- Extracts HTML from mixed text by scanning for `<!DOCTYPE`, `<html`, `<div`, `<section`, `<style`
- Returns empty string if no HTML found, triggering the fallback wrapper

### Session store mutation
`session_store` is a module-level dict. The `/style` and `/pointer` endpoints mutate it directly (queueing for next `/command`). This is not thread-safe but acceptable for single-user local use.

### `slide_type` vs `format`, `theme` vs `style`
The `ChatRequest` model accepts both old (`slide_type`, `theme`) and new (`format`, `style`) field names. The `/command` endpoint maps old to new for backward compatibility.

### Frontend double-click protection
`genBtn.disabled = true` immediately on `sendCommand()`, and the button has an early return if `genBtn.disabled`. The stop button uses `AbortController` to cancel the fetch.

### Iframe scroll preservation
During live streaming, the frontend tries to preserve scroll position by updating `contentDocument.body.innerHTML` instead of resetting `srcdoc`. Falls back to `srcdoc` on cross-origin errors.

## Directory Structure

```
zlides/
├── slide_server.py          # Main FastAPI app (ENTRY POINT)
├── main.py                  # Stub — ignore
├── mcp_wrapper.py           # Standalone MCP tool
├── launch.sh                # Launcher script
├── index.html               # Main frontend
├── frontend/
│   ├── app.js               # Frontend logic
│   └── styles.css           # Frontend styles
├── style_bank/              # Style packs (JSON)
│   ├── gitenglish.json
│   ├── clean.json
│   ├── dark.json
│   └── minimal.json
├── saved_slides/            # Generated HTML files (gitignored)
├── assets/                  # Brand images
├── tests/
│   └── test_slide_server.py
├── pyproject.toml           # uv project config
├── uv.lock                  # uv lockfile
├── requirements.txt         # Fallback deps (minimal)
├── .env                     # Secrets (gitignored)
└── session.json             # Conversation state (gitignored)
```

## Dependencies

Core: `fastapi`, `uvicorn`, `httpx`, `pydantic`, `pyjwt`, `python-dotenv`, `python-multipart`, `zhipuai`
Dev: `pytest`

Frontend uses CDN-loaded `html2canvas` for PNG export; no build step.
