"""Streamlit UI smoke checks for the live research dashboard."""
from pathlib import Path
from streamlit.testing.v1 import AppTest
from src.demo import demo_result
from src.report import render_report


def test_streamlit_starts_without_api_key_and_exposes_only_live_research_controls(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    app = AppTest.from_file(Path(__file__).parents[1] / "app.py").run(timeout=60)
    assert not app.exception
    assert not app.radio
    assert not any(box.label == "Research focus" for box in app.selectbox)
    assert any(box.label == "Company or ticker (optional)" for box in app.text_input)
    assert any(button.label.startswith("Start Research") for button in app.button)
    assert any(element.label == "Open checked sample report" for element in app.expander)


def test_report_download_is_present_and_contains_current_result():
    result = demo_result()
    report = render_report(result)
    assert "DEMO DATA" in report and result.question in report
    app = AppTest.from_file(Path(__file__).parents[1] / "app.py")
    app.session_state["result"] = result
    app.run(timeout=60)
    assert not app.exception
    assert any(button.label == "↓  Download report" for button in app.get("download_button"))
