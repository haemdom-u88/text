import os
from datetime import datetime

from flask import Blueprint, jsonify, render_template, send_from_directory

import app_state

bp = Blueprint("core", __name__)


@bp.route("/")
def index():
    try:
        return send_from_directory(os.path.abspath("."), "index.html")
    except Exception:
        return render_template("index.html")


@bp.route("/assets/echarts.min.js")
def echarts_min():
    try:
        return send_from_directory(os.path.join(os.path.abspath("."), "src"), "echarts.min.js")
    except Exception:
        return send_from_directory(os.path.join(os.path.abspath("."), "static", "lib"), "echarts.min.js")


@bp.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "initialized": app_state.is_initialized,
        "timestamp": datetime.now().isoformat()
    })


@bp.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory("static", filename)


@bp.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join("static"), "favicon.ico")
