"""Exercise the actual optional SDK using HTTP fixtures, never a live endpoint."""
import json
from pathlib import Path
import pytest
from typer.testing import CliRunner

openai = pytest.importorskip("openai")
httpx = pytest.importorskip("httpx")

from agentbench.cli import app
from agentbench.context import AgentContext
from examples.support_agent.llm_agent import LLMSettings, llm_agent, run_tool_loop
from examples.support_agent.tools import support_tools


async def test_real_sdk_roundtrip_without_network():
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        output = ([{"type": "function_call", "id": "fc_1", "call_id": "call_1", "name": "get_order", "arguments": '{"order_id":"missing"}'}]
                  if len(requests) == 1 else [{"type": "message", "id": "msg_1", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": '{"status":"not_found"}', "annotations": []}]}])
        return httpx.Response(200, json={"id": f"resp_{len(requests)}", "object": "response", "created_at": 1,
            "status": "completed", "model": "fixture", "output": output,
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}})

    async with openai.AsyncOpenAI(api_key="test-fixture-only", max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))) as client:
        ctx = AgentContext({"orders": {}}, support_tools)
        result = await run_tool_loop({"order_id": "missing"}, ctx, client, LLMSettings(model="fixture"))
    assert result.output == {"status": "not_found"}
    assert result.usage["total_tokens"] == 30
    assert requests[1]["input"][-1] == {"type": "function_call_output", "call_id": "call_1", "output": "null"}
    assert requests[0]["text"]["format"]["strict"] is True


def test_missing_key_fails_preflight(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        llm_agent.prepare({"model": "fixture"})


def test_dotenv_and_metadata(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=fixture-key\nOPENAI_MODEL=fixture-model\n")
    settings = llm_agent.prepare({})
    assert "api_key" not in settings and settings["model"] == "fixture-model"
    assert llm_agent.metadata(settings)["prompt_id"].startswith("policy-v1:")


def test_settings_errors_do_not_echo_credentials(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
    with pytest.raises(ValueError) as error:
        llm_agent.prepare({"model": "fixture", "api_key": "DO-NOT-LOG"})
    assert "DO-NOT-LOG" not in str(error.value)


def test_cli_marks_llm_runs_stochastic(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
    monkeypatch.setenv("OPENAI_MODEL", "fixture-model")
    from agentbench.models import AgentResponse
    async def fake_run(input, context):
        return AgentResponse(output={"status": "invalid_request"})
    monkeypatch.setattr(llm_agent, "run", fake_run)
    dataset = Path(__file__).parents[1] / "datasets/refunds.yaml"
    path = tmp_path / "result.json"
    result = CliRunner().invoke(app, ["eval", "--agent", "examples.support_agent.llm_agent:llm_agent",
        "--dataset", str(dataset), "--out", str(path)])
    assert result.exit_code == 1, result.output
    metadata = json.loads(path.read_text())["experiment"]
    assert metadata["execution_mode"] == "stochastic"
    assert metadata["model_id"] == "fixture-model"
    assert metadata["prompt_id"].startswith("policy-v1:")
    assert "fixture-key" not in path.read_text()
