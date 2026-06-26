from unittest.mock import patch
import pytest
import os
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from slide_server import app

    return TestClient(app)


@pytest.fixture
def mock_env_vars(monkeypatch):
    monkeypatch.setenv("Z_AI_API_KEY", "test_key.test_secret")


# ── Original tests ────────────────────────────────────────────────────────────


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["version"] == "0.2.0"


def test_upload_no_file(client):
    response = client.post("/upload")
    assert response.status_code == 422


@patch("slide_server.Z_AI_API_KEY", "mock_key")
def test_upload_invalid_file_type(client):
    fake_file = ("test.exe", b"test content", "application/octet-stream")
    response = client.post("/upload", files={"file": fake_file}, data={"type": "file"})
    assert response.status_code == 400
    assert "File type not allowed" in response.json()["detail"]


def test_command_endpoint_missing_message(client):
    response = client.post("/command", json={})
    assert response.status_code == 422


def test_style_endpoint(client):
    response = client.post("/style", json={"style": {"color": "blue"}})
    assert response.status_code == 200
    assert response.json()["status"] == "style_queued"


def test_pointer_endpoint(client):
    response = client.post("/pointer", json={"pointer": {"url": "https://example.com"}})
    assert response.status_code == 200
    assert response.json()["status"] == "pointer_queued"


def test_extract_final_html():
    from slide_server import extract_final_html

    data = {
        "choices": [
            {
                "messages": [
                    {
                        "content": [
                            {
                                "type": "object",
                                "object": {
                                    "output": "<html><body>Test content that is long enough to pass the 50 character threshold</body></html>"
                                },
                            }
                        ]
                    }
                ]
            }
        ]
    }

    result = extract_final_html(data)
    assert "<html>" in result
    assert "Test content" in result


def test_wrap_in_slide_html():
    from slide_server import wrap_in_slide_html

    content = "# Test Header\nThis is content"
    result = wrap_in_slide_html(content, "Test Slide")

    assert "<!DOCTYPE html>" in result
    assert "<h1>Test Header</h1>" in result
    assert "<p>This is content</p>" in result


def test_save_slide_to_file(tmp_path):
    from slide_server import save_slide_to_file

    html = "<html><body>Test</body></html>"
    prompt = "test prompt"

    result = save_slide_to_file(html, prompt)

    assert result.endswith(".html")
    assert os.path.exists(result)

    with open(result, "r") as f:
        saved_content = f.read()
    assert saved_content == html

    os.remove(result)


# ── v0.2.0 new tests ─────────────────────────────────────────────────────────


def test_formats_endpoint(client):
    response = client.get("/formats")
    assert response.status_code == 200
    data = response.json()
    ids = [f["id"] for f in data]
    assert "slides" in ids
    assert "poster" in ids
    assert "worksheet" in ids
    assert "rr" in ids


def test_styles_list_includes_auto(client):
    response = client.get("/styles")
    assert response.status_code == 200
    data = response.json()
    ids = [s["id"] for s in data]
    assert "auto" in ids


def test_styles_list_includes_gitenglish(client):
    response = client.get("/styles")
    data = response.json()
    ids = [s["id"] for s in data]
    assert "gitenglish" in ids


def test_get_style_detail(client):
    response = client.get("/styles/gitenglish")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "gitEnglish Hub"
    assert "#262424" in data["prompt_hint"]


def test_get_nonexistent_style(client):
    response = client.get("/styles/nonexistent-xyz")
    assert response.status_code == 404


def test_clean_agent_output_strips_fences():
    from slide_server import clean_agent_output

    raw = "```html\n<!DOCTYPE html><html><body>Hello</body></html>\n```"
    result = clean_agent_output(raw)
    assert result.startswith("<!DOCTYPE")
    assert result.endswith("</html>")
    assert "```" not in result


def test_clean_agent_output_passthrough():
    from slide_server import clean_agent_output

    raw = "<!DOCTYPE html><html><body>Hello</body></html>"
    result = clean_agent_output(raw)
    assert result == raw


def test_clean_agent_output_extracts_embedded_html():
    from slide_server import clean_agent_output

    raw = "Here is your slide:\n<!DOCTYPE html><html><body>Content here</body></html>"
    result = clean_agent_output(raw)
    assert result.startswith("<!DOCTYPE")


def test_build_system_prompt_slides_auto():
    from slide_server import build_system_prompt

    prompt = build_system_prompt("slides", "auto")
    assert "multi-slide" in prompt
    assert "presentation" in prompt


def test_build_system_prompt_gitenglish():
    from slide_server import build_system_prompt

    prompt = build_system_prompt("slides", "gitenglish")
    assert "#262424" in prompt


def test_build_system_prompt_worksheet():
    from slide_server import build_system_prompt

    prompt = build_system_prompt("worksheet", "auto")
    assert "exercises" in prompt.lower()


def test_build_system_prompt_rr():
    from slide_server import build_system_prompt

    prompt = build_system_prompt("rr", "auto")
    assert "regenerate" in prompt.lower()


def test_save_and_delete_style(client):
    response = client.post(
        "/styles/save",
        json={
            "style": {
                "id": "test-style-unit",
                "name": "Test Style",
                "prompt_hint": "Make it look like a test",
                "css": {"bg": "#ffffff"},
                "preview_colors": ["#ffffff"],
            }
        },
    )
    assert response.status_code == 200
    assert response.json()["saved"] is True
    assert response.json()["id"] == "test-style-unit"

    # Verify it appears in the list
    styles = client.get("/styles").json()
    ids = [s["id"] for s in styles]
    assert "test-style-unit" in ids

    # Get full detail
    detail = client.get("/styles/test-style-unit").json()
    assert detail["name"] == "Test Style"

    # Delete it
    del_resp = client.delete("/styles/test-style-unit")
    assert del_resp.status_code == 200

    # Verify gone
    styles2 = client.get("/styles").json()
    ids2 = [s["id"] for s in styles2]
    assert "test-style-unit" not in ids2


def test_delete_nonexistent_style(client):
    resp = client.delete("/styles/nonexistent-xyz")
    assert resp.status_code == 404


def test_combine_tool_pages():
    from slide_server import combine_tool_pages
    pages = [
        {"tool": "add_slide", "html": "<div>page3</div>", "position": [3]},
        {"tool": "insert_page", "html": "<div>page1</div>", "position": [1]},
        {"tool": "modify_page", "html": "<div>page2</div>", "position": [2]},
    ]
    res = combine_tool_pages(pages)
    assert res == "<div>page1</div><div>page2</div><div>page3</div>"


