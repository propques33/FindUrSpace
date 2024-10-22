import os
from pymongo import MongoClient
from dotenv import load_dotenv
import logging
import json

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    filename='migration_upload.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def get_db_from_new_cluster():
    """
    Connects to the new MongoDB cluster using the MONGO_URI_1 environment variable.
    """
    mongo_uri = os.environ.get('MONGO_URI_1')
    if not mongo_uri:
        raise ValueError("MONGO_URI_1 is not set in the environment variables.")
    
    client = MongoClient(mongo_uri)
    db = client['FindYourSpace']  # Use the same database name as the original
    return db

def upload_json_to_collection(db, collection_name, json_file):
    """
    Uploads documents from a JSON file to the specified collection in MongoDB.
    """
    collection = db[collection_name]
    
    with open(json_file, 'r') as f:
        documents = json.load(f)
    
    # Insert documents into the collection
    if documents:
        collection.insert_many(documents)
        logging.info(f"Uploaded {len(documents)} documents to {collection_name} from {json_file}")
        print(f"Uploaded {len(documents)} documents to {collection_name} from {json_file}")
    else:
        logging.warning(f"No documents found in {json_file}. Skipping upload to {collection_name}")
        print(f"No documents found in {json_file}. Skipping upload to {collection_name}")

def upload_all_collections(db):
    """
    Uploads all JSON files (collections) to the new MongoDB cluster.
    """
    for file_name in os.listdir():
        if file_name.endswith('.json'):
            collection_name = file_name.replace('.json', '')  # Remove .json extension for collection name
            try:
                upload_json_to_collection(db, collection_name, file_name)
            except Exception as e:
                logging.error(f"Error uploading collection {collection_name}: {e}")
                print(f"Error uploading collection {collection_name}: {e}")

if __name__ == "__main__":
    try:
        # Initialize connection to new database
        db = get_db_from_new_cluster()

        # Upload all collections to the new database
        upload_all_collections(db)

        print("All collections uploaded successfully. Check the log for details.")
    except Exception as e:
        logging.error(f"An error occurred during the upload process: {e}")
        print(f"An error occurred during the upload process: {e}")
