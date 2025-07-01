"""
app.py — Secure Flask app with JWT-based authentication and dynamic token expiration

This file defines the main application factory `create_app()`, which:
- Sets up secure JWT authentication with short-lived access tokens and longer-lived refresh tokens.
- Uses Flask-JWT-Extended to create, verify, and revoke JWTs.
- Configures Cross-Origin Resource Sharing (CORS) to allow frontend apps to access the API.
- Provides these core routes:
    - `/login`: accepts username and password, returns access and refresh tokens.
    - `/refresh`: accepts a valid refresh token and issues a new access token.
    - `/logout`: revokes tokens by adding their unique IDs to a blacklist.
    - `/protected`: an example protected route accessible only with a valid access token.
    - `/admin/set_token_expiry`: an admin-only route to dynamically change access and refresh token expiration times during runtime.

Key security feature:
- Tokens include an "issued at" (`iat`) timestamp.
- The app maintains a `TOKEN_ISSUED_AFTER` cutoff timestamp.
- Any token issued before `TOKEN_ISSUED_AFTER` is automatically invalidated (rejected).
- When the token expiration is changed dynamically via `/admin/set_token_expiry`, the `TOKEN_ISSUED_AFTER` is updated to the current time to immediately invalidate all previously issued tokens with old expiration times.
- This approach ensures that **old tokens are never accepted beyond the new expiration policy**, preventing security issues related to long-lived or outdated tokens.

How to use the dynamic token expiration API:
- Send a POST request to `/admin/set_token_expiry` with JSON body specifying new expiration values in seconds. For example:

    ```bash
    curl -X POST http://localhost:5000/admin/set_token_expiry \
        -H "Content-Type: application/json" \
        -d '{"access_seconds":3600, "refresh_seconds":7200}'
    ```

  This sets access tokens to expire in 1 hour (3600 seconds) and refresh tokens in 2 hours (7200 seconds), immediately invalidating all tokens issued before this change.

- The next tokens issued after this call will follow the new expiration times.
- Any tokens issued before this update will be rejected on all protected routes.

This makes it easy and safe to **test different token expiration policies during development** without restarting the app or changing code.

---

REQUIREMENTS (install with pip):
    pip install flask flask-cors flask-jwt-extended bcrypt

DEPENDENCIES:
    - This app expects a dictionary `env_data` passed into `create_app()` with:
        - "FLASK_USER": the username (string)
        - "FLASK_PASSWORD": bcrypt-hashed password (string)
        - "JWT_SECRET_KEY": secret string used to sign JWT tokens
        - "JWT_ACCESS_TOKEN_EXPIRES": access token expiry in seconds (int)
        - "JWT_REFRESH_TOKEN_EXPIRES": refresh token expiry in seconds (int)
        - "db": a MongoDB client instance or other database connection for routes

Overall, this app demonstrates best practices for token lifecycle management in JWT-secured Flask APIs, with added flexibility for live configuration of token expiration policies.
"""
import bcrypt
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)
from jwt.exceptions import ExpiredSignatureError
from datetime import timedelta, datetime, timezone
from logger import logger
import uuid


