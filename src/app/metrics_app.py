import logging
import threading
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, send_from_directory
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest
from werkzeug.serving import make_server

from ..utils import metrics

logger = logging.getLogger(__name__)


def _severity_thresholds(name: str) -> tuple[float, float]:
    """(warning_ms, error_ms) — category-aware, since 'fast' means something
    different for a DB lookup than for an ffmpeg subprocess."""
    if name.startswith("ffmpeg:"):
        return 2000, 5000
    if name.startswith("db:"):
        return 50, 250
    if name.startswith("route:"):
        return 300, 1500
    if name.startswith("video_processor:"):
        return 1000, 4000
    return 500, 2000


def _annotated_snapshot() -> dict:
    data = metrics.snapshot()
    for name, s in data.items():
        warn, err = _severity_thresholds(name)
        s['severity_p95'] = 'error' if s['p95_ms'] > err else ('warning' if s['p95_ms'] > warn else '')
        s['severity_max'] = 'error' if s['max_ms'] > err else ('warning' if s['max_ms'] > warn else '')
    return data


def create_metrics_app() -> Flask:
    """A standalone Flask app serving only the /metrics and /debug/* endpoints,
    meant to be run on its own port so operators can keep it off the public
    ingress without adding path-based blocking rules for the main app."""
    app = Flask(__name__)
    app.template_folder = str(Path(__file__).parent / 'templates')
    app.static_folder = str(Path(__file__).parent / 'static')

    @app.route("/public/<path:path>")
    def get_public(path):
        """Serve static files from the static directory."""
        return send_from_directory("static", path)

    @app.route("/debug/metrics")
    def debug_metrics():
        return render_template("metrics.html")

    @app.route("/debug/metrics/rows")
    def debug_metrics_rows():
        data = _annotated_snapshot()
        if request.args.get("format") == "json":
            return jsonify(data)
        return render_template("_metrics_rows.html", stats=data)

    @app.route("/debug/metrics/reset", methods=["POST"])
    def debug_metrics_reset():
        metrics.reset()
        return render_template("_metrics_rows.html", stats={})

    @app.route("/metrics")
    def prometheus_metrics():
        return Response(generate_latest(REGISTRY), mimetype=CONTENT_TYPE_LATEST)

    return app


def start_metrics_server(port: int, host: str = "0.0.0.0") -> threading.Thread:
    """Serve the metrics/debug endpoints on their own port in a background thread,
    separate from the main application listener."""
    app = create_metrics_app()
    server = make_server(host, port, app)
    thread = threading.Thread(target=server.serve_forever, name="metrics-server", daemon=True)
    thread.start()
    logger.info(f"Metrics server listening on {host}:{port}")
    return thread
