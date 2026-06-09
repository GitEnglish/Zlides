# INTEGRATIONS.md - External Integrations

**Last Updated:** 2026-03-31

## Z.AI API (Zhipu AI)

**Purpose:** Core slide generation via AI agent

### Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/agents` | POST | Stream slide generation |
| `/api/paas/v4/files` | POST | Upload files (images, docs) as references |

### Authentication

- **Type:** JWT Bearer tokens
- **Algorithm:** HS256 with `sign_type: SIGN` header
- **Token payload:**
  ```json
  {
    "api_key": "...",
    "exp": <timestamp_ms>,
    "timestamp": <timestamp_ms>
  }
  ```
- **Source:** `Z_AI_API_KEY` environment variable (format: `api_key.secret`)

### Agent Configuration

- **Agent ID:** `slides_glm_agent`
- **Streaming:** Enabled (SSE responses)
- **Web Search:** Optional tool, enabled via `tools: [{"type": "web_search", "web_search": {"enable": true}}]`

### Request Flow

1. Client sends prompt to `/command` endpoint
2. Server generates JWT token from API key
3. Server forwards request to Z.AI with conversation context
4. Z.AI streams response via Server-Sent Events (SSE)
5. Server parses SSE chunks and extracts HTML
6. HTML is saved to `saved_slides/` directory

### File Upload

- Files uploaded to Z.AI get a file ID
- File ID is attached to next generation via `file_ids` parameter
- Used for style references and content inputs

### Response Parsing

Complex nested structure in Z.AI responses:
- `choices[0].messages[]` array
- Each message has `content` (array or dict)
- Content items have `type: "text"` or `type: "object"`
- Object items contain `output` field with HTML

### Session Management

- **Conversation ID:** Tracked in `session.json` for multi-turn conversations
- **TTL:** 30 minutes
- **Context:** Only used for edit/modify requests (detected by keywords)

## Frontend CDNs

| Library | Purpose | CDN |
|---------|---------|-----|
| html2canvas | PNG export | `https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js` |

## No Database

- No persistent database (Neo4j dependency is unused)
- Session stored in local `session.json` file
- Generated slides saved as HTML files in `saved_slides/` directory
