import os
from urllib.parse import quote
from datetime import datetime, timedelta, timezone
from flask import Blueprint, jsonify

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from botocore.signers import CloudFrontSigner

media_bp = Blueprint("media_bp", __name__)

CF_DOMAIN = os.environ["CLOUDFRONT_DOMAIN"]
CF_KEY_PAIR_ID = os.environ["CF_KEY_PAIR_ID"]
CF_PRIVATE_KEY_PEM_RAW = os.environ["CF_PRIVATE_KEY_PEM"]
MEDIA_TTL_SEC = int(os.environ.get("MEDIA_TTL_SEC", "300"))


def rsa_signer(message):
    # Load the private key from the environment variable string
    private_key = serialization.load_pem_private_key(
        CF_PRIVATE_KEY_PEM_RAW.encode("utf-8"),
        password=None,
        backend=default_backend()
    )
    
    # Return the RSA signature using SHA1 and PKCS#1 v1.5 padding
    return private_key.sign(
        message,
        padding.PKCS1v15(),
        hashes.SHA1()
    )

@media_bp.get("/media/animation/<path:key>")        
def get_signed_animation(key: str):   
    animation_path = quote(f"FULL HD 1080P/{key}.mp4", safe="/")
    animation_url = f'https://{CF_DOMAIN}/{animation_path}'           
    
    illustration_path = quote(f"Illustrations High Resolution/{key}.jpg", safe="/")
    illustration_url = f'https://{CF_DOMAIN}/{illustration_path}'     

    cloudfront_signer = CloudFrontSigner(CF_KEY_PAIR_ID, rsa_signer)
    
    # Singed links expiration dates
    animation_expire_date = datetime.now(timezone.utc) + timedelta(seconds=MEDIA_TTL_SEC)
    illustration_expire_date = datetime.now(timezone.utc) + timedelta(seconds=MEDIA_TTL_SEC)

    # Signed animation URL
    signed_animation_url = cloudfront_signer.generate_presigned_url(
        animation_url, 
        date_less_than=animation_expire_date
    )
    
    # Signed illustration URL
    signed_illustration_url = cloudfront_signer.generate_presigned_url(
        illustration_url, 
        date_less_than=illustration_expire_date
    )

    return jsonify({
        "success": True,
        "animation_url": signed_animation_url,
        "illustration_url": signed_illustration_url
    })


@media_bp.get("/media/illustration/<path:key>")
def get_signed_illustration(key: str):
    """
    Return only the signed CloudFront URL for the illustration (jpg).
    """
    try:
        # Normalize + encode path parts (preserve "/" between folders)
        illustration_path = quote(f"Illustrations High Resolution/{key}.jpg", safe="/")
        illustration_url = f"https://{CF_DOMAIN}/{illustration_path}"

        # Use a longer TTL for illustrations
        now_utc = datetime.now(timezone.utc)
        illustration_expire_date = now_utc + timedelta(hours=24)

        cloudfront_signer = CloudFrontSigner(CF_KEY_PAIR_ID, rsa_signer)

        signed_illustration_url = cloudfront_signer.generate_presigned_url(
            illustration_url,
            date_less_than=illustration_expire_date
        )

        return jsonify({
            "success": True,
            "illustration_url": signed_illustration_url
        })

    except Exception as e:
        # log and return an error JSON (avoid exposing sensitive internals)
        return jsonify({"success": False, "error": "failed_to_generate_signed_url"}), 500
    