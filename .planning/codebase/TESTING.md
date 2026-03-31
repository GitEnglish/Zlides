# TESTING.md - Testing Practices

**Last Updated:** 2026-03-31

## Test Framework

- **pytest** 9.0.2+ (only dev dependency)
- **TestClient** from FastAPI for endpoint testing
- **No coverage tool** configured

## Test Structure

```
tests/
├── __init__.py
└── test_slide_server.py  # ~106 lines
```

## Test Categories

### 1. Health Check (`test_health_check`)

```python
def test_health_check(client):
    response = client.get("/")
    assert response.status_code == 200
```

### 2. Upload Validation (`test_upload_no_file`, `test_upload_invalid_file_type`)

- Tests 422 response for missing file
- Tests 400 response for disallowed file types (`.exe`)

### 3. Command Validation (`test_command_endpoint_missing_message`)

- Tests 422 response for empty POST to `/command`

### 4. Style/Pointer Endpoints (`test_style_endpoint`, `test_pointer_endpoint`)

- Tests 200 response
- Validates `status` field in response JSON

### 5. Helper Functions (`test_extract_html_from_response`, `test_wrap_in_slide_html`, `test_save_slide_to_file`)

- **Unit tests** for internal functions
- Use fixtures for temp directory (`tmp_path`)
- Test HTML parsing and file I/O

## Fixtures

| Fixture | Purpose |
|---------|---------|
| `client()` | Provides `TestClient(app)` for FastAPI testing |
| `mock_env_vars(monkeypatch)` | Sets `Z_AI_API_KEY` environment variable |

## What's NOT Tested

| Category | Gap |
|----------|-----|
| **Integration** | No actual Z.AI API calls tested |
| **Streaming** | SSE response parsing not tested |
| **Multi-slide** | Navigation logic not tested |
| **Session** | Session persistence not tested |
| **File upload** | Successful upload path not tested |
| **HTML export** | Frontend export functions not tested |
| **Error recovery** | Fallback HTML extraction not tested |

## Running Tests

```bash
# From project root
pytest

# With uv
uv run pytest
```

## Test Quality

| Metric | Status |
|--------|--------|
| Coverage | Unknown (no coverage tool) |
| Flakiness | Low (no external deps mocked) |
| Speed | Fast (all local) |
| Maintainability | Good (clear structure) |

## Recommendations

1. **Add coverage:** `pytest-cov` for visibility
2. **Mock httpx:** Test SSE parsing without real API calls
3. **Frontend tests:** Consider Playwright or similar for `index.html`
4. **Integration tests:** Test against Z.AI sandbox if available
5. **Error scenarios:** Test timeout, invalid JWT, API errors
