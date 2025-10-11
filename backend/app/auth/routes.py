from __future__ import annotations
from flask import Blueprint, request, jsonify, current_app
from app.db import db
import re
import bcrypt
import secrets
import hashlib
import jwt
from jwt.algorithms import RSAAlgorithm
import json
import requests
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple, Iterable
from .utils import send_reset_email

# from google.oauth2 import id_token
# from google.auth.transport import requests as grequests

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# ----------------------------- Utilities (no behavior change) -----------------------------

EMAIL_RE = re.compile(r"^\S+@\S+\.\S+$")

USER_COLS = (
    "user_id",
    "name",
    "password",
    "current_venue_id",
    "birthday",
    "gender",
    "level",
    "email",
    "picture",         
    "workout_number",
)


def utc_now():
    return datetime.now(timezone.utc)

def _row_to_user(row: Tuple[Any, ...]) -> Dict[str, Any]:
    """Convert a Users SELECT * tuple into a dict with stable keys."""
    return {k: row[i] if i < len(row) else None for i, k in enumerate(USER_COLS)}

def _json_error(message: str, code: int):
    """Consistent error responder (status code preserved by caller)."""
    return jsonify({"error": message}), code

def get_user_by_email(email: str) -> Optional[Tuple[Any, ...]]:
    rows = db.execute("SELECT * FROM Users WHERE email=%s", (email,), fetch=True)
    return rows[0] if rows else None

def create_user(name: str, email: str, pw_hash: bytes, agreed: bool) -> Tuple[Any, ...]:
    rows = db.execute(
        """INSERT INTO Users (name, email, password, level, workout_number, agreed)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING *""",
        (name, email, pw_hash.decode("utf-8"), 1, 0, agreed),
        fetch=True,
    )
    return rows[0]

def link_provider(user_id: int, provider: str, provider_user_id: str) -> None:
    db.execute(
        """INSERT INTO user_providers (user_id, provider, provider_user_id)
           VALUES (%s, %s, %s)
           ON CONFLICT (provider, provider_user_id) DO NOTHING""",
        (user_id, provider, provider_user_id),
    )

def create_default_venue(user_id: int, name: str = "My Venue") -> int:
    rows = db.execute(
        """
        INSERT INTO Venues (
            name, user_id, gym_setup, goals, priority_muscles, pain_points,
            split, days_of_week, workout_frequency, time_per_workout,
            rest_time_between_set
        )
        VALUES (%s, %s, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)
        RETURNING venue_id
        """,
        (name, user_id),
        fetch=True,
    )
    return rows[0][0]

def set_user_current_venue(user_id: int, venue_id: int) -> None:
    db.execute("UPDATE Users SET current_venue_id=%s WHERE user_id=%s", (venue_id, user_id))

def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _issue_reset_for(user_id: int, ip: Optional[str] = None) -> Tuple[str, datetime]:
    raw = secrets.token_urlsafe(48)
    token_hash = _hash_token(raw)
    expires_at = utc_now() + timedelta(hours=1)          # aware UTC

    db.execute(
        """INSERT INTO password_resets (user_id, token_hash, expires_at, created_ip)
           VALUES (%s, %s, %s, %s)""",
        (user_id, token_hash, expires_at, ip),
    )
    return raw, expires_at

def insert_venue_equipment(venue_id: int, equipment_list: Iterable[Dict[str, Any]]) -> None:
    for eq in equipment_list:
        # Resolve the equipment_id
        weight_val = eq.get("weight", "")
        weight_val = str(float(weight_val)) if weight_val != "" else ""
        result = db.execute(
            """
            SELECT equipment_id FROM equipment 
            WHERE name = %s AND weight_resistance_time = %s
            """,
            (eq["name"], weight_val),
            fetch=True,
        )
        if not (result and len(result) > 0):
            # Silent skip preserves original behavior (only logs)
            print(
                f"No matching equipment found for '{eq['name']}' "
                f"with weight '{weight_val}'. Skipping insertion."
            )
            continue

        equipment_id = result[0][0]
        try:
            db.execute(
                """
                INSERT INTO Venue_equipment (venue_id, equipment_id, quantity)
                VALUES (%s, %s, %s)
                """,
                (venue_id, equipment_id, eq.get("quantity", 1)),
            )
            print(
                f"Inserted venue_equipment for venue_id {venue_id} with equipment_id {equipment_id}"
            )
        except Exception as e:
            print(f"Error inserting equipment '{eq['name']}' for venue {venue_id}: {e}")

