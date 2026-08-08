from flask import Flask, g, request
from logging.config import dictConfig
from pathlib import Path
import os
from ..utils.id_encoding import encode_id
from ..utils import metrics
import time
import datetime

from ..utils.config import Config

def create_app():
    dictConfig({
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'default': {
                'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'stream': 'ext://flask.logging.wsgi_errors_stream',
                'formatter': 'default',
                'level': 'INFO'
            }
        },
        'root': {
            'level': 'INFO',
            'handlers': ['console']
        }
    })

    app = Flask(__name__)
    app.jinja_env.globals.update(encode_id=encode_id)

    # Set up template and static directories
    app.template_folder = str(Path(__file__).parent / 'templates')
    app.static_folder = str(Path(__file__).parent / 'static')

    from .routes import bp, config
    app.register_blueprint(bp)
    app.jinja_env.globals.update(thumbnails_enabled=config.thumbnails_enabled)

    @app.template_filter('format_duration')
    def format_duration(s):
        return time.strftime('%H:%M:%S', time.gmtime(s))

    @app.before_request
    def _start_timer():
        g._start_time = time.perf_counter()

    @app.after_request
    def _record_timer(response):
        if hasattr(g, '_start_time'):
            elapsed = time.perf_counter() - g._start_time
            metrics.record(f'route:{request.endpoint or request.path}', elapsed)
        return response

    return app
