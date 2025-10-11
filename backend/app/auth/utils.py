# utils.py
import os
from dotenv import load_dotenv, find_dotenv
from flask import current_app

# NEW: Brevo SDK imports
import sib_api_v3_sdk
# from sib_api_v3_sdk.rest import ApiException

load_dotenv(find_dotenv(usecwd=True))


def send_reset_email(to_email: str, app_link: str, web_link: str | None = None) -> None:
    """
    Fire‑and‑forget password reset email using Brevo (SendinBlue).
    """
    try:
        # Configure Brevo client from env
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = os.getenv("BREVO_API_KEY")
        api_client = sib_api_v3_sdk.ApiClient(configuration)
        emails_api = sib_api_v3_sdk.TransactionalEmailsApi(api_client)

        # ----- Plain text (kept simple) -----
        text_lines = [
            "Reset your GenFit password",
            "",
            f"Open in the app: {app_link}",
        ]
        if web_link:
            text_lines.append(f"Or open on the web: {web_link}")
        text_lines.extend(["", "If you didn’t request this, you can ignore this email."])
        text = "\n".join(text_lines)

        # ----- Dark brand HTML (unchanged from your Resend version) -----
        brand_bg   = "#121212"
        card_bg    = "#1c1c1c"
        accent     = "#7A5AF5"
        text_main  = "#EDEDED"
        text_muted = "#A8A8A8"
        divider    = "#2a2a2a"
        web_row_html = (
            f"""
            <tr>
              <td align="center" style="padding-top:12px;">
                <a href="{web_link}" target="_blank" rel="noopener"
                   style="font-size:14px; color:{text_muted}; text-decoration:none;">
                   Having trouble? Open on the web
                </a>
              </td>
            </tr>
            """ if web_link else ""
        )

        html = f"""<!doctype html>
            <html>
            <head>
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
            <meta name="color-scheme" content="dark">
            <meta name="supported-color-schemes" content="dark light">
            <title>Reset your GenFit password</title>
            <style>
            @media (max-width: 540px) {{
                .container {{ width: 100% !important; }}
                .card {{ padding: 20px !important; }}
                .logo {{ font-size: 20px !important; }}
            }}
            a.button {{
                display:inline-block; text-decoration:none; line-height:1.2;
                border-radius:12px; padding:14px 22px; font-weight:700;
            }}
            </style>
            </head>
            <body style="margin:0; padding:0; background:{brand_bg};">
            <div style="display:none; font-size:1px; color:#fff; line-height:1px; max-height:0; max-width:0; opacity:0; overflow:hidden;">
                Use this secure link to reset your GenFit password.
            </div>

            <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background:{brand_bg};">
                <tr>
                <td align="center" style="padding: 32px 16px;">
                    <table role="presentation" class="container" width="560" cellpadding="0" cellspacing="0" style="width:560px;">
                    <tr>
                        <td style="padding: 8px 0 16px 0; text-align:center;">
                        <div class="logo" style="font-family:Segoe UI, Roboto, Arial, sans-serif; color:{text_main}; font-weight:800; font-size:24px; letter-spacing:0.5px;">
                            GenFit
                        </div>
                        </td>
                    </tr>

                    <tr>
                        <td class="card" style="background:{card_bg}; border-radius:16px; padding:28px; border:1px solid {divider};">
                        <h1 style="margin:0 0 10px 0; font-family:Segoe UI, Roboto, Arial, sans-serif; color:{text_main}; font-size:20px;">
                            Reset your password
                        </h1>
                        <p style="margin:0 0 18px 0; font-family:Segoe UI, Roboto, Arial, sans-serif; color:{text_muted}; font-size:14px; line-height:1.5;">
                            Tap the button below to choose a new password. This link will expire soon for your security.
                        </p>

                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                            <tr>
                            <td align="center" style="padding: 8px 0 0 0;">
                                <a href="{app_link}" target="_blank" rel="noopener" class="button"
                                style="background:{accent}; color:#ffffff; font-family:Segoe UI, Roboto, Arial, sans-serif;">
                                Reset password
                                </a>
                            </td>
                            </tr>
                            {web_row_html}
                        </table>

                        <div style="height:1px; background:{divider}; margin:22px 0;"></div>

                        <p style="margin:0; font-family:Segoe UI, Roboto, Arial, sans-serif; color:{text_muted}; font-size:12px; line-height:1.6;">
                            Didn’t request this? You can safely ignore this email—your password won’t change.
                        </p>
                        </td>
                    </tr>

                    <tr>
                        <td style="text-align:center; padding:16px 4px 0 4px;">
                        <p style="margin:0; font-family:Segoe UI, Roboto, Arial, sans-serif; color:{text_muted}; font-size:12px;">
                            © {current_app.config.get("BRAND_COPYRIGHT", "GenFit")}
                        </p>
                        </td>
                    </tr>

                    </table>
                </td>
                </tr>
            </table>
            </body>
            </html>
        """

        # Compose & send via Brevo
        sender = current_app.config.get("MAIL_FROM", "ouattarabilly33@gmail.com")
        # Brevo needs a plain email address and optional name split:
        if "<" in sender and ">" in sender:
            name = sender.split("<")[0].strip().strip('"').strip()
            addr = sender.split("<")[1].split(">")[0].strip()
            sender_obj = {"name": name, "email": addr}
        else:
            sender_obj = {"email": sender}

        payload = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": to_email}],
            sender=sender_obj,
            subject="Reset your GenFit password",
            html_content=html,
            text_content=text,
        )
        resp = emails_api.send_transac_email(payload)
        print(resp)
        print("Sender: ", sender)
    except Exception:
        current_app.logger.exception("[forgot] failed to send reset email via Brevo")
