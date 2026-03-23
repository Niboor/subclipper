from flask import Flask
from logging.config import dictConfig
from pathlib import Path
import os
from ..utils.id_encoding import encode_id
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
    
    from .routes import bp
    app.register_blueprint(bp)

    @app.template_filter('format_duration')
    def format_duration(s):
        return time.strftime('%H:%M:%S', time.gmtime(s))
    
    return app
