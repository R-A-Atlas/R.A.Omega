# Document export smoke tests (optional WeasyPrint / OpenAI)

from pathlib import Path

import pytest


def test_pptx_and_xlsx_minimal_envelope(tmp_path: Path):
    from atlas_export.build_deck import write_query_envelope_pptx
    from atlas_export.build_workbook import write_query_envelope_xlsx

    d = {
        "query": "Analyze NVDA",
        "parsed_query": {"tickers": ["NVDA"]},
        "final_report": {
            "ticker": "NVDA",
            "tldr": "Test",
            "executive_summary": "Ex",
            "trade_plan": {"entry": "100"},
        },
        "tldr": "T",
        "trader_memo": "M",
        "scenarios": [{"label": "Base", "probability": 0.5, "trigger": "", "outcome": ""}],
    }
    p1 = write_query_envelope_pptx(d, tmp_path / "n.pptx")
    p2 = write_query_envelope_xlsx(d, tmp_path / "n.xlsx")
    assert p1.is_file() and p1.stat().st_size > 1000
    assert p2.is_file() and p2.stat().st_size > 500


def test_docx_minimal_envelope(tmp_path: Path):
    from atlas_export.build_docx import write_query_envelope_docx

    d = {
        "query": "Give me everything on BlackRock in a Word document",
        "_output_mode": "document",
        "parsed_query": {"intent_route": "DOCUMENT_GENERATION"},
        "final_report": {
            "company_name": "BlackRock",
            "executive_summary": "BlackRock is a global asset manager.",
            "company_overview": "It provides asset management and investment technology.",
            "key_risks": ["Market cycle risk", "Fee compression"],
        },
        "tldr": "BlackRock is an asset-management scale leader.",
    }
    p = write_query_envelope_docx(d, tmp_path / "n.docx")
    assert p.is_file() and p.stat().st_size > 1000
    assert p.read_bytes().startswith(b"PK")


def test_text_markdown_and_csv_minimal_envelope(tmp_path: Path):
    from atlas_export.build_text import write_query_envelope_csv, write_query_envelope_text

    d = {
        "query": "Give me an audit report as markdown",
        "final_report": {
            "executive_summary": "The system is healthy.",
            "key_risks": ["Missing production keys"],
        },
        "tldr": "System healthy with production-key follow-up.",
    }
    txt = write_query_envelope_text(d, tmp_path / "n.txt", fmt="txt")
    md = write_query_envelope_text(d, tmp_path / "n.md", fmt="md")
    csv = write_query_envelope_csv(d, tmp_path / "n.csv")
    assert txt.read_text(encoding="utf-8").startswith("R.A. Omega Intelligence Report")
    assert md.read_text(encoding="utf-8").startswith("# R.A. Omega Intelligence Report")
    assert "section,content" in csv.read_text(encoding="utf-8").splitlines()[0]


def test_html_and_agent_xlsx_minimal_envelope(tmp_path: Path):
    from atlas_agents.documents.comparison.html_print_agent import generate_html
    from atlas_agents.documents.excel.excel_agent import generate_excel

    d = {
        "query": "Analyze NVDA",
        "parsed_query": {"tickers": ["NVDA"]},
        "final_report": {"ticker": "NVDA", "tldr": "Test", "trade_plan": {"entry": "100"}},
        "tldr": "T",
    }
    html_path = generate_html(d, tmp_path / "n.html")
    xlsx_path = generate_excel(d, tmp_path / "n.xlsx")
    assert html_path.is_file()
    assert "<html" in html_path.read_text(encoding="utf-8").lower()
    assert xlsx_path.is_file() and xlsx_path.stat().st_size > 500


def test_export_html_and_excel_endpoints_return_files(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("ATLAS_DISABLE_AUTH", "true")
    import api_server

    c = TestClient(api_server.app)
    d = {
        "query": "Analyze NVDA",
        "parsed_query": {"tickers": ["NVDA"]},
        "final_report": {"ticker": "NVDA", "tldr": "Test"},
        "tldr": "T",
    }
    html_r = c.post("/export/html", json=d)
    excel_r = c.post("/export/excel", json=d)
    assert html_r.status_code == 200
    assert "text/html" in html_r.headers["content-type"]
    assert excel_r.status_code == 200
    assert "spreadsheetml.sheet" in excel_r.headers["content-type"]


def test_export_docx_endpoint_returns_file(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("ATLAS_DISABLE_AUTH", "true")
    import api_server

    c = TestClient(api_server.app)
    d = {
        "query": "Give me everything on BlackRock in a Word document",
        "_output_mode": "document",
        "parsed_query": {"intent_route": "DOCUMENT_GENERATION"},
        "final_report": {
            "company_name": "BlackRock",
            "executive_summary": "BlackRock is a global asset manager.",
            "company_overview": "It provides asset management and investment technology.",
        },
        "tldr": "BlackRock is an asset-management scale leader.",
    }
    r = c.post("/export/docx", json=d)
    assert r.status_code == 200
    assert "wordprocessingml.document" in r.headers["content-type"]
    assert r.content.startswith(b"PK")


def test_export_lightweight_file_endpoints_return_files(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("ATLAS_DISABLE_AUTH", "true")
    import api_server

    c = TestClient(api_server.app)
    d = {
        "query": "Give me an audit report as CSV",
        "final_report": {"executive_summary": "The system is healthy."},
        "tldr": "Healthy.",
    }
    checks = {
        "/export/txt": "text/plain",
        "/export/md": "text/markdown",
        "/export/csv": "text/csv",
    }
    for endpoint, content_type in checks.items():
        r = c.post(endpoint, json=d)
        assert r.status_code == 200
        assert content_type in r.headers["content-type"]
        assert len(r.content) > 20


def test_export_pdf_endpoint_returns_file_with_fallback(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("ATLAS_DISABLE_AUTH", "true")
    import api_server

    c = TestClient(api_server.app)
    d = {
        "query": "Analyze NVDA",
        "parsed_query": {"tickers": ["NVDA"]},
        "final_report": {"ticker": "NVDA", "tldr": "Test"},
        "tldr": "T",
    }
    r = c.post("/export/pdf", json=d)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_pdf_export_works_without_weasyprint_native_stack(tmp_path: Path):
    from atlas_export.pdf_render import write_query_envelope_pdf

    d = {
        "query": "Analyze NVDA",
        "parsed_query": {"tickers": ["NVDA"]},
        "final_report": {"ticker": "NVDA", "tldr": "x"},
        "tldr": "T",
    }
    p = write_query_envelope_pdf(d, tmp_path / "n.pdf")
    assert p.is_file()
    assert p.read_bytes().startswith(b"%PDF")


def test_tts_no_provider_returns_503(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("ATLAS_DISABLE_AUTH", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "")

    import api_server

    c = TestClient(api_server.app)
    r = c.post("/tts", json={"text": "Short test phrase."})
    assert r.status_code == 503
