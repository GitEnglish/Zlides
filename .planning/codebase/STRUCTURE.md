# STRUCTURE.md - Directory Structure

**Last Updated:** 2026-03-31

## Directory Layout

```
zlides/
├── .planning/              # GSD project planning
│   ├── config.json        # Workflow settings (YOLO mode)
│   └── codebase/          # This directory
├── saved_slides/          # Generated slide HTML files
├── tests/                 # Pytest tests
│   ├── __init__.py
│   └── test_slide_server.py
├── .venv/                 # Python virtual environment
├── .env                   # Environment variables (Z_AI_API_KEY)
├── .gitignore             # Git exclusions
├── .python-version        # Python 3.11
├── index.html             # Frontend UI (entire app in one file)
├── launch.sh              # Startup script
├── main.py                # Placeholder entry point
├── mcp_wrapper.py         # MCP JSON-RPC wrapper
├── pyproject.toml         # UV project config
├── slide_server.py        # FastAPI backend (main server)
├── test_payload.py        # Test script for Z.AI API
├── uv.lock                # UV dependency lock file
├── PLAN.md                # Planned features (formats, style bank)
├── agent-hub-plan.md      # Agent integration plan
└── assets/                # Static assets (branding, etc.)
```

## Key Files

### Core Application

| File | Lines | Purpose |
|------|-------|---------|
| `slide_server.py` | ~558 | FastAPI backend, Z.AI integration, SSE streaming |
| `index.html` | ~400+ | Frontend UI (HTML/CSS/JS all inline) |

### Configuration

| File | Purpose |
|------|---------|
| `.env` | Z.AI API key (`Z_AI_API_KEY=api_key.secret`) |
| `pyproject.toml` | Python dependencies, project metadata |
| `launch.sh` | Process management, port cleanup, server startup |

### Testing

| File | Purpose |
|------|---------|
| `tests/test_slide_server.py` | FastAPI endpoint tests, helper function tests |

### Tools

| File | Purpose |
|------|---------|
| `mcp_wrapper.py` | JSON-RPC wrapper for MCP tool integration |
| `test_payload.py` | Manual Z.AI API testing |

### Planning

| File | Purpose |
|------|---------|
| `PLAN.md` | Upgrade plan: Format system, Style Bank, GitEnglish integration |
| `agent-hub-plan.md` | Agent hub integration notes |

## Naming Conventions

- **Python:** `snake_case` for functions/variables
- **API endpoints:** `/kebab-case` (`/upload`, `/command`, `/style`, `/pointer`)
- **JavaScript:** `camelCase` for variables/functions
- **HTML IDs:** `kebab-case` (`slide-frame`, `editor-toolbar`)
- **Files:** `snake_case.py` for Python modules

## Generated Artifacts

| Location | Pattern | Purpose |
|----------|---------|---------|
| `saved_slides/` | `slide_YYYYMMDD_HHMMSS_{prompt}.html` | Auto-saved generated slides |

## Session Files

| File | Purpose | TTL |
|------|---------|-----|
| `session.json` | Conversation ID, pending styles/pointers | 30 minutes |

## Frontend Structure (index.html)

```
<head>
  - Styles (CSS for sidebar, preview, controls)
  - html2canvas CDN
</head>
<body>
  - #sidebar (chat history, input controls)
  - #editor-area (preview toolbar, iframe, navigation)
  - <script> (all application logic)
    - State variables (currentSlides, currentSlideIdx)
    - UI update functions
    - SSE handling
    - Export functions (PNG, HTML)
</body>
```

## Important Locations

| Location | Why it matters |
|----------|----------------|
| `slide_server.py:233-242` | `ChatRequest` model — defines API contract |
| `slide_server.py:262-501` | `/command` endpoint — core generation logic |
| `slide_server.py:158-192` | `extract_html_from_response()` — HTML parsing |
| `index.html:249-350` | `sendCommand()` — frontend SSE handling |
| `PLAN.md` | Future roadmap (formats, style bank, RR format) |
