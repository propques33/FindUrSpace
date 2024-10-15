import os
import requests
from base64 import b64encode
import OTPLessAuthSDK

def send_whatsapp_verification(mobile):
    client_id = os.getenv('CLIENT_ID')
    client_secret = os.getenv('CLIENT_SECRET')
    redirect_uri = "https://findurspace.tech/operators/verify_mobile"
    channel = "WHATSAPP"

    # Remove leading zero from mobile number if present
    if mobile.startswith('0'):
        mobile = mobile.lstrip('0')

    if not mobile.startswith('+91'):
        mobile = f"+91{mobile}"

    user_details = OTPLessAuthSDK.UserDetail.generate_magic_link(
        mobile, None, client_id, client_secret, redirect_uri, channel
    )
    return user_details
