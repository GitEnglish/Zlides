# CONCERNS.md - Technical Debt & Issues

**Last Updated:** 2026-03-31

## Critical Issues

### 1. Neo4j Dependency (Remove)

| Issue | Details |
|-------|---------|
| **What:** | `neo4j` package in `pyproject.toml` but never imported |
| **Impact:** | Unnecessary dependency, bloats install |
| **Fix:** | Remove from dependencies |

### 2. Missing Error Recovery

| Issue | Details |
|-------|---------|
| **What:** | If Z.AI API fails completely, no retry logic |
| **Impact:** | User sees error, must retry manually |
| **Location:** | `slide_server.py:337-500` |

## Medium Priority

### 3. Hardcoded Agent ID

| Issue | Details |
|-------|---------|
| **What:** | `"slides_glm_agent"` hardcoded in multiple places |
| **Impact:** | Can't switch agents without code change |
| **Location:** | `slide_server.py:299`, `mcp_wrapper.py:14` |
| **Fix:** | Environment variable or config |

### 4. Session File Race Conditions

| Issue | Details |
|-------|---------|
| **What:** | `session.json` write not atomic |
| **Impact:** | Corrupted session if multiple requests overlap |
| **Location:** | `slide_server.py:83-86` |
| **Fix:** | Use file locking or sqlite |

### 5. No Request Validation Limits

| Issue | Details |
|-------|---------|
| **What:** | No max page_count enforcement (frontend allows 1-20) |
| **Impact:** | API abuse possible, cost overruns |
| **Location:** | `slide_server.py:233-242` |

## Low Priority

### 6. Inconsistent HTML Extraction

| Issue | Details |
|-------|---------|
| **What:** | 3-level fallback logic is complex |
| **Impact:** | Maintenance burden, edge cases |
| **Location:** | `slide_server.py:158-227` |
| **Fix:** | Refactor to cleaner state machine |

### 7. Frontend State Management

| Issue | Details |
|-------|---------|
| **What:** | Global variables, no state persistence |
| **Impact:** | Lost work on refresh |
| **Location:** | `index.html:215-217` |
| **Fix:** | localStorage for slide history |

### 8. No Logging

| Issue | Details |
|-------|---------|
| **What:** | Only `print()` statements for debugging |
| **Impact:** | No production observability |
| **Fix:** | Add structured logging (python-logstash or similar) |

### 9. CSS in HTML Files

| Issue | Details |
|-------|---------|
| **What:** | Inline styles in generated slides |
| **Impact:** | Can't theme consistently, large file sizes |
| **Location:** | `slide_server.py:141-155` |
| **Fix:** | CSS class-based theming (part of PLAN.md roadmap) |

## Security Considerations

| Issue | Severity | Details |
|-------|----------|---------|
| **CORS wildcard** | Medium | `allow_origins=["*"]` — open to all origins |
| **No rate limiting** | Medium | API can be abused |
| **API key in .env** | Low | Standard practice, but .env should be gitignored |
| **File upload** | Low | 100MB limit, type checking — reasonable |

## Performance

| Issue | Impact |
|-------|--------|
| **No caching** | Repeated prompts hit Z.AI API every time |
| **Streaming accumulates** | Large responses consume memory |
| **No compression** | HTML could be gzipped |

## Planned Improvements (from PLAN.md)

These are **not concerns**, but planned enhancements:

- Format system (slides, poster, worksheet, report, rr)
- Style Bank with JSON style packs
- GitEnglish branding integration
- Export to Sanity CMS (HTML fragment)

## Debt from PLAN.md

| Item | Status |
|------|--------|
| **Format system** | Not implemented — hardcoded to slides |
| **Style Bank** | Not implemented — basic theme dropdown only |
| **RR Format** | Not implemented |
| **GitEnglish branding** | Not implemented |

## Stability

| Area | Status |
|------|--------|
| **Crashes** | Rare — graceful error handling |
| **Data loss** | Possible — session corruption, no frontend persistence |
| **Recovery** | Manual — refresh page to recover |
