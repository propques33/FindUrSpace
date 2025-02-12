import io
import json
import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
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

def get_temp_pdfs_folder_id(service):
    # Check if the 'temp_pdfs' folder exists
    folder_name = 'temp_pdfs'
    query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    files = results.get('files', [])

    # If the folder exists, return the folder ID
    if files:
        return files[0]['id']
    
    # If the folder does not exist, create it and return the new folder ID
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    folder = service.files().create(body=file_metadata, fields='id').execute()
    return folder.get('id')

def upload_pdf_to_google_drive(pdf_buffer, creds, filename):
    # Build the Google Drive service
    service = build('drive', 'v3', credentials=creds)
    
    # Get or create the 'temp_pdfs' folder
    folder_id = get_temp_pdfs_folder_id(service)
    
    # Define file metadata
    file_metadata = {
        'name': filename,
        'parents': [folder_id]  # Upload the file into 'temp_pdfs' folder
    }
    
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


def send_pdf_via_cunnekt(shareable_link, recipient_number):
    # Cunnekt API setup
    api_key = os.getenv('CUNNEKT_API_KEY')
    url = "https://app2.cunnekt.com/v1/sendnotification"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "API-KEY": api_key
    }

    # Prepare the payload
    data = {
    "mobile": recipient_number,
    "templateid": "1844499816365738",
    "overridebot": "yes/no",
    "template": {
        "components": [
            {
                "type": "header",
                "parameters": [
                    {
                        "type": "document",
                        "document": {
                            "link": shareable_link,
                            "filename": "Your_Options.pdf" 
                        }
                    }
                ]
            },
            {
                "type": "body",
                "parameters": [
                        {"type": "text", "text": f"PDF Download Link: {shareable_link}"}
                    ]
            }
        ]
    }
}

    # Convert the payload to JSON string
    payload = json.dumps(data)

    # Send the request to Cunnekt API
    print("Sending PDF via WhatsApp using Cunnekt API...")
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


def get_coworking_folder_id(service):
    # Check if the 'coworking_spaces_layouts' folder exists
    folder_name = 'coworking_spaces_layouts'
    query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    files = results.get('files', [])

    # If the folder exists, return the folder ID
    if files:
        return files[0]['id']

    # If the folder does not exist, create it and return the new folder ID
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    folder = service.files().create(body=file_metadata, fields='id').execute()
    return folder.get('id')


def upload_image_to_google_drive(image_buffer, creds, filename):
    """
    Uploads an image to Google Drive and returns the shareable link.
    
    Parameters:
    - image_buffer: io.BytesIO buffer of the image to be uploaded.
    - creds: Google Drive API credentials.
    - filename: The name to give the uploaded file on Google Drive.
    
    Returns:
    - shareable_link: The direct download link of the uploaded file.
    """
    # Build the Google Drive service
    service = build('drive', 'v3', credentials=creds)

    # Get or create the 'coworking_spaces_layouts' folder
    folder_id = get_coworking_folder_id(service)

    # Define file metadata
    file_metadata = {
        'name': filename,
        'parents': [folder_id]  # Upload the file into 'coworking_spaces_layouts' folder
    }

    # Upload the image file
    media = MediaIoBaseUpload(image_buffer, mimetype='image/jpeg')
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
    print(f"Image uploaded to Google Drive. Direct download link: {shareable_link}")
    
    return shareable_link
