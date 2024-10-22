import os
from pymongo import MongoClient, ASCENDING
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB connection setup
def get_db():
    mongo_uri = os.environ.get('MONGO_URI')  # Ensure the MONGO_URI is defined in your .env file
    client = MongoClient(mongo_uri)
    db = client['FindYourSpace']
    return db

# Initialize indexes for better querying performance
def initialize_indexes(db):
    # Indexes can speed up queries on frequently searched fields like email, date, etc.
    db.email_logs.create_index([('email', ASCENDING), ('date', ASCENDING)])
    db.coworking_spaces.create_index([('city', ASCENDING), ('micromarket', ASCENDING), ('price', ASCENDING)])

# Function to clean up old logs (if needed)
def delete_old_logs(db):
    limit_date = datetime.datetime.now() - datetime.timedelta(days=30)
    result = db.email_logs.delete_many({'date': {'$lt': limit_date}})
    print(f"Deleted {result.deleted_count} old logs.")

# Usage Example:
# db = get_db()
# initialize_indexes(db)
