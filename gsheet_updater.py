import gspread
from google.oauth2.service_account import Credentials
import os
import base64
import json
from dotenv import load_dotenv

load_dotenv()

def init_google_sheet():
    # Define the scope
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    # Decode the base64-encoded JSON credentials
    encoded_credentials = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_BASE64')
    decoded_credentials = base64.b64decode(encoded_credentials).decode('utf-8')
    credentials_info = json.loads(decoded_credentials)

    creds = Credentials.from_service_account_info(credentials_info, scopes=scope)
    
    client = gspread.authorize(creds)
    sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1oAqrCyUQKJHtzeEmfy-96tea9qkrgVQDhu5f_Oebtos/edit#gid=1458518171")
    return sheet.worksheet("Opportunities")



def update_google_sheet(sheet, user_data, property_data):

    # Convert datetime to string
    date_created = property_data['date'].strftime('%Y-%m-%d %H:%M:%S')
    
    # Preparing the row to insert into the Google Sheet
    row = [
        user_data['cname'],                     # Company Name
        date_created,                           # Date Created
        "Open",                                 # Opportunity Status
        "",                                     # Opportunity Stage
        property_data['seats'],                 # Number of seats
        property_data['city'],                  # Location
        property_data['micromarket'],           # Micromarket
        user_data['name'],                      # Primary Contact (First)
        user_data['mobile_number'],             # Phone Number
        user_data['email'],                     # Email Address
        property_data['property_names'],        # Option shared
        "",                                     # Notes by bot
        date_created                            # Opportunity Last Modified
    ]
    
    # Appending the row to the Opportunities sheet
    sheet.append_row(row)

def handle_new_property_entry(db, property_data):
    sheet = init_google_sheet()
    user = db.users.find_one({"_id": property_data['user_id']})
    
    if user:
        update_google_sheet(sheet, user, property_data)