"""
app.py — Secure Flask app with JWT-based authentication

This file defines the main application factory `create_app()`, which:
- Sets up secure JWT authentication using short-lived access tokens and longer-lived refresh tokens
- Configures CORS to allow cross-origin requests (e.g. from a frontend)
- Provides a `/login` route for token generation
- Provides a `/refresh` route to renew access tokens
- Secures routes using @jwt_required()
- Loads MongoDB-connected routes (e.g. /stores) from external modules via Blueprint

REQUIREMENTS (install with pip):
    pip install flask flask-cors flask-jwt-extended bcrypt

DEPENDENCIES:
    - This app expects a dictionary `env_data` passed into `create_app()` with:
        - "FLASK_USER" → the username (string)
        - "FLASK_PASSWORD" → bcrypt-hashed password (string)
        - "JWT_SECRET_KEY" → a secret string to sign JWT tokens
        - "db" → a pymongo database object for CRUD (injected from main.py)
"""

# Password hashing/checking
import bcrypt

# Flask core functions
from flask import Flask, request, jsonify

# CORS allows frontend (like React) to call this backend securely
from flask_cors import CORS

# JWT tools for issuing and protecting routes
from flask_jwt_extended import (
    JWTManager,                # Initializes JWT support in Flask
    create_access_token,       # Used to create short-lived access tokens
    create_refresh_token,      # Used to create long-lived refresh tokens
    jwt_required,              # Decorator to secure endpoints with JWT
    get_jwt_identity           # Gets the user identity from a valid token
)


def create_app(env_data):
    # Create the Flask app instance
    app = Flask(__name__)

    # Set the secret key used to sign JWTs
    app.config["JWT_SECRET_KEY"] = env_data["JWT_SECRET_KEY"]

    # Token lifetimes
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = 86400  # 900  IS 15MIN     # ⏱ Access token = 1DAY
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = 86400   # 🔁 Refresh token = 1 day

    # Enable Cross-Origin Resource Sharing (for browser clients)
    CORS(app)

    # Enable JWT functionality
    JWTManager(app)

    # Load credentials from env_data
    valid_user = env_data["FLASK_USER"]          # Username allowed to login
    valid_pw_hash = env_data["FLASK_PASSWORD"]   # Bcrypt-hashed password

    # Public route to check if the API is alive
    @app.route("/")
    def index():
        return jsonify(msg="Flask API is running")

    # Login route: returns access + refresh tokens on success
    @app.route("/login", methods=["POST"])
    def login():
        # Get JSON body from the request
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")

        # Validate user/pass (hash check)
        if username != valid_user or not bcrypt.checkpw(password.encode(), valid_pw_hash.encode()):
            return jsonify(msg="Invalid credentials"), 401

        # Generate JWTs
        access_token = create_access_token(identity=username)
        refresh_token = create_refresh_token(identity=username)

        return jsonify(
            access_token=access_token,
            refresh_token=refresh_token,
            info="⚠️ Access token valid for 1 minute. Use refresh token to renew."
        )

    # Refresh route: requires valid refresh token
    @app.route("/refresh", methods=["POST"])
    @jwt_required(refresh=True)
    def refresh():
        # Get current user from the valid refresh token
        identity = get_jwt_identity()

        # Issue a new access token (same identity)
        new_token = create_access_token(identity=identity)
        return jsonify(access_token=new_token)

    # Example protected route
    @app.route("/protected", methods=["GET"])
    @jwt_required()  # This will reject requests without a valid access token
    def protected():
        user = get_jwt_identity()
        return jsonify(msg=f"Hello {user}, access granted")

    # --- Modular Route Setup ---
    # Load secure routes from routes/stores.py using Flask Blueprints
    from routes.stores import stores_bp, init_store_routes
    init_store_routes(env_data["db"])           # Pass the database to the routes
    app.register_blueprint(stores_bp)           # Register the Blueprint with the Flask app
    from routes.users import users_bp, init_user_routes
    init_user_routes(env_data["db"])           
    app.register_blueprint(users_bp)   
    from routes.super_user import super_user_bp, init_super_user_routes
    init_super_user_routes(env_data["db"])           
    app.register_blueprint(super_user_bp)        


    return app
