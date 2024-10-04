#image_upload.py
import os
import boto3
from PIL import Image
from io import BytesIO
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# DigitalOcean Spaces configurations
DO_SPACE_NAME = "findurspace"
DO_REGION = "blr1"  # Replace with your region
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

# Compress image to 512KB
def compress_image(image_file, max_size_kb=512):
    img = Image.open(image_file)
    img_format = img.format

    # Buffer to hold the compressed image in memory
    buffer = BytesIO()
    quality = 85  # Start with 85% quality

    while True:
        buffer.seek(0)
        buffer.truncate(0)
        img.save(buffer, format=img_format, quality=quality)
        size_kb = buffer.tell() / 1024

        if size_kb <= max_size_kb or quality <= 10:
            break
        quality -= 5

    buffer.seek(0)
    return buffer, img_format

# Upload compressed image to DigitalOcean Space
def upload_image_to_space(image_buffer, file_name):
    try:
        s3_client.upload_fileobj(
            image_buffer,
            DO_SPACE_NAME,
            f"findurspace/{file_name}",
            ExtraArgs={'ACL': 'public-read', 'ContentType': f'image/{file_name.split(".")[-1]}'}
        )
        return f"{DO_ENDPOINT}/findurspace/{file_name}"
    except Exception as e:
        print(f"Failed to upload image: {e}")
        return None

# Process and upload images
def process_and_upload_images(image_files, owner_info, coworking_name):
    db = get_db()
    image_urls = []

    for image_file in image_files:
        # Compress image
        compressed_image, img_format = compress_image(image_file)

        # Create a unique file name
        file_name = f"{coworking_name}_{owner_info['name']}_{image_file.filename}"

        # Upload image to DigitalOcean Space
        image_url = upload_image_to_space(compressed_image, file_name)
        if image_url:
            image_urls.append(image_url)
        else:
            print(f"Failed to upload {image_file.filename}")

    # Save image URLs to the database
    property_details = {
        'owner': owner_info,
        'coworking_name': coworking_name,
        'layout_images': image_urls,
        'date': datetime.now()
    }

    db.coworking_spaces.insert_one(property_details)
    print(f"Uploaded {len(image_urls)} images and saved them in DB.")

