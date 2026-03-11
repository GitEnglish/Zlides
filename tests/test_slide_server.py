import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from slide_server import app

    return TestClient(app)


@pytest.fixture
def mock_env_vars(monkeypatch):
    monkeypatch.setenv("Z_AI_API_KEY", "test_key.test_secret")


def test_health_check(client):
    response = client.get("/")
    assert response.status_code == 200


def test_upload_no_file(client):
    response = client.post("/upload")
    assert response.status_code == 422


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


def test_extract_html_from_response():
    from slide_server import extract_html_from_response

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

    result = extract_html_from_response(data)
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
    import os

    html = "<html><body>Test</body></html>"
    prompt = "test prompt"

    result = save_slide_to_file(html, prompt)

    assert result.endswith(".html")
    assert os.path.exists(result)

    with open(result, "r") as f:
        saved_content = f.read()
    assert saved_content == html

    os.remove(result)
