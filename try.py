import json
from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB connection setup
def get_db():
    mongo_uri = os.environ.get('MONGO_URI')  # Ensure the MONGO_URI is defined in your .env file
    client = MongoClient(mongo_uri)
    db = client['FindUrSpace']  # Replace with your actual database name FindUrSpace
    return db

# Fetch and print documents from the users collection
def fetch_and_print_users():
    db = get_db()
    users_collection = db['users']  # Adjust 'users' if your collection name differs
    users = users_collection.find()  # Fetch all documents in the collection

    for user in users:
        # Convert ObjectId to string for easier readability
        user['_id'] = str(user['_id'])
        print(json.dumps(user, indent=4))

# Call the function
if __name__ == "__main__":
    fetch_and_print_users()