# NEW: ensure default venue exists for a user (used by SSO routes for B)
def _ensure_default_venue(user_id: int) -> Optional[int]:
    """
    If the user doesn't have a current_venue_id, create one and set it.
    Returns the current/default venue_id (created or existing).
    """
    try:
        row = db.execute(
            "SELECT current_venue_id FROM Users WHERE user_id=%s",
            (user_id,),
            fetch=True,
        )
        if not row:
            return None
        current_vid = row[0][0]
        if current_vid:
            return current_vid
        # create and set
        venue_id = create_default_venue(user_id, name="Fitness Venue")
        set_user_current_venue(user_id, venue_id)
        return venue_id
    except Exception:
        current_app.logger.exception(f"ensure_default_venue failed for user_id={user_id}")
        return None

# ----------------------------------- Auth: Register/Login -----------------------------------
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    agreed = data.get("agreed") or False

    if not agreed:
        return _json_error("Please agree to the Privacy Policy and Terms & Conditions.", 400)

    if not name:
        return _json_error("Name is required.", 400)
    if not EMAIL_RE.match(email):
        return _json_error("Valid email is required.", 400)
    if len(password) < 8:
        return _json_error("Password must be at least 8 characters.", 400)

    existing = get_user_by_email(email)
    if existing:
        return _json_error("Email is already registered.", 409)

    try:
        pw_hash = bcrypt.hashpw(password, bcrypt.gensalt())
        user_row = create_user(name, email, pw_hash, agreed=agreed)
        user = _row_to_user(user_row)

        venue_id = create_default_venue(user["user_id"], name="Fitness Venue")
        set_user_current_venue(user["user_id"], venue_id)

        # Preserve payload shape
        return jsonify({"success": True, "user_id": user["user_id"], "venue_id": venue_id})
    except Exception:
        current_app.logger.exception("Registration failed")
        return _json_error("Registration failed. Please try again.", 500)


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user_row = get_user_by_email(email)
    if not user_row:
        return _json_error("Invalid credentials.", 201)

    user = _row_to_user(user_row)
    stored = (user.get("password") or "").encode("utf-8")
    if not stored or not bcrypt.checkpw(password.encode("utf-8"), stored):
        return _json_error("Invalid credentials.", 201)

    return jsonify({"success": True, "user_id": user["user_id"]})

# ----------------------------------- Google SSO (access token) -----------------------------------

