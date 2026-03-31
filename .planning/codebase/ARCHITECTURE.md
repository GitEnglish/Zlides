# ARCHITECTURE.md - System Architecture

**Last Updated:** 2026-03-31

## Pattern

**Client-Server with AI Backend:**

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│  Browser    │◄───────►│ FastAPI      │◄───────►│  Z.AI API   │
│  (index.html│  HTTP   │  Backend     │  HTTPS  │  (GLM       │
│   + JS)     │  SSE    │ (port 2828)  │  JWT    │  Agent)     │
└─────────────┘         └──────────────┘         └─────────────┘
                              │
                              ▼
                       ┌──────────────┐
                       │ File System  │
                       │ - session.json│
                       │ - saved_slides/│
                       └──────────────┘
```

## Layers

### Frontend (`index.html`)

- **Single Page Application** (no framework)
- **Direct fetch API** to backend
- **Server-Sent Events (SSE)** for streaming responses
- **iframe-based preview** for generated slides
- **Session state:** In-memory JavaScript variables

### Backend (`slide_server.py`)

- **FastAPI app** with CORS enabled (all origins)
- **StreamingResponse** for SSE to client
- **Async httpx** for Z.AI API calls
- **In-memory session store** (synced to `session.json`)

### AI Integration

- **JWT-based auth** with Z.AI
- **SSE parsing** from streaming responses
- **Multi-stage fallback** for HTML extraction:
  1. Accumulated delta content
  2. Extract from response structure
  3. Fallback to text-to-HTML wrapper

## Data Flow

### Slide Generation Flow

```
User Input (index.html)
    │
    ▼ POST /command {message, system_prompt, page_count, ...}
    │
    ▼ FastAPI handler
    │
    ▼ Build Z.AI payload (agent_id, messages, tools, file_ids)
    │
    ▼ Generate JWT token
    │
    ▼ POST to Z.AI (stream=True)
    │
    ▼ Parse SSE chunks (async for line in response.aiter_lines())
    │   ├─ thinking phase → forward to UI
    │   ├─ answer phase → accumulate HTML
    │   └─ final_html event → complete slide
    │
    ▼ Extract/validate HTML
    │
    ├─► Save to saved_slides/
    └─► Stream to frontend (SSE)
```

### File Upload Flow

```
User selects file
    │
    ▼ POST /upload (multipart/form-data)
    │
    ▼ Validate file type/size
    │
    ▼ Upload to Z.AI files endpoint
    │
    ├─► If upload_type=style → Store file_id in session_store["pending_style_image"]
    └─► Return file ID to client
```

### Style/Pointer Queuing

```
Client sends style JSON → POST /style
    │
    ▼ Store in session_store["pending_style"]
    │
    ▼ Applied to NEXT /command request

Client sends pointer URL → POST /pointer
    │
    ▼ Store in session_store["pending_pointer"]
    │
    ▼ Applied to NEXT /command request
```

## Entry Points

| File | Purpose | invoked by |
|------|---------|------------|
| `slide_server.py` | FastAPI backend server | `launch.sh` or `uv run python slide_server.py` |
| `index.html` | Frontend UI | Browser at `http://localhost:2827/index.html` |
| `launch.sh` | Startup script (kills old processes, starts both servers) | User |
| `mcp_wrapper.py` | JSON-RPC wrapper for MCP integration | External MCP tools |

## Abstractions

### HTML Extraction (3-level fallback)

1. **Accumulated content** — Delta content from streaming chunks
2. **Response parsing** — `extract_html_from_response()` traverses nested structure
3. **Text fallback** — `extract_text_as_html()` wraps plain text in HTML
4. **Ultimate fallback** — `wrap_in_slide_html()` creates basic HTML

### Session Management

- **In-memory:** `session_store` dict
- **Persistence:** `save_session()` writes to `session.json`
- **TTL check:** `load_session()` expires after 30 minutes
- **Conversation context:** `conversation_id` for multi-turn chats

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| SSE over WebSockets | Simpler for unidirectional streaming, works with fetch API |
| iframe for slide preview | Sandboxes generated HTML/CSS from UI |
| Local file storage | No database needed, simple HTML file persistence |
| Session file instead of database | Single-user focused, simple state |
| JWT generation server-side | Z.AI requires signed tokens, can't expose API key |
