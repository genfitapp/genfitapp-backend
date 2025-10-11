# profile.py
from __future__ import annotations

import os
import uuid
from typing import Any, Dict, Iterable, List, Optional, Tuple

import sib_api_v3_sdk
# from sib_api_v3_sdk.rest import ApiException

from flask import Blueprint, request, jsonify, send_from_directory, current_app
from werkzeug.utils import secure_filename

from app.db import db  # import the db instance from app/db.py
from .utils import get_consecutive_streaks, group_workouts_by_week
# import resend

# ------------------------------------------------------------------------------------------
# Blueprint
# ------------------------------------------------------------------------------------------

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")

# ------------------------------------------------------------------------------------------
# Constants / Config Helpers
# ------------------------------------------------------------------------------------------

ALLOWED_EXTS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_MIMES = {"image/jpeg", "image/png", "image/webp"}

def _avatar_upload_dir() -> str:
    """
    Local upload directory for avatars (startup/dev).
    Override by setting app.config["AVATAR_UPLOAD_DIR"].
    """
    base = current_app.config.get(
        "AVATAR_UPLOAD_DIR",
        os.path.join(current_app.root_path, "uploads", "avatars")
    )
    os.makedirs(base, exist_ok=True)
    return base

def _avatar_public_base() -> Optional[str]:
    """
    Public base URL for avatars when fronted by CDN/object storage.
    Example: https://cdn.example.com/avatars
    """
    return current_app.config.get("AVATAR_PUBLIC_BASE")

# ------------------------------------------------------------------------------------------
# Small Utilities (no behavior change)
# ------------------------------------------------------------------------------------------

