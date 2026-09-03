"""Flask application entry point.

Run with:  python app.py
Serves on 127.0.0.1:5000 by default; set SSCM_HOST=0.0.0.0 for intranet
deployment (see config.py).
"""
from flask import Flask

import config
from routes.dashboard import dashboard_bp
from routes.api import api_bp
from routes.optimization import optimization_bp


def create_app():
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(optimization_bp, url_prefix="/api")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
