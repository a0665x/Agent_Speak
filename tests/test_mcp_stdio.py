from __future__ import annotations

import asyncio
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[1]


def test_stdio_mcp_initializes_and_lists_public_tools() -> None:
    async def exercise() -> dict[str, dict]:
        parameters = StdioServerParameters(
            command=str(ROOT / "scripts" / "run_mcp.sh"),
            args=[],
            env={"AGENT_SPEAK_URL": "http://127.0.0.1:8765"},
        )
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await asyncio.wait_for(session.initialize(), timeout=10)
                result = await asyncio.wait_for(session.list_tools(), timeout=10)
                return {tool.name: tool.inputSchema for tool in result.tools}

    schemas = asyncio.run(exercise())
    assert set(schemas) == {
        "status",
        "capabilities",
        "list_audio_devices",
        "microphone_smoke",
        "listen_once",
        "speak",
    }
    for sensitive_tool in ("microphone_smoke", "listen_once", "speak"):
        assert "user_confirmed" in schemas[sensitive_tool]["properties"]
