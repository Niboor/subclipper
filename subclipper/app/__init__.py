from flask import Flask
from logging.config import dictConfig
from pathlib import Path

def create_app():
    dictConfig({
        'version': 1,
        'formatters': {'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        }},
        'handlers': {'wsgi': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://flask.logging.wsgi_errors_stream',
            'formatter': 'default'
        }},
        'root': {
            'level': 'INFO',
            'handlers': ['wsgi']
        }
    })
    
    app = Flask(__name__)
    
    # Set up template and static directories
    app.template_folder = str(Path(__file__).parent / 'templates')
    app.static_folder = str(Path(__file__).parent / 'static')
    
    from .routes import bp
    app.register_blueprint(bp)
    
    return app 