import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB connection setup
def get_db():
    mongo_uri = os.environ.get('MONGO_URI')  # Ensure the MONGO_URI is defined in your .env file
    client = MongoClient(mongo_uri)
    db = client['FindUrSpace']
    return db
