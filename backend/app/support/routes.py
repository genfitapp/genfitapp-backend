from flask import Blueprint, request, jsonify
import os
import base64
from werkzeug.utils import secure_filename
# Brevo (Sendinblue) SDK
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from dotenv import load_dotenv, find_dotenv

support_bp = Blueprint("support", __name__, url_prefix="/support")

# Load .env from the project root (or current working dir)
load_dotenv(find_dotenv(usecwd=True))

# ---------- helpers ----------

def _require_env(name: str) -> str:
    """Get an env var or raise a clear error if missing."""
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val


def _brevo_client() -> sib_api_v3_sdk.TransactionalEmailsApi:
    """Create a Brevo API client with the API key from env."""
    cfg = sib_api_v3_sdk.Configuration()
    cfg.api_key['api-key'] = _require_env("BREVO_API_KEY")
    return sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(cfg))


def _sender_from_config() -> dict:
    """
    MAIL_FROM can be:
      - 'GenFit <no-reply@example.com>' -> {'name': 'GenFit', 'email': 'no-reply@example.com'}
      - 'no-reply@example.com'          -> {'email': 'no-reply@example.com'}
    """
    sender = _require_env("MAIL_FROM")
    if "<" in sender and ">" in sender:
        name = sender.split("<")[0].strip().strip('"')
        addr = sender.split("<")[1].split(">")[0].strip()
        return {"name": name, "email": addr}
    return {"email": sender}


def _attachments_for_brevo(files) -> list[dict]:
    """
    Convert Werkzeug file objects into Brevo attachments:
    [{'name': 'file.png', 'content': '<base64>'}]
    """
    out = []
    for file in files:
        if not file:
            continue
        filename = secure_filename(file.filename or "")
        if not filename:
            continue
        # Read once (stream will be consumed)
        content_b64 = base64.b64encode(file.read()).decode("utf-8")
        out.append({"name": filename, "content": content_b64})
    return out


# ---------- routes ----------

@support_bp.route("/request", methods=["POST"])
def send_support_request():
    try:
        api = _brevo_client()

        message = (request.form.get("message") or "").strip() or "No message provided"
        user_id = (request.form.get("user_id") or "").strip() or "No user ID"

        # Collect attachments from multipart form-data (key: 'attachments')
        files = request.files.getlist("attachments")
        attachments = _attachments_for_brevo(files)

        html_body = f"""
            <h3>Support Request</h3>
            <p><strong>User ID:</strong> {user_id}</p>
            <p><strong>Message:</strong> {message}</p>
        """

        payload = sib_api_v3_sdk.SendSmtpEmail(
            sender=_sender_from_config(),
            to=[{"email": _require_env("ADMIN_EMAIL")}],
            subject="New Support Request",
            html_content=html_body,
            attachment=attachments or None,  # Brevo expects 'attachment'
        )

        resp = api.send_transac_email(payload)
        # In sandbox/message-id can be None
        return jsonify({
            "status": "success",
            "email_id": getattr(resp, "message_id", None)
        }), 200

    except ApiException as api_err:
        # Brevo API error
        return jsonify({
            "error": "Failed to send email (Brevo API error)",
            "details": str(api_err)
        }), 502
    except Exception as e:
        # Programming/config error (e.g., missing env)
        return jsonify({
            "error": "Failed to send email",
            "details": str(e)
        }), 500


@support_bp.route("/feedback", methods=["POST"])
def send_user_feedback():
    try:
        api = _brevo_client()

        data = request.get_json(silent=True) or {}
        user_id = data.get("user_id")
        subject = (data.get("subject") or "Feedback").strip()
        feedback = (data.get("feedback") or "No feedback provided").strip()
        rating = (data.get("rating") or "N/A")

        html_body = f"""
            <h3>User Feedback</h3>
            <p><strong>User ID:</strong> {user_id}</p>
            <p><strong>Subject:</strong> {subject}</p>
            <p><strong>Feedback:</strong> {feedback}</p>
            <p><strong>Rating:</strong> {rating}</p>
        """

        payload = sib_api_v3_sdk.SendSmtpEmail(
            sender=_sender_from_config(),
            to=[{"email": _require_env("ADMIN_EMAIL")}],
            subject=f"Feedback Received: {subject}",
            html_content=html_body,
        )

        resp = api.send_transac_email(payload)
        return jsonify({
            "status": "success",
            "email_id": getattr(resp, "message_id", None)
        }), 200

    except ApiException as api_err:
        return jsonify({
            "error": "Feedback submission failed (Brevo API error)",
            "details": str(api_err)
        }), 502
    except Exception as e:
        return jsonify({
            "error": "Feedback submission failed",
            "details": str(e)
        }), 500
