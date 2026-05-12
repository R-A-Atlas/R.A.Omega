import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_module(path: Path):
    name = "prompt_backed_" + "_".join(path.relative_to(ROOT).with_suffix("").parts)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_all_materialized_prompt_backed_agents_execute():
    agent_files = sorted((ROOT / "atlas_agents").rglob("agent.py"))
    assert len(agent_files) >= 50

    for path in agent_files:
        module = _load_module(path)
        packet = module.run(query="risk, market, report", context={"ticker": "NVDA"})
        assert packet["ok"] is True, path
        assert packet["agent"]["name"], path
        assert "specialist_packet" in packet, path
        assert "output_contract" in packet["specialist_packet"], path