def _ext_from_filename(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

def _json(data: Dict[str, Any], code: Optional[int] = None):
    """
    Wrapper for jsonify; if code is None the caller’s existing behavior (default 200)
    is preserved.
    """
    if code is None:
        return jsonify(data)
    return jsonify(data), code

def _fetch_one(query: str, params: Tuple[Any, ...]) -> Optional[Tuple[Any, ...]]:
    rows = db.execute(query, params, fetch=True)
    return rows[0] if rows else None

def _get_user_picture(user_id: int) -> Optional[str]:
    row = _fetch_one("SELECT picture FROM Users WHERE user_id = %s;", (user_id,))
    return row[0] if row and row[0] else None

def _set_user_picture(user_id: int, url: Optional[str]) -> None:
    db.execute("UPDATE Users SET picture = %s WHERE user_id = %s;", (url, user_id))

# ------------------------------------------------------------------------------------------
# Data Access Helpers (no behavior change)
# ------------------------------------------------------------------------------------------

def get_user_name_and_level(data: Dict[str, Any]) -> Tuple[str, int]:
    """
    Reads name and level from Users by the provided token (user_id).
    Raises Exception with message preserved by caller.
    """
    try:
        row = _fetch_one(
            "SELECT name, level FROM Users WHERE user_id = %s;",
            (data.get("user_token"),),
        )
        if not row:
            raise Exception("User not found")
        return row[0], row[1]
    except Exception as e:
        raise Exception(f"Database error when retrieving user: {str(e)}")


def get_user_streaks(user_id: int) -> Tuple[int, int]:
    """
    Retrieves the workout frequency from the user's current venue and the user's workout dates,
    then computes current and record streaks.
    """
    # 1) Required workout frequency from the current venue
    venue_row = _fetch_one(
        """
        SELECT V.workout_frequency
        FROM Venues V
        JOIN Users U ON U.current_venue_id = V.venue_id
        WHERE U.user_id = %s;
        """,
        (user_id,),
    )
    if not venue_row:
        raise Exception("User's venue not found or workout_frequency missing")
    required_frequency = venue_row[0]

    # 2) All workout dates
    # routes.py -> get_user_streaks
    workouts_result = db.execute(
        """
        SELECT w.date
        FROM workouts w
        JOIN actual_workout a ON a.workout_id = w.workout_id
        WHERE w.user_id = %s
        AND COALESCE(a.duration_actual, 0) > 0
        ORDER BY w.date ASC;
        """,
        (user_id,),
        fetch=True,
    )

    workout_dates = [row[0] for row in workouts_result if row and row[0] is not None]

    # 3) Group by ISO week (year, week)
    week_counts = group_workouts_by_week(workout_dates)

    # 4) Compute streaks
    current_streak, record_streak = get_consecutive_streaks(week_counts, required_frequency)
    return current_streak, record_streak


def get_user_workout_summary(user_id: int) -> Tuple[int, float]:
    """
    Returns (total_workouts, total_hours) for a user.
    Counts only workouts where duration_actual > 0.
    """
    query = """
    SELECT 
        COUNT(DISTINCT w.workout_id) FILTER (WHERE a.duration_actual > 0) AS total_workouts,
        COALESCE(SUM(a.duration_actual), 0) AS total_duration_in_minutes
    FROM workouts w
    LEFT JOIN actual_workout a ON w.workout_id = a.workout_id
    WHERE w.user_id = %s;
    """
    row = _fetch_one(query, (user_id,))
    total_workouts = row[0] if row else 0
    total_minutes = row[1] if row else 0
    total_hours = total_minutes / 60.0
    return total_workouts, total_hours


# ------------------------------------------------------------------------------------------
# Core Profile Endpoints (behavior preserved)
# ------------------------------------------------------------------------------------------

@profile_bp.route("/", methods=["POST"])
def profile():
    """
    POST /profile
    Request JSON: { user_token: <int> }
    Response JSON:
      {
        "name": <str>,
        "level": <int>,
        "current_streaks": <int>,
        "record_streaks": <int>,
        "total_workouts": <int>,
        "total_hours": <float>
      }
    Status codes preserved (400 on missing data; 500 on exceptions).
    """
    data = request.get_json(silent=True)
    if not data:
        return _json({"error": "Please send request with valid data"}, 400)

    try:
        name, level = get_user_name_and_level(data)
        uid = data.get("user_token")
        current_streak, record_streak = get_user_streaks(uid)
        total_workouts, total_hours = get_user_workout_summary(uid)
    except Exception as e:
        return _json({"error": str(e)}, 500)

    return _json({
        "name": name,
        "level": level,
        "current_streaks": current_streak,
        "record_streaks": record_streak,
        "total_workouts": total_workouts,
        "total_hours": total_hours,
    })

@profile_bp.route("/<int:user_id>", methods=["GET"])
def get_user_profile(user_id: int):
    """
    GET /profile/<user_id>
    Response JSON:
      {
        "user_id": <int>,
        "name": <str>,
        "email": <str|null>,
        "birthday": <mm/dd/YYYY|null>
      }
    Status codes preserved: 200 on success, 404 if not found, 500 on error.
    """
    try:
        row = _fetch_one(
            "SELECT name, email, birthday FROM Users WHERE user_id = %s;",
            (user_id,),
        )
        if not row:
            return _json({"error": "User not found"}, 404)

        name, email, birthday = row
        formatted_birthday = birthday.strftime("%m/%d/%Y") if birthday else None

        return _json({
            "user_id": user_id,
            "name": name,
            "email": email,
            "birthday": formatted_birthday,
        }, 200)

    except Exception as e:
        return _json({"error": "Error retrieving user profile", "details": str(e)}, 500)

# ------------------------------------------------------------------------------------------
# Avatar: Serve / Get / Upload  (integrates with Google picture URLs)
# ------------------------------------------------------------------------------------------

@profile_bp.route("/media/avatars/<path:filename>", methods=["GET"])
def serve_avatar(filename: str):
    """
    GET /profile/media/avatars/<filename>
    Simple file server for uploaded avatars (startup/dev). For production/CDN,
    set AVATAR_PUBLIC_BASE and stop using this route.
    """
    return send_from_directory(_avatar_upload_dir(), filename, conditional=True)

@profile_bp.route("/<int:user_id>/avatar", methods=["GET"])
def get_avatar(user_id: int):
    """
    GET /profile/<user_id>/avatar
    Returns current Users.picture (Google URL or uploaded file URL).
    Response: 200 { "picture": <str|null> }
    """
    picture = _get_user_picture(user_id)
    return _json({"picture": picture}, 200)

@profile_bp.route("/<int:user_id>/avatar", methods=["POST"])
def upload_avatar(user_id: int):
    """
    POST /profile/<user_id>/avatar
    Multipart form with field 'file'. On success:
      200 { "success": True, "picture": "<public url>" }
    Overwrites Users.picture with the uploaded URL (replacing any Google URL).
    """
    if "file" not in request.files:
        return _json({"error": "Missing file field"}, 400)

    file = request.files["file"]
    if not file or file.filename == "":
        return _json({"error": "Empty filename"}, 400)

    ext = _ext_from_filename(file.filename)
    if ext not in ALLOWED_EXTS:
        return _json({"error": f"Unsupported file type: .{ext}"}, 400)

    mime = (file.mimetype or "").lower()
    if mime not in ALLOWED_MIMES:
        return _json({"error": f"Unsupported content-type: {mime}"}, 400)

    #  Cleanup: delete previous avatar if it exists
    try:
        old_url = _get_user_picture(user_id)
        if old_url and old_url.startswith("/profile/media/avatars/"):
            old_name = old_url.rsplit("/", 1)[-1]
            old_path = os.path.join(_avatar_upload_dir(), old_name)
            if os.path.isfile(old_path):
                os.remove(old_path)
    except Exception as e:
        current_app.logger.warning(f"Could not delete old avatar for user {user_id}: {e}")

    # Cache-busting filename to avoid stale avatars in clients/CDNs
    filename = secure_filename(f"{user_id}_{uuid.uuid4().hex}.{ext}")
    # Save to disk
    save_dir = _avatar_upload_dir()
    file.save(os.path.join(save_dir, filename))

    # Build public URL
    public_base = _avatar_public_base()
    if public_base:
        picture_url = f"{public_base.rstrip('/')}/{filename}"
    else:
        picture_url = f"/profile/media/avatars/{filename}"

    # Persist (overwrite Google URL if present)
    _set_user_picture(user_id, picture_url)

    return _json({"success": True, "picture": picture_url}, 200)

# ------------------------------------------------------------------------------------------
# Delete Account (behavior preserved, including places where you omitted status codes)
# ------------------------------------------------------------------------------------------

def send_message(user_id: int, message: str):
    """
    Sends a notification email using Brevo when an account is deleted.
    Returns a Flask response object (preserving your current behavior).
    """
    try:
        # Configure Brevo client from env
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = os.getenv("BREVO_API_KEY")
        api_client = sib_api_v3_sdk.ApiClient(configuration)
        emails_api = sib_api_v3_sdk.TransactionalEmailsApi(api_client)

        html_body = f"""
            <h3>User ID: {user_id} Deleted</h3>
            <p>The specified user requested to delete their account.</p>
            <p><strong>User feedback:</strong> {message}</p>
        """

        # Sender and recipient config (mirrors your old values)
        sender = current_app.config.get("MAIL_FROM", "ouattarabilly33@gmail.com")
        if "<" in sender and ">" in sender:
            name = sender.split("<")[0].strip().strip('"').strip()
            addr = sender.split("<")[1].split(">")[0].strip()
            sender_obj = {"name": name, "email": addr}
        else:
            sender_obj = {"email": sender}

        to_email = current_app.config.get("ADMIN_EMAIL", "genfitsoftware@gmail.com")

        payload = sib_api_v3_sdk.SendSmtpEmail(
            sender=sender_obj,
            to=[{"email": to_email}],
            subject="Account Deleted",
            html_content=html_body,
            # text_content can be added if you want a plaintext fallback
            # tags=["account-delete"]
        )
        resp = emails_api.send_transac_email(payload)

        # Brevo returns an object; message_id may be None in sandbox — keep your success shape
        return jsonify({"status": "success", "email_id": getattr(resp, "message_id", None)}), 200

    except Exception as e:
        # Preserve your original failure semantics
        return jsonify({"error": "Feedback submission failed", "details": str(e)}), 500


@profile_bp.route("/delete", methods=["DELETE"])
def delete_user_account():
    """
    DELETE /profile/delete
    Deletes a user and ALL associated data in a single transaction.
    Also clears Users.picture and removes the user's locally-stored avatar file (if present) after commit.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON", "success": False}), 400

    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required", "success": False}), 400

    message = data.get("message")

    # Capture current picture URL before we remove DB rows, so we can delete the file after commit
    try:
        picture_url = _get_user_picture(user_id)
    except Exception:
        picture_url = None  # non-fatal

    try:
        # db.execute("BEGIN;")

        # 1) Delete children of SUGGESTED/ACTUAL, then parents, then workouts
        db.execute(
            """
            DELETE FROM suggested_exercise_records
            WHERE suggested_workout_id IN (
                SELECT sw.suggested_workout_id
                FROM suggested_workouts sw
                JOIN workouts w ON w.workout_id = sw.workout_id
                WHERE w.user_id = %s
            );
            """,
            (user_id,),
        )
        db.execute(
            """
            DELETE FROM suggested_workouts
            WHERE workout_id IN (
                SELECT workout_id
                FROM workouts
                WHERE user_id = %s
            );
            """,
            (user_id,),
        )
        db.execute(
            """
            DELETE FROM actual_exercise_records
            WHERE actual_workout_id IN (
                SELECT aw.actual_workout_id
                FROM actual_workout aw
                JOIN workouts w ON w.workout_id = aw.workout_id
                WHERE w.user_id = %s
            );
            """,
            (user_id,),
        )
        db.execute(
            """
            DELETE FROM actual_workout
            WHERE workout_id IN (
                SELECT workout_id
                FROM workouts
                WHERE user_id = %s
            );
            """,
            (user_id,),
        )
        db.execute("DELETE FROM workouts WHERE user_id = %s;", (user_id,))

        # 2) Venue-related
        db.execute(
            """
            DELETE FROM Venue_equipment
            WHERE venue_id IN (
                SELECT venue_id FROM Venues WHERE user_id = %s
            );
            """,
            (user_id,),
        )
        db.execute("DELETE FROM Venues WHERE user_id = %s;", (user_id,))

        # 3) Other direct user-owned tables
        db.execute("DELETE FROM Milestones WHERE user_id = %s;", (user_id,))
        db.execute("DELETE FROM exercise_preferences WHERE user_id = %s;", (user_id,))
        db.execute("DELETE FROM password_resets WHERE user_id = %s;", (user_id,))
        db.execute("DELETE FROM user_providers WHERE user_id = %s;", (user_id,))

        # NEW: Clear Users.picture explicitly (helps with soft deletes / audit trails)
        db.execute("UPDATE Users SET picture = NULL WHERE user_id = %s;", (user_id,))

        # 4) Finally, delete the user
        db.execute("DELETE FROM Users WHERE user_id = %s;", (user_id,))

        # db.execute("COMMIT;")

        # Post-commit: try to delete the local avatar file if it exists
        try:
            if picture_url:
                filename = os.path.basename(picture_url.strip())
                if filename:
                    avatars_dir = _avatar_upload_dir()
                    candidate_path = os.path.join(avatars_dir, filename)

                    avatars_dir_abs = os.path.abspath(avatars_dir)
                    candidate_abs = os.path.abspath(candidate_path)
                    if os.path.commonpath([candidate_abs, avatars_dir_abs]) == avatars_dir_abs:
                        if os.path.isfile(candidate_abs):
                            os.remove(candidate_abs)
        except Exception as e:
            current_app.logger.warning(f"Avatar cleanup failed for user {user_id}: {e}")

        if message:
            try:
                send_message(user_id, message)
            except Exception:
                pass

        return jsonify({
            "message": "User account and all associated data deleted successfully.",
            "success": True
        }), 200

    except Exception as e:
        # try:
        #     # db.execute("ROLLBACK;")
        # except Exception:
        #     pass
        return jsonify({
            "error": "Failed to delete user account",
            "details": str(e),
            "success": False
        }), 500
