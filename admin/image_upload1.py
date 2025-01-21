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

# Compress image and convert to WebP at 80% quality
def compress_image(image_file, max_size_kb=512, max_dimensions=(1024, 1024)):
    try:
        img = Image.open(image_file)

        # Resize image if larger than the specified dimensions
        img.thumbnail(max_dimensions)

        # Buffer to hold the compressed image in memory
        buffer = BytesIO()

        # Convert the image to WebP format and save with 80% quality
        img.save(buffer, format="WEBP", quality=80)

        size_kb = buffer.tell() / 1024
        print(f"Compressed WebP image size: {size_kb:.2f} KB")
        
        buffer.seek(0)
        return buffer, "WEBP"
    except Exception as e:
        print(f"Error compressing image: {e}")
        raise

# Upload compressed image to DigitalOcean Space
def upload_image_to_space(image_buffer, file_name):
    try:
        # Upload the image to the correct folder within the DigitalOcean space
        file_key = f"findurspace/{file_name}"  # Folder structure in DigitalOcean Space
        s3_client.upload_fileobj(
            image_buffer,
            DO_SPACE_NAME,
            file_key,
            ExtraArgs={'ACL': 'public-read', 'ContentType': 'image/webp'}
        )

        print(f"Image uploaded to {file_key}")
        # Return the publicly accessible URL
        return f"{DO_ENDPOINT}/{file_key}"
    except Exception as e:
        print(f"Failed to upload image: {e}")
        return None

# Process and upload images
def process_and_upload_image(image_file, property_id):
    db = get_db()

    try:
        print(f"Processing file: {image_file.filename}")
        # Compress the image
        compressed_image, img_format = compress_image(image_file)

        # Create a unique file name using UUID
        unique_id = uuid.uuid4().hex
        original_filename = secure_filename(image_file.filename)  # Sanitize filename
        file_name = f"{property_id}_{unique_id}_{original_filename}"

        # Upload the compressed image to DigitalOcean Space
        image_url = upload_image_to_space(compressed_image, file_name)
        if not image_url:
            print(f"Failed to upload {image_file.filename}")
            return None
        
        # Debug: Check generated image URL
        print(f"Generated Image URL: {image_url}")

        # Update MongoDB with the uploaded image URL
        result = db.fillurdetails.update_one(
            {'_id': ObjectId(property_id)},  # Match by property ID
            {'$push': {'uploaded_images': image_url}}  # Create or append to the new field
        )

        # Debug: Check MongoDB update result
        if result.modified_count > 0:
            print(f"MongoDB Update Successful for property_id {property_id}")
        else:
            print(f"No MongoDB document updated for property_id {property_id}")
        return image_url

    except Exception as e:
        print(f"Error processing file {image_file.filename}: {e}")
        return None
