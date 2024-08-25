import io
import json
import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from dotenv import load_dotenv
import base64
import os

# Load environment variables
load_dotenv()

def authenticate_google_drive():
    # Define the scope
    scope = ["https://www.googleapis.com/auth/drive"]

    # Decode the base64-encoded JSON credentials
    encoded_credentials = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_BASE64')
    decoded_credentials = base64.b64decode(encoded_credentials).decode('utf-8')
    credentials_info = json.loads(decoded_credentials)

    # Authenticate using service account credentials
    creds = Credentials.from_service_account_info(credentials_info, scopes=scope)
    
    return creds

def upload_pdf_to_google_drive(pdf_buffer, creds, filename):
    # Build the Google Drive service
    service = build('drive', 'v3', credentials=creds)
    
    # Define file metadata
    file_metadata = {'name': filename}
    
    # Upload the file
    media = MediaIoBaseUpload(pdf_buffer, mimetype='application/pdf')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()

    # Get the file ID
    file_id = file.get('id')

    # Make the file publicly accessible
    service.permissions().create(
        fileId=file_id,
        body={'type': 'anyone', 'role': 'reader'},
    ).execute()

    # Create the direct download link
    shareable_link = f"https://drive.google.com/uc?export=download&id={file_id}"
    print(f"PDF uploaded to Google Drive. Direct download link: {shareable_link}")
    
    return shareable_link


def send_pdf_via_noapp(shareable_link, recipient_number):
    # noApp API setup
    api_key = os.getenv('NOAPP_API_KEY')
    channel_key = os.getenv('NOAPP_CHANNEL_KEY')
    url = "https://crm.noapp.io/v1/api/message/send-messages"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "apiKey": api_key,
        "channelKey": channel_key
    }

    # Prepare the payload
    data = {
        "receivers": [
            {
                "name": "User",
                "bodyParams": [],
                "headerParams": {
                    "type": "header",
                    "parameters": [
                        {
                            "type": "document",
                            "document": {
                                "link": shareable_link,
                                "filename": "sample.pdf"
                            }
                        }
                    ]
                },
                "whatsappNumber": recipient_number
            }
        ],
        "template_name": "whatsapp_pdf",
        "broadcast_name": "pdf_broadcast"
    }

    # Convert the payload to JSON string
    payload = json.dumps(data)

    # Send the request to noApp API
    print("Sending PDF via WhatsApp using noApp API...")
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=120)
        print("Status Code:", response.status_code)
        
        try:
            response_json = response.json()
            print("Response JSON:", response_json)
        except json.JSONDecodeError:
            print("Failed to parse response as JSON. The response may be empty or not in JSON format.")

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
