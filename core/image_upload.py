# image_upload.py

import os
import boto3
from PIL import Image
from io import BytesIO
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime
import uuid  # Import uuid for unique filename generation
from werkzeug.utils import secure_filename  # Import secure_filename

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
def compress_image(image_file, max_size_kb=300, max_dimensions=(1024, 1024)):
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

# Upload compressed image to DigitalOcean Space
def upload_image_to_space(image_buffer, file_name):
    try:
        # Upload the image to the correct folder within the DigitalOcean space
        s3_client.upload_fileobj(
            image_buffer,
            DO_SPACE_NAME,
            f"{file_name}",  # Ensure only one 'findurspace/' folder
            ExtraArgs={'ACL': 'public-read', 'ContentType': 'image/webp'}
        )

        print(f"Image uploaded to {file_name}")
        # Return the correct URL format with the nested folder structure
        return f"{DO_ENDPOINT}/findurspace/{file_name}"
    except Exception as e:
        print(f"Failed to upload image: {e}")
        return None

# Process and upload images
def process_and_upload_images(image_files, owner_info, coworking_name,category="general", space_id=None, inventory_id=None, room_id=None):
    db = get_db()
    image_urls = []

    for image_file in image_files:
        if not image_file or image_file.filename == '':
            continue  # Skip empty files

        try:
            print(f"Processing file: {image_file.filename}")
            # Compress image
            compressed_image, img_format = compress_image(image_file)

            # Create a unique file name using UUID
            unique_id = uuid.uuid4().hex
            # Secure the original filename to prevent directory traversal attacks
            original_filename = secure_filename(image_file.filename)
            file_extension = ".webp"
            # Enhanced Naming Convention:
            # /findurspace/<category>/<spaceId>/<inventoryId>/<filename>
            # /findurspace/<category>/<spaceId>/<inventoryId>/<roomId>/<filename>
            # if space_id and inventory_id and room_id:  # ✅ Room images
            #     file_name = f"{category}/{coworking_name}/{space_id}/{inventory_id}/room_{room_id}/{unique_id}_{original_filename}"
            # elif space_id and inventory_id:  # ✅ Inventory images
            #     file_name = f"{category}/{coworking_name}/{space_id}/{inventory_id}/{unique_id}_{original_filename}"
            # elif space_id:  # ✅ Property images
            #     file_name = f"{category}/{coworking_name}/{space_id}/{unique_id}_{original_filename}"
            # else:  # ✅ General images
            #     file_name = f"{category}/{coworking_name}/{unique_id}_{original_filename}"

            # Construct folder path based on provided IDs
            file_path = f"findurspace/{category}/{coworking_name}"  # Base path

            if space_id:
                file_path += f"/{space_id}"
            if inventory_id:
                file_path += f"/inventory_{inventory_id}"
            if room_id:
                file_path += f"/room_{room_id}"

            # Final file path including filename
            file_name = f"{file_path}/{unique_id}_{original_filename}{file_extension}"
            
            # Upload image to DigitalOcean Space
            image_url = upload_image_to_space(compressed_image, file_name)
            if image_url:
                image_urls.append(image_url)
            else:
                print(f"Failed to upload {image_file.filename}")
        except Exception as e:
            print(f"Error processing file {image_file.filename}: {e}")

    return image_urls
