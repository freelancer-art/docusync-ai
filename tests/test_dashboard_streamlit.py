from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_dashboard_renders_auth_workflow():
    dashboard_path = Path(__file__).resolve().parents[1] / "app" / "dashboard.py"
    app = AppTest.from_file(dashboard_path, default_timeout=15).run()

    assert not app.exception
    assert any("DocuSync AI Portal" in title.value for title in app.title)
    assert app.radio[0].options == ["Sign In", "Register New CA Firm", "Register Client"]
