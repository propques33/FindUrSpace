import os
import requests
from base64 import b64encode
import OTPLessAuthSDK

def send_whatsapp_message_with_pdf(to_number):
    api_key = os.getenv('GUPSHUP_API_KEY')
    from_whatsapp_number = os.getenv('GUPSHUP_WHATSAPP_NUMBER')
    template_id = os.getenv('GUPSHUP_TEMPLATE_ID')  # Load template ID from .env file

    url = "https://api.gupshup.io/sm/api/v1/msg"

    # Load the static PDF file
    with open('static/pdffin.pdf', 'rb') as f:
        pdf_base64 = b64encode(f.read()).decode('utf-8')

    data = {
        'channel': 'whatsapp',
        'source': from_whatsapp_number,
        'destination': f"whatsapp:{to_number}",
        'message': {
            'type': 'template',
            'template': {
                'id': template_id,
                'params': ["Dear Customer"],  # Replace this with actual parameter if needed
                'media': {
                    'url': f'data:application/pdf;base64,{pdf_base64}',
                    'filename': 'property_data.pdf'
                }
            }
        }
    }

    headers = {
        'Content-Type': 'application/json',
        'apikey': api_key
    }

    response = requests.post(url, json=data, headers=headers)

    if response.status_code == 202:
        print(f"WhatsApp message sent successfully to {to_number}.")
    else:
        print(f"Failed to send WhatsApp message. Status Code: {response.status_code}, Response: {response.text}")



def send_whatsapp_verification(mobile):
    client_id = os.getenv('CLIENT_ID')
    client_secret = os.getenv('CLIENT_SECRET')
    redirect_uri = "https://findurspace-app-i989y.ondigitalocean.app/verify_mobile"
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
