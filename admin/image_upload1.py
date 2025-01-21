import os
import boto3
from PIL import Image
from io import BytesIO
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime
import uuid  # For unique filename generation
from werkzeug.utils import secure_filename  # For sanitizing filenames
from bson import ObjectId

# Load environment variables
load_dotenv()

# DigitalOcean Spaces configurations
DO_SPACE_NAME = "findurspace"
DO_REGION = "blr1"
DO_ENDPOINT = f"https://{DO_SPACE_NAME}.{DO_REGION}.digitaloceanspaces.com"
DO_SPACES_KEY = os.getenv("DO_SPACES_KEY")
DO_SPACES_SECRET = os.getenv("DO_SPACES_SECRET")

# Initialize boto3 client
session = boto3.session.Session()
s3_client = session.client(
    's3',
    region_name=DO_REGION,
    endpoint_url=DO_ENDPOINT,
    aws_access_key_id=DO_SPACES_KEY,
    aws_secret_access_key=DO_SPACES_SECRET
)

# MongoDB connection setup
def get_db():
    mongo_uri = os.getenv('MONGO_URI')  # Ensure the MONGO_URI is defined in your .env file
    client = MongoClient(mongo_uri)
    db = client['FindYourSpace']
    return db

# Upload compressed image to DigitalOcean Space
def upload_pdf_to_space(pdf_file, file_name):
    try:
        # Upload the image to the correct folder within the DigitalOcean space
        file_key = f"{file_name}"  # Folder structure in DigitalOcean Space
        s3_client.upload_fileobj(
            pdf_file,
            DO_SPACE_NAME,
            file_key,
            ExtraArgs={'ACL': 'public-read', 'ContentType': 'application/pdf'}
        )

        print(f"PDF uploaded to {file_key}")
        # Return the publicly accessible URL
        return f"{DO_ENDPOINT}/{file_key}"
    except Exception as e:
        print(f"Failed to upload PDF: {e}")
        return None

# Process and upload images
def process_and_upload_pdf(pdf_file):
    try:
        print(f"Processing PDF: {pdf_file.filename}")

        # Create a unique file name using UUID
        unique_id = uuid.uuid4().hex
        original_filename = secure_filename(pdf_file.filename)  # Sanitize filename
        file_name = f"{unique_id}_{original_filename}"

        # Upload the PDF to DigitalOcean Space
        pdf_url = upload_pdf_to_space(pdf_file, file_name)
        if not pdf_url:
            print(f"Failed to upload {pdf_file.filename}")
            return None
        
        # Debug: Check generated image URL
        print(f"Generated Image URL: {pdf_url}")
        return pdf_url

    except Exception as e:
        print(f"Error processing PDF {pdf_file.filename}: {e}")
        return None