@auth_bp.route("/google", methods=["POST"])
def google_signin():
    """
    Accepts accessToken only.
    - Validates accessToken by calling Google userinfo.
    - Creates/links a user.
    - Ensures the user has a default venue (B).
    Returns:
      200: {"success": True, "user_id": <int>, "venue_id": <int|null>}
      400: {"error": "Missing accessToken"}
      401: {"error": "Invalid Google access token"} or {"error": "Google sign-in failed"}
    """
    data = request.get_json() or {}
    access_token = data.get("accessToken") or data.get("accesstoken")

    agreed = data.get("agreed") or False

    if not agreed:
        return _json_error("Please agree to the Provacy Policy and Terms & Conditions.", 400)
    
    if not access_token:
        return jsonify({"error": "Missing accessToken"}), 400

    try:
        # Validate & fetch profile from Google
        r = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=6,
        )
        r.raise_for_status()
        g = r.json()  # expected keys: sub, email, name, picture, email_verified, ...

        sub = g.get("sub")
        email = (g.get("email") or "").lower()
        name = g.get("name") or "User"
        picture = g.get("picture")  # optional

        # 1) If we have a Google sub, try provider link first
        if sub:
            rows = db.execute(
                """SELECT u.* FROM user_providers up
                   JOIN Users u ON u.user_id = up.user_id
                   WHERE up.provider=%s AND up.provider_user_id=%s""",
                ("google", sub),
                fetch=True,
            )
            if rows:
                user_id = rows[0][0]
                venue_id = _ensure_default_venue(user_id)
                # set_user_current_venue(user_id, venue_id)
                return jsonify({"success": True, "user_id": user_id, "venue_id": venue_id})

        # 2) Otherwise (or if not linked), try by email
        user_row = get_user_by_email(email) if email else None
        if not user_row:
            # Create user; email can be NULL if Google didn't return it
            user_row = db.execute(
                """INSERT INTO Users (name, email, password, level,
                workout_number, picture, agreed)
                VALUES (%s, %s, NULL, %s, %s, %s, %s)
                RETURNING *""",
                (name, email if email else None, 1, 0, picture if picture else None, agreed),
                fetch=True,
            )[0]

        user = _row_to_user(user_row)
        user_id = user["user_id"]

        # 3) Link provider if we have a stable Google 'sub'
        if sub:
            link_provider(user_id, "google", sub)

        # 4) Ensure default venue exists (B)
        venue_id = _ensure_default_venue(user_id)
        # set_user_current_venue(user_id, venue_id)

        return jsonify({"success": True, "user_id": user_id, "venue_id": venue_id})

    except requests.HTTPError:
        current_app.logger.exception("Google userinfo error")
        return jsonify({"error": "Invalid Google access token"}), 401
    except Exception:
        current_app.logger.exception("Google sign-in failed")
        return jsonify({"error": "Google sign-in failed"}), 401

# ------------------------------------ Apple SSO (ID token) ------------------------------------

def _get_apple_public_key(kid: str) -> Optional[Dict[str, Any]]:
    jwks = requests.get("https://appleid.apple.com/auth/keys", timeout=5).json()
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None

@auth_bp.route("/apple", methods=["POST"])
def apple_signin():
    """
    Accepts idToken (Apple).
    - Verifies token against Apple JWKS.
    - Creates/links a user.
    - Ensures the user has a default venue (B).
    """
    data = request.get_json() or {}
    id_token_str = data.get("idToken")
    agreed = data.get("agreed") or False

    if not agreed:
        return _json_error("Please agree to the Provacy Policy and Terms & Conditions.", 400)
    
    if not id_token_str:
        return _json_error("Missing idToken", 400)

    try:
        header = jwt.get_unverified_header(id_token_str)
        key = _get_apple_public_key(header["kid"])
        if not key:
            return _json_error("Apple key not found", 401)

        public_key = RSAAlgorithm.from_jwk(json.dumps(key))
        decoded = jwt.decode(
            id_token_str,
            key=public_key,
            algorithms=["RS256"],
            audience=current_app.config["APPLE_AUDIENCE"],
            issuer="https://appleid.apple.com",
            options={"verify_exp": True},
        )

        provider_user_id = decoded["sub"]
        email = (decoded.get("email") or "").lower() if decoded.get("email") else None

        # 1) If provider link exists, reuse user
        rows = db.execute(
            """SELECT u.* FROM user_providers up
               JOIN Users u ON u.user_id = up.user_id
               WHERE up.provider=%s AND up.provider_user_id=%s""",
            ("apple", provider_user_id),
            fetch=True,
        )
        if rows:
            user = _row_to_user(rows[0])
            venue_id = _ensure_default_venue(user["user_id"])  # <-- B
            return jsonify({"success": True, "user_id": user["user_id"], "venue_id": venue_id})

        # 2) Try merge by email (may be relay or None)
        user_row = get_user_by_email(email) if email else None
        if not user_row:
            user_row = db.execute(
                """INSERT INTO Users (name, email, password, level, workout_number, agreed)
                   VALUES (%s, %s, NULL, %s, %s, %s)
                   RETURNING *""",
                ("Apple User", email, 1, 0, agreed),
                fetch=True,
            )[0]

        user = _row_to_user(user_row)

        # 3) Link provider
        link_provider(user["user_id"], "apple", provider_user_id)

        # 4) Ensure default venue exists (B)
        venue_id = _ensure_default_venue(user["user_id"])

        return jsonify({"success": True, "user_id": user["user_id"], "venue_id": venue_id})

    except Exception:
        current_app.logger.exception("Apple token verification failed")
        return _json_error("Invalid Apple token", 401)

