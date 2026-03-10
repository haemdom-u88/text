import logging
import os
import sys
import time

from dotenv import load_dotenv
from flask import Flask, g, request
from flask_cors import CORS

import app_state
from routes import batch, core, extract, graph, llm

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))
load_dotenv()

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/app.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logging.addLevelName(logging.DEBUG, "调试")
logging.addLevelName(logging.INFO, "信息")
logging.addLevelName(logging.WARNING, "警告")
logging.addLevelName(logging.ERROR, "错误")
logging.addLevelName(logging.CRITICAL, "严重")

werkzeug_logger = logging.getLogger("werkzeug")
werkzeug_logger.setLevel(logging.CRITICAL)
werkzeug_logger.disabled = True
for handler in logger.handlers:
    if handler not in werkzeug_logger.handlers:
        werkzeug_logger.addHandler(handler)
werkzeug_logger.propagate = False

flask_logger = logging.getLogger("flask")
flask_logger.setLevel(logging.INFO)
for handler in logger.handlers:
    if handler not in flask_logger.handlers:
        flask_logger.addHandler(handler)
flask_logger.propagate = False

app = Flask(__name__)
CORS(app)

app.register_blueprint(core.bp)
app.register_blueprint(extract.bp)
app.register_blueprint(batch.bp)
app.register_blueprint(graph.bp)
app.register_blueprint(llm.bp)


@app.before_request
def before_request():
    app_state.set_request_ip(request.remote_addr or "unknown")
    if not app_state.is_initialized:
        app_state.initialize_services()
    try:
        g._start_time = time.perf_counter()
    except Exception:
        pass


@app.after_request
def after_request(response):
    try:
        duration_ms = None
        if hasattr(g, "_start_time"):
            duration_ms = (time.perf_counter() - g._start_time) * 1000
        logger.info(
            "Request %s %s %s -> %s%s",
            request.remote_addr,
            request.method,
            request.path,
            response.status_code,
            f" ({duration_ms:.1f}ms)" if duration_ms is not None else ""
        )
    except Exception:
        pass
    return response


if __name__ == "__main__":
    app.run(debug=False)
