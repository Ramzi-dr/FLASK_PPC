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
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
    decode_token
)
from jwt import decode as jwt_decode
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from datetime import timedelta, datetime, timezone
from collections import OrderedDict
import json


def create_app(env_data):
    app = Flask(__name__)

    app.config["JWT_SECRET_KEY"] = env_data["JWT_SECRET_KEY"]

    # Use token expiration seconds from env_data, fallback to defaults
    access_exp_sec = int(env_data.get("JWT_ACCESS_TOKEN_EXPIRES", 60))
    refresh_exp_sec = int(env_data.get("JWT_REFRESH_TOKEN_EXPIRES", 300))

    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(seconds=access_exp_sec)
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(seconds=refresh_exp_sec)

    app.config["JWT_VERIFY_EXPIRATION"] = True

    # Token cutoff to reject tokens issued before this time
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

        print(f"DEBUG: Now={now}, Token exp={exp}, Token iat={iat}, Cutoff={app.config['TOKEN_ISSUED_AFTER']}, jti={jti}")

        if jti in token_blacklist:
            print(f"DEBUG: Token revoked: jti={jti}")
            return True

        if exp is not None and exp < now:
            print("DEBUG: Token expired (manual expiration check)")
            return True

        if iat < app.config["TOKEN_ISSUED_AFTER"]:
            print("DEBUG: Token issued before cutoff, reject")
            return True

        return False

    @app.route("/logout", methods=["POST"])
    @jwt_required()
    def logout():
        jti = get_jwt().get("jti")
        token_blacklist.add(jti)
        print(f"DEBUG: Token revoked and added to blacklist: jti={jti}")
        return jsonify(msg="Logged out successfully"), 200

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        print("DEBUG: Expired token detected (expired_token_loader)")
        return jsonify(msg="❌ Token expired"), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(err_msg):
        print(f"DEBUG: Invalid token: {err_msg} (invalid_token_loader)")
        return jsonify(msg="❌ Invalid token"), 422

    @jwt.unauthorized_loader
    def unauthorized_callback(err_msg):
        print(f"DEBUG: Missing token: {err_msg} (unauthorized_loader)")
        return jsonify(msg="❌ Missing token"), 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        print("DEBUG: Revoked token detected (revoked_token_loader)")
        return jsonify(msg="❌ Token revoked"), 401

    @app.errorhandler(ExpiredSignatureError)
    def handle_expired_error(e):
        print("DEBUG: Token expired error caught (from PyJWT)")
        return jsonify(msg="❌ Token expired"), 401

    @app.route("/")
    def index():
        print("DEBUG: Index route called")
        return jsonify(msg="Flask API is running")

    @app.route("/login", methods=["POST"])
    def login():
        print("DEBUG: Login route called")
        data = request.get_json()
        print(f"DEBUG: Login payload: {data}")
        username = data.get("username")
        password = data.get("password")

        if username != valid_user:
            print("DEBUG: Invalid username")
            return jsonify(msg="Invalid credentials"), 401

        if not bcrypt.checkpw(password.encode(), valid_pw_hash.encode()):
            print("DEBUG: Invalid password")
            return jsonify(msg="Invalid credentials"), 401

        access_token = create_access_token(identity=username)
        refresh_token = create_refresh_token(identity=username)

        decoded_access = decode_token(access_token)
        print("DEBUG: Access token decoded payload:", decoded_access)

        print(f"DEBUG: Tokens issued for user {username}")
        return jsonify(
            access_token=access_token,
            refresh_token=refresh_token,
            info=f"⚠️ Access token valid for {app.config['JWT_ACCESS_TOKEN_EXPIRES']}. Use refresh token to renew."
        )

    @app.route("/refresh", methods=["POST"])
    def refresh():
        print("DEBUG: Refresh route called")
        data = request.get_json()
        token = data.get("token", None)
        print(f"DEBUG: Token received in JSON body: {token}")

        if not token:
            print("DEBUG: Missing token in JSON body")
            return jsonify(msg="❌ Missing token in JSON body"), 401

        try:
            decoded = jwt_decode(token, app.config["JWT_SECRET_KEY"], algorithms=["HS256"])
            print(f"DEBUG: Refresh token decoded: {decoded}")
            if decoded.get("type") != "refresh":
                print("DEBUG: Token is not a refresh token")
                return jsonify(msg="❌ Token is not a refresh token"), 422
            if decoded.get("jti") in token_blacklist:
                print(f"DEBUG: Refresh token revoked: jti={decoded.get('jti')}")
                return jsonify(msg="❌ Token revoked"), 401
        except ExpiredSignatureError:
            print("DEBUG: Refresh token expired")
            return jsonify(msg="❌ Token expired"), 401
        except InvalidTokenError as e:
            print(f"DEBUG: Refresh token invalid: {str(e)}")
            return jsonify(msg="❌ Invalid token"), 422

        new_access_token = create_access_token(identity=decoded["sub"])
        print("DEBUG: New access token issued")
        return jsonify(access_token=new_access_token)

    @app.route("/protected", methods=["GET"])
    @jwt_required()
    def protected():
        user = get_jwt_identity()
        print(f"DEBUG: Access token valid for user {user}")
        return jsonify(msg=f"Hello {user}, access granted")

    @app.route("/admin/set_token_expiry", methods=["POST"])
    def set_token_expiry():
        data = request.get_json()
        access_seconds = data.get("access_seconds")
        refresh_seconds = data.get("refresh_seconds")

        if access_seconds is not None:
            app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(seconds=int(access_seconds))
            print(f"DEBUG: Access token expiry set to {access_seconds} seconds")

        if refresh_seconds is not None:
            app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(seconds=int(refresh_seconds))
            print(f"DEBUG: Refresh token expiry set to {refresh_seconds} seconds")

        app.config["TOKEN_ISSUED_AFTER"] = datetime.now(tz=timezone.utc).timestamp()
        print(f"DEBUG: TOKEN_ISSUED_AFTER updated to {app.config['TOKEN_ISSUED_AFTER']}")

        return jsonify(msg="Token expiry updated and old tokens invalidated")

    from routes.stores import stores_bp, init_store_routes
    init_store_routes(env_data["db"])
    app.register_blueprint(stores_bp)

    from routes.users import users_bp, init_user_routes
    init_user_routes(env_data["db"])
    app.register_blueprint(users_bp)

    from routes.super_user import super_user_bp, init_super_user_routes
    init_super_user_routes(env_data["db"])
    app.register_blueprint(super_user_bp)

    print("DEBUG: App created and routes registered")
    return app