# -------------------------------- Password reset & update (same behavior) -------------------

@auth_bp.route("/forgot", methods=["POST"])
def forgot_password():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()

    # Always behave the same regardless of account existence
    user_row = get_user_by_email(email)
    if user_row:
        user = _row_to_user(user_row)
        try:
            raw_token, exp = _issue_reset_for(user["user_id"], request.remote_addr)
            app_scheme = current_app.config.get("APP_SCHEME", "genfitapp")
            app_link = f"{app_scheme}://reset?token={raw_token}"
            try:
                send_reset_email(email, app_link)
            except Exception as e:
                current_app.logger.exception("reset email send failed")
            current_app.logger.info(f"[forgot] reset issued uid={user['user_id']} exp={exp.isoformat()}")
        except Exception:
            current_app.logger.exception("reset issuance failed")

    # Same response either way
    return jsonify({"ok": True})


@auth_bp.route("/reset", methods=["POST"])
def reset_password():
    data = request.get_json() or {}
    raw_token = data.get("token") or ""
    new_password = data.get("password") or ""

    if len(new_password) < 8:
        return _json_error("Password must be at least 8 characters.", 400)

    token_hash = _hash_token(raw_token)
    rows = db.execute(
        """SELECT reset_id, user_id, expires_at, used_at
             FROM password_resets
            WHERE token_hash=%s""",
        (token_hash,), fetch=True,
    )
    if not rows:
        return _json_error("Invalid or expired token.", 400)

    reset_id, user_id, expires_at, used_at = rows[0]

    # Compare with aware UTC 'now'
    if used_at is not None or expires_at < utc_now():
        return _json_error("Invalid or expired token.", 400)

    # Update password
    pw_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    db.execute("UPDATE Users SET password=%s WHERE user_id=%s", (pw_hash, user_id))

    # Mark this token used (UTC), and invalidate any other active tokens for same user
    now = utc_now()
    db.execute("UPDATE password_resets SET used_at=%s WHERE reset_id=%s", (now, reset_id))
    db.execute(
        """UPDATE password_resets
              SET used_at=%s
            WHERE user_id=%s AND used_at IS NULL AND expires_at > %s""",
        (now, user_id, now),
    )

    return jsonify({"ok": True})


@auth_bp.route("/update_password/<int:user_id>", methods=["PUT"])
def update_password(user_id: int):
    data = request.get_json(silent=True) or {}
    prev_password = data.get("prevPassword")
    new_password = data.get("newPassword")
    confirm_password = data.get("confirmPassword")

    if not all([prev_password, new_password, confirm_password]):
        return _json_error("All password fields are required", 400)

    if new_password != confirm_password:
        return _json_error("New password and confirmation do not match", 400)

    try:
        result = db.execute("SELECT password FROM Users WHERE user_id = %s;", (user_id,), fetch=True)
        if not result:
            return _json_error("User not found", 404)

        current_hashed_password = result[0][0]
        if not bcrypt.checkpw(prev_password.encode("utf-8"), current_hashed_password.encode("utf-8")):
            # Preserve original 401 and code marker
            return jsonify({"error": "Incorrect current password", "code": 1})

        new_hashed_password = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        db.execute("UPDATE Users SET password = %s WHERE user_id = %s;", (new_hashed_password, user_id))
        return jsonify({"message": "Password updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": "Error updating password", "details": str(e)}), 500
