import os
from pymongo import MongoClient
from dotenv import load_dotenv
import logging
import time
import json  # Import JSON module for saving data locally

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    filename='migration.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def get_db():
    """
    Connects to the MongoDB instance using the connection string provided in the environment variables.
    """
    mongo_uri = os.environ.get('MONGO_URI')
    if not mongo_uri:
        raise ValueError("MONGO_URI is not set in the environment variables.")
    
    client = MongoClient(mongo_uri)
    db = client['FindYourSpace']  # Replace with your actual database name
    return db

def download_collection_as_json(db, collection_name):
    """
    Fetches all documents from the specified collection and saves them as a JSON file.
    """
    collection = db[collection_name]
    documents = list(collection.find({}))
    
    # File path for saving the collection
    file_name = f"{collection_name}.json"
    
    # Saving the documents as JSON
    with open(file_name, 'w') as f:
        json.dump(documents, f, default=str, indent=4)  # Using default=str to handle ObjectId serialization
    
    logging.info(f"Downloaded {len(documents)} documents from {collection_name} to {file_name}")
    print(f"Downloaded {len(documents)} documents from {collection_name} to {file_name}")

def download_all_collections(db):
    """
    Downloads all collections in the database and saves them as JSON files.
    """
    collection_names = db.list_collection_names()
    for collection_name in collection_names:
        try:
            download_collection_as_json(db, collection_name)
        except Exception as e:
            logging.error(f"Error downloading collection {collection_name}: {e}")
            print(f"Error downloading collection {collection_name}: {e}")

if __name__ == "__main__":
    try:
        # Initialize database connection
        db = get_db()

        # Download all collections in the database
        download_all_collections(db)

        print("All collections downloaded successfully. Check the log for details.")
    except Exception as e:
        logging.error(f"An error occurred during the download process: {e}")
        print(f"An error occurred during the download process: {e}")
