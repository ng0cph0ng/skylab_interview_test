from flask import Flask
from api.login_api import login_bp
from api.manager_api import manager_bp
from api.monitor_api import monitor_bp
from api.storage_api import storage_bp
from api.user_api import user_bp

app = Flask(__name__)

app.register_blueprint(login_bp, url_prefix="/api")
app.register_blueprint(manager_bp, url_prefix="/api")
app.register_blueprint(monitor_bp, url_prefix="/api")
app.register_blueprint(storage_bp, url_prefix="/api")
app.register_blueprint(user_bp, url_prefix="/api")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, debug=True)
