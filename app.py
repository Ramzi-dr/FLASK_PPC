from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt
)
from jwt.exceptions import ExpiredSignatureError
from datetime import timedelta, datetime, timezone
from logger import logger
import uuid
import bcrypt
from werkzeug.security import check_password_hash


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
        if jti in token_blacklist or (exp and exp < now) or (iat < app.config["TOKEN_ISSUED_AFTER"]):
            logger.warning("Blocked/expired token used")
            return True
        return False

    @app.route("/logout", methods=["POST"])
    @jwt_required()
    def logout():
        jti = get_jwt().get("jti")
        token_blacklist.add(jti)
        return jsonify(msg="Logged out successfully"), 200

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify(msg="❌ Token expired"), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(err_msg):
        return jsonify(msg="❌ Invalid token"), 422

    @jwt.unauthorized_loader
    def unauthorized_callback(err_msg):
        return jsonify(msg="❌ Missing token"), 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify(msg="❌ Token revoked"), 401

    @app.errorhandler(ExpiredSignatureError)
    def handle_expired_error(e):
        return jsonify(msg="❌ Token expired"), 401

    @app.route("/")
    def index():
        return jsonify(msg="Flask API is running")

    @app.route("/login", methods=["POST"])
    def login():
        data = request.get_json()
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()

        # Admin login
        if username == valid_user and bcrypt.checkpw(password.encode(), valid_pw_hash.encode()):
            access_token = create_access_token(identity=username, additional_claims={"role": "admin"})
            refresh_token = create_refresh_token(identity=username, additional_claims={"role": "admin"})
            logger.info(f"Admin login OK: {username}")
            return jsonify(
                msg="✅ Admin login OK",
                access_token=access_token,
                refresh_token=refresh_token,
                info={
                    "access": f"⚠️ Access token valid for {app.config['JWT_ACCESS_TOKEN_EXPIRES']}",
                    "refresh": f"♻️ Refresh token valid for {app.config['JWT_REFRESH_TOKEN_EXPIRES']}",
                },
            ), 200

        # Fallback: user login
        user_doc = env_data["db"].users.find_one({"email": username.upper()})
        if not user_doc or not check_password_hash(user_doc["password"], password):
            logger.warning(f"Login failed: invalid credentials for {username}")
            return jsonify(msg="❌ Invalid credentials"), 401

        access_token = create_access_token(identity=username.upper(), additional_claims={"role": "user"})
        refresh_token = create_refresh_token(identity=username.upper(), additional_claims={"role": "user"})
        logger.info(f"User login OK: {username.upper()}")
        return jsonify(
            msg="✅ User login OK",
            access_token=access_token,
            refresh_token=refresh_token,
            info={
                "access": f"⚠️ Access token valid for {app.config['JWT_ACCESS_TOKEN_EXPIRES']}",
                "refresh": f"♻️ Refresh token valid for {app.config['JWT_REFRESH_TOKEN_EXPIRES']}",
            },
        ), 200

    @app.route("/refresh", methods=["POST"])
    @jwt_required(refresh=True)
    def refresh():
        identity = get_jwt_identity()
        claims = get_jwt()
        role = claims.get("role", "user")
        new_token = create_access_token(identity=identity, additional_claims={"role": role})
        logger.info(f"New access token issued for: {identity}")
        return jsonify(access_token=new_token)

    @app.route("/protected", methods=["GET"])
    @jwt_required()
    def protected():
        user = get_jwt_identity()
        claims = get_jwt()
        role = claims.get("role", "unknown")
        return jsonify(msg=f"Hello {user} ({role}), access granted")

    # Register routes
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

    from routes.user_login import user_login_bp, init_user_login_routes
    init_user_login_routes(env_data["db"])
    app.register_blueprint(user_login_bp)

    return app
