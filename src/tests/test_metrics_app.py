from pathlib import Path

import pytest

from src.app.metrics_app import create_metrics_app, start_metrics_server
from src.utils import metrics


@pytest.fixture(autouse=True)
def _reset_metrics():
    metrics.reset()
    yield
    metrics.reset()


@pytest.fixture
def client():
    app = create_metrics_app()
    app.testing = True
    return app.test_client()


def test_prometheus_metrics_endpoint(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert resp.content_type.startswith("text/plain")


def test_debug_metrics_dashboard_renders(client):
    resp = client.get("/debug/metrics")
    assert resp.status_code == 200
    assert b"Subclipper Metrics" in resp.data


def test_debug_metrics_rows_json_reflects_recorded_metrics(client):
    metrics.record("db:get_video", 0.01)
    metrics.record("db:get_video", 0.02)

    resp = client.get("/debug/metrics/rows?format=json")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "db:get_video" in data
    assert data["db:get_video"]["count"] == 2


def test_debug_metrics_rows_html_when_no_format(client):
    resp = client.get("/debug/metrics/rows")
    assert resp.status_code == 200
    assert resp.content_type.startswith("text/html")


def test_debug_metrics_reset_clears_metrics(client):
    metrics.record("db:get_video", 0.01)
    assert "db:get_video" in metrics.snapshot()

    resp = client.post("/debug/metrics/reset")
    assert resp.status_code == 200
    assert metrics.snapshot() == {}


def test_metrics_app_has_no_unrelated_routes(client):
    """The metrics app should only ever expose metrics/debug/static endpoints —
    it must never accidentally pick up application routes."""
    rules = {rule.rule for rule in client.application.url_map.iter_rules()}
    assert rules == {
        "/static/<path:filename>",
        "/public/<path:path>",
        "/debug/metrics",
        "/debug/metrics/rows",
        "/debug/metrics/reset",
        "/metrics",
    }


def test_main_app_routes_no_longer_define_metrics_or_debug_endpoints():
    """Regression guard: the metrics/debug routes must live only in metrics_app.py,
    not be duplicated back onto the main application blueprint.

    Reads routes.py as text rather than importing it, since importing it
    eagerly constructs Config()/SubtitleIndexer, which needs SEARCH_PATH and
    spins up non-daemon actor threads — too heavy for a unit test."""
    routes_src = (Path(__file__).parent.parent / "app" / "routes.py").read_text()
    assert '"/metrics"' not in routes_src
    assert '"/debug/metrics"' not in routes_src


def test_start_metrics_server_serves_on_given_port():
    import socket
    import time
    import urllib.request

    # Grab a free port up front so the test isn't racing another process for it.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    thread = start_metrics_server(port, host="127.0.0.1")
    assert thread.is_alive()
    assert thread.daemon

    for _ in range(20):
        try:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=0.5)
            assert resp.status == 200
            break
        except (ConnectionError, OSError):
            time.sleep(0.05)
    else:
        pytest.fail(f"metrics server never became reachable on port {port}")
