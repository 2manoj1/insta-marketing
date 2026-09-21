"""
Unit tests for the Model Context Protocol (MCP) JSON-RPC 2.0 server.
"""
import pytest
from src.mcp.server import mcp_server, MCP_TOOLS_MANIFEST


@pytest.mark.anyio
async def test_mcp_initialize():
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    }
    resp = await mcp_server.handle_jsonrpc_request(req)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert resp["result"]["serverInfo"]["name"] == "insta-marketing-mcp"
    assert "tools" in resp["result"]["capabilities"]


@pytest.mark.anyio
async def test_mcp_tools_list():
    req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
    }
    resp = await mcp_server.handle_jsonrpc_request(req)
    assert resp["id"] == 2
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "calculate_rate_card" in tool_names
    assert "verify_contact_info" in tool_names
    assert "deep_brand_enrich" in tool_names
    assert "generate_bespoke_pitch" in tool_names
    assert "okf_query_knowledge" in tool_names


@pytest.mark.anyio
async def test_mcp_tools_call_calculate_rate_card():
    req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "calculate_rate_card",
            "arguments": {
                "followers_count": 50000,
                "niche": "Tech",
            }
        }
    }
    resp = await mcp_server.handle_jsonrpc_request(req)
    assert resp["id"] == 3
    assert resp["result"]["isError"] is False
    content_text = resp["result"]["content"][0]["text"]
    assert "Mid-Tier Influencer" in content_text or "Micro" in content_text
    assert "ugc_video_30d_ads" in content_text


@pytest.mark.anyio
async def test_mcp_tools_call_verify_contact():
    req = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "verify_contact_info",
            "arguments": {
                "email": "partnerships@brand.com",
                "phone": "9876543210",
            }
        }
    }
    resp = await mcp_server.handle_jsonrpc_request(req)
    assert resp["id"] == 4
    content_text = resp["result"]["content"][0]["text"]
    assert "confidence_score" in content_text
    assert "+91 98765 43210" in content_text


@pytest.mark.anyio
async def test_mcp_tools_call_verify_brand_instagram_page():
    req = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "verify_brand_instagram_page",
            "arguments": {
                "brand_handle": "@snitch.co.in",
            }
        }
    }
    resp = await mcp_server.handle_jsonrpc_request(req)
    assert resp["id"] == 5
    assert resp["result"]["isError"] is False
    content_text = resp["result"]["content"][0]["text"]
    assert "Snitch" in content_text
    assert "collab@" in content_text