def create_app(env_data):
    logger.info(f"create_app called — ID: {uuid.uuid4()}")

    app = Flask(__name__)
    app.debug = False

    @app.before_request
    def sync_token_expiry():
        db = env_data["db"]["env"]
        access_doc = db.find_one({"key": "JWT_ACCESS_TOKEN_EXPIRES_SECONDS"})
        refresh_doc = db.find_one({"key": "JWT_REFRESH_TOKEN_EXPIRES_SECONDS"})
        cutoff_doc = db.find_one({"key": "TOKEN_ISSUED_AFTER"})

        if access_doc:
            try:
                app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(seconds=int(access_doc["value"]))
            except ValueError:
                logger.warning("Invalid JWT_ACCESS_TOKEN_EXPIRES_SECONDS value in DB.")

        if refresh_doc:
            try:
                app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(seconds=int(refresh_doc["value"]))
            except ValueError:
                logger.warning("Invalid JWT_REFRESH_TOKEN_EXPIRES_SECONDS value in DB.")

        if cutoff_doc:
            try:
                app.config["TOKEN_ISSUED_AFTER"] = float(cutoff_doc["value"])
            except ValueError:
                logger.warning("Invalid TOKEN_ISSUED_AFTER value in DB.")

    app.config["JWT_SECRET_KEY"] = env_data["JWT_SECRET_KEY"]
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(seconds=int(env_data.get("JWT_ACCESS_TOKEN_EXPIRES", 60)))
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(seconds=int(env_data.get("JWT_REFRESH_TOKEN_EXPIRES", 300)))
    app.config["JWT_VERIFY_EXPIRATION"] = True
    app.config["TOKEN_ISSUED_AFTER"] = datetime.now(tz=timezone.utc).timestamp()

    CORS(app)

    jwt = JWTManager(app)

    valid_user = env_data["FLASK_USER"]
    valid_pw_hash = env_data["FLASK_PASSWORD"]

    token_blacklist = set()

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        jti = jwt_payload.get("jti")
        exp = jwt_payload.get("exp")
        iat = jwt_payload.get("iat", 0)
        now = datetime.now(tz=timezone.utc).timestamp()

        if jti in token_blacklist:
            logger.warning(f"Blocked token used: jti={jti}")
            return True

        if exp and exp < now:
            logger.warning("Token manually expired")
            return True

        if iat < app.config["TOKEN_ISSUED_AFTER"]:
            logger.warning("Token issued before cutoff")
            return True

        return False

    @app.route("/logout", methods=["POST"])
    @jwt_required()
    def logout():
        jti = get_jwt().get("jti")
        token_blacklist.add(jti)
        return jsonify(msg="Logged out successfully"), 200

    def log_token_event(reason):
        try:
            token = request.headers.get("Authorization", "").replace("Bearer ", "")[:15] + "..."
            ip = request.remote_addr or "unknown"
            route = request.path or "unknown"
            logger.warning(f"{reason} | IP: {ip} | Route: {route} | Token: {token}")
        except Exception as e:
            logger.error(f"⚠️ Failed to log token event: {e}")

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        log_token_event("Expired token")
        return jsonify(msg="❌ Token expired"), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(err_msg):
        log_token_event(f"Invalid token: {err_msg}")
        return jsonify(msg="❌ Invalid token"), 422

    @jwt.unauthorized_loader
    def unauthorized_callback(err_msg):
        log_token_event(f"Unauthorized access: {err_msg}")
        return jsonify(msg="❌ Missing token"), 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        log_token_event("Revoked token attempt")
        return jsonify(msg="❌ Token revoked"), 401

    @app.errorhandler(ExpiredSignatureError)
    def handle_expired_error(e):
        log_token_event("Token expired (JWT exception)")
        return jsonify(msg="❌ Token expired"), 401

    @app.route("/")
    def index():
        if request.remote_addr != "127.0.0.1":
            logger.info(
                f"Health check from IP: {request.remote_addr} | Agent: {request.headers.get('User-Agent')}"
            )
        return jsonify(msg="Flask API is running")

    @app.route("/login", methods=["POST"])
    def login():
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")

        if username != valid_user:
            logger.warning("Login failed: invalid username")
            return jsonify(msg="Invalid credentials"), 401

        if not bcrypt.checkpw(password.encode(), valid_pw_hash.encode()):
            logger.warning("Login failed: invalid password")
            return jsonify(msg="Invalid credentials"), 401

        access_token = create_access_token(identity=username)
        refresh_token = create_refresh_token(identity=username)

        logger.info(f"Tokens issued for user: {username}")

        return jsonify(
            access_token=access_token,
            refresh_token=refresh_token,
            info={
                "access": f"⚠️ Access token valid for {app.config['JWT_ACCESS_TOKEN_EXPIRES']}",
                "refresh": f"♻️ Refresh token valid for {app.config['JWT_REFRESH_TOKEN_EXPIRES']}",
            },
        )

    @app.route("/refresh", methods=["POST"])
    @jwt_required(refresh=True)
    def refresh():
        identity = get_jwt_identity()
        new_access_token = create_access_token(identity=identity)
        logger.info(f"New access token issued for: {identity}")
        return jsonify(access_token=new_access_token)

    @app.route("/protected", methods=["GET"])
    @jwt_required()
    def protected():
        user = get_jwt_identity()
        logger.info(f"Protected route accessed by: {user}")
        return jsonify(msg=f"Hello {user}, access granted")

    from routes.stores import stores_bp, init_store_routes
    init_store_routes(env_data["db"])
    app.register_blueprint(stores_bp)

    from routes.users import users_bp, init_user_routes
    init_user_routes(env_data["db"])
    app.register_blueprint(users_bp)

    from routes.super_user import super_user_bp, init_super_user_routes
    init_super_user_routes(env_data["db"])
    app.register_blueprint(super_user_bp)

    from routes.cameras import cameras_bp, init_camera_routes
    init_camera_routes(env_data["db"])
    app.register_blueprint(cameras_bp)

    from routes.admin import admin_bp, init_admin_routes
    init_admin_routes(env_data["db"])
    app.register_blueprint(admin_bp, url_prefix="/admin")

    from routes.camera_data import data_bp, init_camera_data_routes
    init_camera_data_routes(env_data["db"])
    app.register_blueprint(data_bp, url_prefix="/camera_data")

    from routes.store_data import data_bp, init_store_data_routes
    init_store_data_routes(env_data["db"])
    app.register_blueprint(data_bp, url_prefix="/store_data")

    return app
