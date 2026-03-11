from flask import Flask
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# ── Register Blueprints (routes) ──────────────────────────
from routes.poll_routes import poll_bp
from routes.vote_routes import vote_bp
from routes.admin_routes import admin_bp

app.register_blueprint(poll_bp)
app.register_blueprint(vote_bp)
app.register_blueprint(admin_bp)

# ── Run the app ───────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)