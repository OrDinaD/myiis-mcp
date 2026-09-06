import pytest
from starlette.testclient import TestClient
from myiis_mcp.server import app, mcp

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client

def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert data["mcp_endpoint"] == "/mcp"

def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "MyIIS MCP Server"
    assert "endpoints" in data

def test_mcp_initialize(client):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"},
        },
    }
    response = client.post(
        "/mcp",
        json=payload,
        headers={"accept": "application/json, text/event-stream"},
    )
    assert response.status_code == 200
    assert "event: message" in response.text
    assert '"protocolVersion":"2024-11-05"' in response.text

def test_mcp_list_tools(client):
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }
    response = client.post(
        "/mcp",
        json=payload,
        headers={"accept": "application/json, text/event-stream"},
    )
    assert response.status_code == 200
    text = response.text

    # Verify all expected tools exist
    expected_tools = [
        "get_group_schedule",
        "get_teacher_schedule",
        "get_teacher_profile",
        "search_groups",
        "search_teachers",
        "get_current_week",
    ]
    for tool_name in expected_tools:
        assert f'"{tool_name}"' in text, f"Missing tool: {tool_name}"

    # Verify readOnlyHint is true for all tools
    assert '"readOnlyHint":true' in text or '"read_only_hint":true' in text

@pytest.mark.asyncio
async def test_tool_direct_call():
    # Direct tool call through MCPServer instance
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "get_group_schedule" in tool_names
    assert "get_teacher_schedule" in tool_names
    assert "get_teacher_profile" in tool_names
    assert "get_current_week" in tool_names

    # Check annotations on get_group_schedule
    group_tool = next(t for t in tools if t.name == "get_group_schedule")
    assert group_tool.annotations is not None
    assert group_tool.annotations.read_only_hint is True
    assert group_tool.annotations.destructive_hint is False
    assert group_tool.annotations.open_world_hint is False

    # Check annotations on get_teacher_profile
    profile_tool = next(t for t in tools if t.name == "get_teacher_profile")
    assert profile_tool.annotations is not None
    assert profile_tool.annotations.read_only_hint is True


def test_widget_endpoint(client):
    response = client.get("/widget")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "БГУИР • ИИС" in response.text
    assert "window.openai" in response.text

    # Check alias
    alias_resp = client.get("/widget.html")
    assert alias_resp.status_code == 200


def test_mcp_resources_list(client):
    payload = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "resources/list",
        "params": {},
    }
    response = client.post(
        "/mcp",
        json=payload,
        headers={"accept": "application/json, text/event-stream"},
    )
    assert response.status_code == 200
    text = response.text
    assert "ui://bsuir/widget.html" in text
    assert "text/html;profile=mcp-app" in text
    assert "connectDomains" in text or "connect_domains" in text


def test_mcp_resources_read(client):
    payload = {
        "jsonrpc": "2.0",
        "id": 11,
        "method": "resources/read",
        "params": {"uri": "ui://bsuir/widget.html"},
    }
    response = client.post(
        "/mcp",
        json=payload,
        headers={"accept": "application/json, text/event-stream"},
    )
    assert response.status_code == 200
    text = response.text
    assert "ui://bsuir/widget.html" in text
    assert "БГУИР • ИИС Виджет" in text

