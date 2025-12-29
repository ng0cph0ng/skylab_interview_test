from flask import Flask, render_template, request, redirect, url_for, session
import bcrypt

from utils.autho import login_required, admin_required

from routes.login import login_bp
from routes.client_manager import client_manager_bp
from routes.client_monitor import client_monitor_bp
from routes.client_storage import client_storage_bp

app = Flask(__name__)
app.secret_key = "bfd318dd201eea59b358a36e7537402bba47026bea5b91155a8f2edd13282bbd"


app.register_blueprint(login_bp)
app.register_blueprint(client_manager_bp)
app.register_blueprint(client_monitor_bp)
app.register_blueprint(client_storage_bp)


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route("/")
def index():
    return redirect(url_for("login.login"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
