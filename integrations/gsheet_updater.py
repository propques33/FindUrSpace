import gspread
from google.oauth2.service_account import Credentials
import os
import base64
import json
from dotenv import load_dotenv
import datetime

load_dotenv()

def init_google_sheet(sheet_name="Opportunities"):
    # Define the scope for accessing Google Sheets and Drive
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    try:
        # Decode the base64-encoded JSON credentials from environment variables
        encoded_credentials = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_BASE64')
        if not encoded_credentials:
            return None
        
        decoded_credentials = base64.b64decode(encoded_credentials).decode('utf-8')
        credentials_info = json.loads(decoded_credentials)
        
        # Initialize Google credentials
        creds = Credentials.from_service_account_info(credentials_info, scopes=scope)
        client = gspread.authorize(creds)
        
        # Open the sheet by its URL
        sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1oAqrCyUQKJHtzeEmfy-96tea9qkrgVQDhu5f_Oebtos/edit#gid=1458518171")
        return sheet.worksheet(sheet_name)
    
    except Exception as e:
        return None

def update_google_sheet(sheet, user_data, property_data):
    if sheet is None:
        return
    
    try:
        # Convert datetime to string for the sheet
        date_created = property_data['date'].strftime('%Y-%m-%d %H:%M:%S')

        # Prepare the row data to insert into the Google Sheet
        row = [
            user_data.get('cname', 'Unknown'),     # Company Name
            date_created,                         # Date Created
            "Open",                               # Opportunity Status
            "",                                   # Opportunity Stage
            property_data.get('seats', 'N/A'),    # Number of seats
            property_data.get('city', 'N/A'),     # Location
            property_data.get('micromarket', 'N/A'),  # Micromarket
            property_data.get('budget', 'N/A'),   # Budget (Newly Added)
            user_data.get('name', 'Unknown'),     # Primary Contact (First)
            user_data.get('mobile_number', 'N/A'),# Phone Number
            user_data.get('email', 'N/A'),        # Email Address
            property_data.get('inventory_type', 'N/A'),
            property_data.get('hear_about', 'N/A'), 
            property_data.get('property_names', 'N/A'), # Option shared
            "",                                   # Notes by bot
            date_created                          # Opportunity Last Modified
        ]
        
        # Append the row to the sheet
        sheet.append_row(row)
    
    except Exception as e:
        pass

def handle_new_property_entry(db, property_data):
    try:
        # Initialize the Google Sheet
        sheet = init_google_sheet()

        # Fetch the user data from MongoDB using the provided user_id (already an ObjectId)
        user = db.users.find_one({"_id": property_data['user_id']})

        if user:
            # Ensure these fields are fetched properly
            user_name = user.get('name', 'Unknown')
            user_cname = user.get('company', 'Unknown')  # Company name
            user_email = user.get('email', 'N/A')
            user_mobile = user.get('contact', 'N/A')  # Mobile number field (adjust if your schema differs)

            # Prepare user data for Google Sheet update
            user_data = {
                'name': user_name,
                'cname': user_cname,  # Company name
                'email': user_email,
                'mobile_number': user_mobile  # Adjust field name if necessary
            }

            # Update the Google Sheet with user and property data
            update_google_sheet(sheet, user_data, property_data)
    except Exception as e:
        pass

def update_users_google_sheet(user_data):
    """Updates the Users sheet with new user information."""
    sheet = init_google_sheet(sheet_name="Users")  # Fetch the Users sheet

    if sheet is None:
        print("Failed to connect to Users Google Sheet.")
        return

    try:
        # Convert datetime to string for the sheet
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Prepare the row data for the Users sheet
        row = [
            user_data.get('name', 'Unknown'),     # Name
            user_data.get('contact', 'N/A'),      # Contact
            user_data.get('company', 'N/A'),      # Company
            user_data.get('email', 'N/A'),        # Email
            timestamp                              # Timestamp
        ]

        # Append the row to the Users sheet
        sheet.append_row(row)
        print("User data successfully added to Users Google Sheet.")

    except Exception as e:
        print(f"Error updating Users Google Sheet: {e}")


def handle_new_user_entry(user_data):
    """Handles the process of updating the Users Google Sheet when a new user submits Step 1."""
    try:
        # Update the Google Sheet with user data
        update_users_google_sheet(user_data)
    except Exception as e:
        print(f"Error handling new user entry: {e}")