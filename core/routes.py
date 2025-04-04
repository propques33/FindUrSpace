# current routes.py
from flask import Blueprint, render_template, request, jsonify, flash, session, current_app, send_from_directory, redirect, url_for,make_response
from collections import defaultdict
from core.email_handler import send_email_and_whatsapp_with_pdf1
from bson import ObjectId  # Import ObjectId to handle MongoDB _id type conversion
from bson.regex import Regex
import threading
import io
import re
import os
import pandas as pd
import requests
from dotenv import load_dotenv
from integrations.gsheet_updater import handle_new_property_entry
from integrations.google_drive_integration import authenticate_google_drive, upload_image_to_google_drive
from core.image_upload import process_and_upload_images
from integrations.otplessauth import OtpLessAuth
from integrations.gsheet_updater import handle_new_user_entry
import random  # Import random module at the top
from datetime import datetime, timedelta


# Function to handle Google Sheet updates in the background
def update_gsheet_background(app, db, property_data):
    with app.app_context():  # Ensure app context is available in the background thread
        try:
            handle_new_property_entry(db, property_data)  # Update the Google Sheet
        except Exception as e:
            print(f"Failed to update Google Sheet: {e}")


# Helper function to send the email and WhatsApp in the background
def send_email_and_whatsapp_background(app, email, name, contact, filtered_properties):
    with app.app_context():  # Push the application context
        try:
            print("Sending email and WhatsApp with the following details:")
            print(f"Email: {email}, Name: {name}, Contact: {contact}")
            print(f"Filtered Properties: {filtered_properties}")
            success, _ = send_email_and_whatsapp_with_pdf1(email, name, contact, filtered_properties)
            print("Email and whatapp sent successfully")
        except Exception as e:
            print(f"Failed to send email and whatsapp: {e}")


# Helper function to parse price strings and convert to float
def parse_price(price_str):
    try:
        return float(str(price_str).replace(',', '').replace('₹', ''))
    except (ValueError, TypeError):
        return 0.0

# Helper function to get max budget with 20% buffer
# def get_max_budget(budget):
#     try:
#         # Remove any currency symbols and commas, convert to float
#         budget = float(str(budget).replace(',', '').replace('₹', ''))
#         # Allow for a 20% variance above the budget
#         return budget * 1.2  # 20% above budget
#     except (ValueError, TypeError):
#         return float('inf')

# Helper function to get lowest price from inventory
def get_lowest_price(inventory):
    lowest_price = float('inf')
    for item in inventory:
        if item.get('type') not in ['Meeting rooms', 'Conference rooms']:
            price = parse_price(item.get('price_per_seat', 0))
            if price > 0:  # Ensure we don't consider zero or invalid prices
                lowest_price = min(lowest_price, price)
    return lowest_price if lowest_price != float('inf') else 0

# Define the Blueprint for core routes
core_bp = Blueprint('core_bp', __name__)

@core_bp.route('/send_otp', methods=['POST'])
def send_otp():
    mobile = request.json.get('mobile')
    if not mobile:
        return jsonify({'success': False, 'message': 'Mobile number is required'})

    otp_service = OtpLessAuth()
    response = otp_service.send_otp(mobile)

    if response['success']:
        session['contact'] = mobile  # Store mobile in session
        return jsonify({'success': True, 'requestId': response['requestId']})
    else:
        return jsonify({'success': False, 'message': response.get('message', 'Failed to send OTP')})

# @core_bp.route('/outerpage')
# def outerpage():
#     db = current_app.config['db']  # Access the MongoDB instance

#     # Fetch records with 'new' field set to True
#     records = list(db.fillurdetails.find({"status": 'new'}))

#     # Debugging line (optional): Print fetched records in console
#     print("Fetched Records:", records)

#     return render_template('outerpage.html', records=records)

from flask import render_template, request, current_app

@core_bp.route('/outerpage')
def outerpage():
    db = current_app.config['db']  # Access the MongoDB instance
    contact = request.args.get('contact', None)  # Get contact from URL param
    filter_city = request.args.get('location', None)
    filter_micromarket = request.args.get('area', None)
    filter_inventory_type = request.args.get('inventoryType', None)
    page = request.args.get('page', 1, type=int)

    # If contact is provided, fetch User ID
    user_id = None
    user_preferences = None
    if contact:
        user = db.users.find_one({'contact': contact})
        if user:
            user_id = str(user['_id'])
            # Get user preferences using user_id
            user_preferences = db.properties.find_one({'user_id': ObjectId(user_id)})
    
    if user_preferences and not filter_city and not filter_micromarket and not filter_inventory_type:
        filter_city = user_preferences.get('city')
        filter_micromarket = user_preferences.get('micromarket')
        filter_inventory_type = user_preferences.get('inventory_type')

    # Normalize inventory type to match DB values (e.g., 'Daypass' → 'Day pass')
    normalized_inventory_type = None
    if filter_inventory_type:
        for record in db.fillurdetails.find({"status": 'new'}):
            for inventory in record.get('inventory', []):
                db_type = inventory.get('type', '')
                if db_type.replace(" ", "").lower() == filter_inventory_type.replace(" ", "").lower():
                    normalized_inventory_type = db_type
                    break
            if normalized_inventory_type:
                break

    # Pagination Variables
    cards_per_page = 6
    # page = request.args.get('page', 1, type=int)

    # Fetch records from fillurdetails based on filters
    if filter_city and filter_micromarket:
        records = list(db.fillurdetails.find({
            "city": {'$regex': f'^{filter_city}$', '$options': 'i'},
            "micromarket": {'$regex': f'^{filter_micromarket}$', '$options': 'i'},
            "status": 'new'
        }))
    else:
        # If no filters, fallback to showing all records with status 'new'
        records = list(db.fillurdetails.find({"status": 'new'}))
    
    # Flatten records into individual cards
    all_cards = []
    for record in records:
        if 'inventory' not in record:
            continue  # Skip records without an inventory field

        for inventory in record['inventory']:
            if normalized_inventory_type and inventory['type'] != normalized_inventory_type:
                continue  # Skip inventories that don't match the preferred type

            #Generate random star rating and reviews count
            star_rating = round(random.uniform(3.5, 5.0), 1)  # Between 3.5 and 5.0
            review_count = random.randint(10, 500)  # Between 10 and 500
                
            # Day Pass, Dedicated Desk, and Virtual Office as single cards
            if inventory['type'] in ["Day pass", "Dedicated desk", "Virtual office"]:
                all_cards.append({
                    'record': record,
                    'inventory': inventory,
                    'type': inventory['type'],
                    'price': inventory.get('price_per_seat', 0),
                    'star_rating': star_rating,  # Pass random rating
                    'review_count': review_count,
                    'images': inventory.get('images', [])   # Pass random reviews count
                })
            # Meeting Rooms as separate cards for each room
            elif inventory['type'] == "Meeting rooms" and 'room_details' in inventory:
                for room in inventory['room_details']:
                    all_cards.append({
                        'record': record,
                        'inventory': inventory,
                        'type': f"{room['seating_capacity']} Seater Meeting Room",
                        'price': room.get('price', 0),
                        'images': room.get('images', []),
                        'star_rating': round(random.uniform(3.5, 5.0), 1),
                        'review_count': random.randint(10, 500),
                        'room_number': room.get('room_number')
                    })
            # Private Cabins as separate cards for each cabin
            elif inventory['type'] == "Private cabin" and 'room_details' in inventory:
                for cabin in inventory['room_details']:
                    all_cards.append({
                        'record': record,
                        'inventory': inventory,
                        'type': f"{cabin['seating_capacity']} Seater Private Cabin",
                        'price': cabin.get('price', 0),
                        'images': cabin.get('images', []),
                        'star_rating': round(random.uniform(3.5, 5.0), 1),
                        'review_count': random.randint(10, 500),
                        'room_number': cabin.get('room_number')
                    })  

    # Pagination Logic
    total_cards = len(all_cards)
    total_pages = (total_cards + cards_per_page - 1) // cards_per_page
    start = (page - 1) * cards_per_page
    end = start + cards_per_page
    paginated_cards = all_cards[start:end]

    # Debugging line (optional): Check the cards being sent to template
    print("Paginated Cards:", paginated_cards)

    return render_template('outerpage.html', cards=paginated_cards, page=page, total_pages=total_pages,contact=contact,
        location=filter_city,
        area=filter_micromarket,
        inventoryType=filter_inventory_type)


@core_bp.route('/get_user_by_contact')
def get_user_by_contact():
    db = current_app.config['db']
    contact = request.args.get('contact')
    user = db.users.find_one({"contact": contact})
    if user:
        return jsonify({
            "name": user.get("name"),
            "email": user.get("email")
        })
    return jsonify({})

def split_camel_case(s):
    return re.sub(r'(?<!^)(?=[A-Z])', ' ', s)
    
@core_bp.route('/flexspace/<city>/<micromarket>/<coworking_name>')
def innerpage(city, micromarket, coworking_name):
    from bson import ObjectId
    db = current_app.config['db']
    raw_inventory_type = request.args.get('inventoryType', None)
    seating = request.args.get('seating', request.args.get('seats', None))
    contact = request.args.get('contact', None)  # Capture contact from the URL
    razorpay_key = current_app.config.get("RAZORPAY_KEY_ID")

    # Session validation for OTP verification
    verified_contact = session.get('verified_contact')
    is_verified = verified_contact == contact if contact else False

    # Invalidate session if someone manually changes contact in URL
    if contact and verified_contact and verified_contact != contact:
        session['verified_contact'] = None
        is_verified = False

    # Fetch the property details from the database using city, micromarket, and coworking_name
    property_data = db.fillurdetails.find_one({
        "city": {'$regex': f'^{city}$', '$options': 'i'},
        "micromarket": {'$regex': f'^{micromarket}$', '$options': 'i'},
        "coworking_name": {'$regex': f'^{coworking_name}$', '$options': 'i'}
    })

    if not property_data:
        return "Property not found", 404

    # property_id = property_data["_id"]

    # Normalize inventoryType from raw URL (e.g. Meetingrooms → Meeting rooms)
    inventory_type = None
    if raw_inventory_type:
        for inventory in property_data.get('inventory', []):
            db_inventory_type = inventory.get("type", "")
            if db_inventory_type.replace(" ", "").lower() == raw_inventory_type.replace(" ", "").lower():
                inventory_type = db_inventory_type
                break

    # Fetch user details if contact is provided
    user_data = None
    property_details = None  # To store seats and budget
    is_user_complete = False  # 🔹 Initialize flag

    if contact:
        user_data = db.users.find_one({'contact': contact}, {"_id": 1, "name": 1, "contact": 1, "company": 1, "email": 1})

        if user_data:
            user_data["_id"] = str(user_data["_id"])  # Convert ObjectId to string
            user_id = user_data["_id"]  # Get the user ID safely

            is_user_complete = bool(user_data.get("name") and user_data.get("email"))  # ✅ Step 1: Compute flag

            # Fetch property details using user_id
            property_details = db.properties.find_one({'user_id': ObjectId(user_id)}, {"_id": 0, "seats": 1, "budget": 1})

    # Set default values if no data found
    seats = property_details.get("seats", "Not Specified") if property_details else "Not Specified"
    budget = property_details.get("budget", "Not Specified") if property_details else "Not Specified"

    # Extract amenities
    amenities = property_data.get("amenities", [])

    # Extract office timings
    office_timings = property_data.get("office_timings", {})

    # Extract opening and closing times
    opening_time_str = office_timings.get("opening_time", "09:00")  # Default to 09:00 if not found
    closing_time_str = office_timings.get("closing_time", "21:30")  # Default to 21:30 if not found

    # Convert string time to datetime objects
    opening_time = datetime.strptime(opening_time_str, "%H:%M")
    closing_time = datetime.strptime(closing_time_str, "%H:%M")

    # Generate time slots (1-hour interval)
    time_slots = []
    current_time = opening_time
    while current_time < closing_time:
        time_slots.append(current_time.strftime("%I:%M %p"))  # Format as AM/PM
        current_time += timedelta(hours=1)


    # Extract the relevant inventory based on inventoryType
    # selected_inventory = None
    # inventory_images = []  
    # if inventory_type:
    #     for inventory in property_data.get('inventory', []):
    #         if inventory.get('type') == inventory_type:
    #             selected_inventory = inventory
                
    #             if 'images' in inventory and inventory['images']:
    #                 inventory_images.extend(inventory['images'])

    #             if 'room_details' in inventory:
    #                 for room in inventory['room_details']:
    #                     inventory_images.extend(room.get('images', []))

    #             break  

    # Selected Inventory + Image Logic
    property_images = property_data.get('property_images', [])

    selected_inventory = None
    selected_room = None
    inv_imgs = []

    seat_count = 1  # default
    total_price = 0  # default
    if inventory_type:
        for inventory in property_data.get('inventory', []):
            if inventory.get('type') == inventory_type:
                if seating and 'room_details' in inventory:
                    for room in inventory['room_details']:
                        if str(room.get('seating_capacity')) == str(seating):
                            selected_inventory = inventory
                            selected_room = room
                            inv_imgs = room.get('images', [])[:2] if room.get('images') else []
                            seat_count = int(seating)
                            break
                else:
                    selected_inventory = inventory
                    inv_imgs = inventory.get('images', [])[:2] if inventory.get('images') else []
                    seat_count = int(seating) if seating else inventory.get('count', 1)
                break

    # Calculate total price only for relevant types
    if inventory_type in ["Meeting rooms", "Private cabin"]:
        if selected_room and 'price' in selected_room:
            total_price = selected_room['price']
        else:
            total_price = selected_inventory.get('price_per_seat', 0)

    combined_images = inv_imgs + property_images
    seen = set()
    inventory_images = []
    for img in combined_images:
        if img and img not in seen:
            seen.add(img)
            inventory_images.append(img)

    meeting_group = ["Day pass", "Meeting rooms"]
    desk_group = ["Dedicated desk", "Private cabin", "Virtual office"]

    other_inventories = []
    for inventory in property_data.get('inventory', []):
        
        if inventory.get('type') == inventory_type:
            # Handle other seating variants (for Meeting rooms & Private cabin)
            if 'room_details' in inventory:
                for room in inventory['room_details']:
                    if str(room.get("seating_capacity")) == str(seat_count):
                        continue  # Skip the same seat count

                    # Include other seating variants
                    first_image = room['images'][0] if room.get('images') else None
                    other_inventories.append({
                        "type": inventory_type,
                        "price": room.get('price', 0),
                        "price_label": "/hour" if inventory_type == "Meeting rooms" else "/seat/month",
                        "first_image": first_image,
                        "coworking_name": property_data.get("coworking_name", "N/A"),
                        "micromarket": property_data.get("micromarket", "N/A"),
                        "city": property_data.get("city", "N/A"),
                        "star_rating": round(random.uniform(3.5, 5.0), 1),
                        "review_count": random.randint(10, 500),
                        "seating_capacity": room.get("seating_capacity")
                    })
            continue  # Skip rest of loop
 

        if (inventory_type in desk_group and inventory['type'] not in desk_group) or \
           (inventory_type in meeting_group and inventory['type'] not in meeting_group):
            continue  

        star_rating = round(random.uniform(3.5, 5.0), 1)  
        review_count = random.randint(10, 500)  

        first_image = None

        if inventory.get('images'):
            first_image = inventory['images'][0]

        elif inventory.get('room_details'):
            for room in inventory['room_details']:
                if room.get('images'):
                    first_image = room['images'][0]
                    break

        coworking_name = property_data.get("coworking_name", "N/A")
        micromarket = property_data.get("micromarket", "N/A")
        city = property_data.get("city", "N/A")
        seating_capacity = inventory.get("seating_capacity", "N/A")
        
        # Format price per unit
        if inventory['type'] == "Day pass":
            price_label = "/seat/day"
        elif inventory['type'] == "Dedicated desk":
            price_label = "/seat/month"
        elif "Meeting Room" in inventory['type']:
            price_label = "/hour"
        elif inventory['type'] == "Virtual office":
            price_label = "/year"
        elif "Private Cabin" in inventory['type']:
            price_label = "/seat/month"
        else:
            price_label = ""
            

        other_inventories.append({
            "type": inventory['type'],
            "price": inventory.get('price_per_seat', 0),
            "price_label": price_label,
            "first_image": first_image,
            "coworking_name": coworking_name,
            "micromarket": micromarket,
            "city": city,
            "star_rating": star_rating,
            "review_count": review_count
        })

    return render_template(
        'innerpage.html',
        property=property_data,
        inventoryType=inventory_type,
        selected_inventory=selected_inventory ,
        selected_room=selected_room,  # Pass the selected inventory to the template
        contact=contact,  # Pass contact for user tracking
        user_data=user_data or {},  # Pass user details if needed
        seats=seats,
        budget=budget,
        razorpay_key=razorpay_key,
        inventory_images=inventory_images,  # Pass inventory-specific images
        property_images=property_images,  # Pass all property images
        office_timings=property_data.get("office_timings", {}),
        amenities=amenities,  # Pass amenities dynamically
        other_inventories=other_inventories,  # Pass the other inventory data to template
        time_slots=time_slots,
        is_user_complete=is_user_complete,
        total_price=total_price,
        seat_count=seat_count ,
        is_verified=is_verified   # Pass time slots to the template
    )

@core_bp.route('/store_verified_contact', methods=['POST'])
def store_verified_contact():
    data = request.get_json()
    contact = data.get("contact")

    if not contact:
        return jsonify({"success": False, "message": "Contact number missing"}), 400

    # ✅ Store in session
    session['verified_contact'] = contact

    return jsonify({"success": True, "message": "Contact verified and stored in session"})


@core_bp.route('/<city>/<micromarket>/<coworking_name>')
def innerpage_direct(city, micromarket, coworking_name):
    return innerpage(city, micromarket, coworking_name)


@core_bp.route('/schedule_tour', methods=['POST'])
def schedule_tour():
    db = current_app.config['db']

    # Parse form data
    data = request.json
    user_id = data.get("user_id")
    property_id = data.get("property_id")
    name = data.get("name")
    email = data.get("email")
    company = data.get("company")
    contact = data.get("contact")
    inventory_type = data.get("inventoryType")
    date = data.get("date")
    time = data.get("time")
    message = data.get("message")
    move_in_date = data.get("moveInDate", None)  # Optional
    duration = data.get("duration", None)  # Optional
    gstin = data.get("gstin", None)  # Optional
    num_seats = data.get("numSeats")
    budget = data.get("budget")
    seat_count = int(num_seats) if num_seats and str(num_seats).isdigit() and int(num_seats) > 1 else ""



    # Check if user exists
    user = db.users.find_one({"contact": contact})

    if user:
        # Update existing user
        db.users.update_one(
            {"contact": contact},
            {"$set": {
                "name": data.get("name"),
                "company": data.get("company"),
                "email": data.get("email"),
                "updated_at": datetime.utcnow()
            }}
        )
        user_id = user["_id"]
    else:
        # Create a new user record
        new_user = {
            "name": data.get("name"),
            "contact": contact,
            "company": data.get("company"),
            "email": data.get("email"),
            "created_at": datetime.utcnow()
        }
        user_id = db.users.insert_one(new_user).inserted_id

    # Validate required fields
    if not user_id or not property_id or not name or not email or not contact or not date or not time:
        return jsonify({"success": False, "message": "Missing required fields"}), 400

    # Convert user_id and property_id to ObjectId
    try:
        user_id = ObjectId(user_id)
        property_id = ObjectId(property_id)
    except:
        return jsonify({"success": False, "message": "Invalid user or property ID"}), 400

    if inventory_type in ["Meeting rooms", "Private cabin"] and seat_count:
        formatted_inventory_type = f"{seat_count} Seater {inventory_type}"
    else:
        formatted_inventory_type = inventory_type


    # Prepare document for MongoDB
    visit_data = {
        "user_id": user_id,
        "property_id": property_id,
        "name": name,
        "email": email,
        "company": company,
        "contact": contact,
        "inventory_type": formatted_inventory_type,
        "date": datetime.strptime(date, "%Y-%m-%d"),
        "time": time,
        "message": message,
        "move_in_date": datetime.strptime(move_in_date, "%Y-%m-%d") if move_in_date else None,
        "duration": duration,
        "gstin": gstin,
        "num_seats": num_seats,
        "budget": budget,
        "status": "pending", 
        "created_at": datetime.utcnow()
    }

    # Insert into MongoDB
    db.visits.insert_one(visit_data)

    return jsonify({"success": True,"contact": contact, "message": "Tour scheduled successfully!"})


@core_bp.route('/submit_purchase', methods=['POST'])
def submit_purchase():
    db = current_app.config['db']  # Access the MongoDB database
    booking_collection = db["booking"]  # Reference the 'booking' collection


    try:
        data = request.json
        contact = data.get("phone")
        inventory_type = data.get("inventoryType")
        # Fix seat_count and inventory formatting
        seat_count = int(data.get("quantity", 0))
        formatted_inventory_type = inventory_type

        if inventory_type in ["Meeting rooms", "Private cabin"] and seat_count > 1:
            formatted_inventory_type = f"{seat_count} Seater {inventory_type}"

        if not contact:
            return jsonify({"success": False, "message": "Phone number is required"}), 400

        # Check if user exists
        user = db.users.find_one({"contact": contact})

        if user:
            # Update existing user
            db.users.update_one(
                {"contact": contact},
                {"$set": {
                    "name": data.get("fullName"),
                    "company": data.get("company"),
                    "email": data.get("email"),
                    "updated_at": datetime.utcnow()
                }}
            )
            user_id = user["_id"]
        else:
            # Create a new user record
            new_user = {
                "name": data.get("fullName"),
                "contact": contact,
                "company": data.get("company"),
                "email": data.get("email"),
                "created_at": datetime.utcnow()
            }
            user_id = db.users.insert_one(new_user).inserted_id

        # Required fields for validation
        required_fields = ["inventoryType", "quantity", "totalPrice", "fullName", "email", "phone", "date"]
        if not all(field in data for field in required_fields):
            return jsonify({"success": False, "message": "Missing required fields"}), 400

        # Convert date string to datetime object
        try:
            booking_date = datetime.strptime(data["date"], "%Y-%m-%d")
        except ValueError:
            return jsonify({"success": False, "message": "Invalid date format"}), 400

        # Optional time field for Meeting Rooms
        booking_time = data.get("time", None)

        # Fetch user_id using contact number
        user_data = db.users.find_one({"contact": data["phone"]}, {"_id": 1})
        user_id = str(user_data["_id"]) if user_data else None

        # Store booking in MongoDB
        booking = {
            "user_id": user_id,  # Store user_id if found
            "property_id": data["property_id"],  # Store property ID
            "inventoryType": formatted_inventory_type,
            "quantity": data["quantity"],
            "totalPrice": data["totalPrice"],
            "fullName": data["fullName"],
            "email": data["email"],
            "phone": data["phone"],
            "company": data.get("company", ""),
            "gstin": data.get("gstin", None),  # Store GSTIN if provided
            "date": booking_date,
            "time": booking_time,  # Only applicable for Meeting Rooms
            "status": data.get("status", "Paid") ,  # Default status
            "created_at": datetime.utcnow()
        }

        # Store Razorpay payment details if present
        booking.update({
            "razorpay_payment_id": data.get("razorpay_payment_id"),
            "razorpay_order_id": data.get("razorpay_order_id"),
            "razorpay_signature": data.get("razorpay_signature"),
        })

        # Insert into MongoDB
        booking_collection.insert_one(booking)

        return jsonify({"success": True,"contact": data["phone"], "message": "Booking received successfully!"}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@core_bp.route('/verify_otp', methods=['POST'])
def verify_otp():
    mobile = session.get('contact')
    otp = request.json.get('otp')

    if not mobile or not otp:
        return jsonify({'success': False, 'message': 'Invalid request'})

    otp_service = OtpLessAuth()
    response = otp_service.verify_otp(mobile, otp)

    if response['success']:
        session['otp_verified'] = True
        session.modified = True  # Ensure session persists
        print(f"Session after OTP verification: {session}")
        return jsonify({'success': True, 'message': 'OTP verified successfully!'})
    else:
        return jsonify({'success': False, 'message': 'OTP verification failed'})


# def verify_otp():
#     request_id = request.json.get('requestId')
#     otp = request.json.get('otp')

#     if not request_id or not otp:
#         return jsonify({'success': False, 'message': 'Both requestId and OTP are required'})

#     otp_service = OtpLessAuth()
#     response = otp_service.verify_otp(request_id, otp)

#     if response['success']:
#         session['otp_verified'] = True  # Mark OTP as verified in session
#         return jsonify({'success': True, 'message': 'OTP verified successfully!'})
#     else:
#         return jsonify({'success': False, 'message': response.get('message', 'Failed to verify OTP')})
                       
@core_bp.route('/sitemap.xml')
def sitemap():
    return send_from_directory(directory=current_app.root_path, path='sitemap.xml', mimetype='application/xml')

# Route to render index.html
@core_bp.route('/')
def index():
    # Render the template with the dynamic city data
    return render_template('index.html')


@core_bp.route('/user')
def user():
    db = current_app.config['db']  # MongoDB connection
    contact = request.args.get('contact')  # Get contact from URL parameter

    if not contact:
        return "Contact number is required!", 400

    # Step 1: Fetch user details to get user_id
    user = db.users.find_one({'contact': contact}, {'_id': 1, 'name': 1, 'contact': 1, 'email': 1, 'company': 1, 'location': 1})
    
    if not user:
        return "User not found!", 404

    user_id = str(user['_id'])

    # Step 2: Fetch visits using user_id
    visits = list(db.visits.find({'user_id': ObjectId(user_id)}))

    # Step 3: Process visits and fetch property details
    for visit in visits:
        property_id = visit.get('property_id')

        # Fetch property details
        property_details = db.fillurdetails.find_one(
            {'_id': ObjectId(property_id)},
            {'coworking_name': 1, 'micromarket': 1, 'city': 1, 'address': 1, 'inventory': 1}
        )

        if property_details:
            # Extract price_per_seat from the inventory matching the inventory type
            inventory_type = visit.get('inventory_type')
            price_per_seat = None

            for inventory in property_details.get('inventory', []):
                if inventory.get('type') == inventory_type:
                    price_per_seat = inventory.get('price_per_seat')
                    break

            # Attach relevant property details to visit record
            visit['property'] = {
                'coworking_name': property_details.get('coworking_name'),
                'micromarket': property_details.get('micromarket'),
                'city': property_details.get('city'),
                'address': property_details.get('address'),
                'price_per_seat': price_per_seat
            }

    # Step 4: Fetch bookings using user_id
    bookings = list(db.booking.find({'user_id': user_id}))

    # Step 5: Process bookings and fetch property details
    for booking in bookings:
        property_id = booking.get('property_id')

        # Fetch property details
        property_details = db.fillurdetails.find_one(
            {'_id': ObjectId(property_id)},
            {'coworking_name': 1, 'micromarket': 1, 'city': 1, 'address': 1, 'inventory': 1}
        )

        if property_details:
            # Extract price_per_seat from inventory based on inventory type
            inventory_type = booking.get('inventoryType')
            price_per_seat = None

            for inventory in property_details.get('inventory', []):
                if inventory.get('type') == inventory_type:
                    price_per_seat = inventory.get('price_per_seat')
                    break

            # Attach property details to booking record
            booking['property'] = {
                'coworking_name': property_details.get('coworking_name'),
                'micromarket': property_details.get('micromarket'),
                'city': property_details.get('city'),
                'address': property_details.get('address'),
                'price_per_seat': price_per_seat
            }

        # Convert MongoDB date format to readable format
        if 'date' in booking and isinstance(booking['date'], dict) and '$date' in booking['date']:
            booking['date'] = datetime.strptime(booking['date']['$date'], "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%d %B %Y")

    # Pass data to the template
    return render_template('user.html', user=user, visits=visits, bookings=bookings)



# Function to update users Excel sheet
def update_users_excel(new_user):
    file_path = os.path.join(current_app.root_path, 'Users.xlsx')

    # Check if file exists
    if os.path.exists(file_path):
        df = pd.read_excel(file_path)
    else:
        df = pd.DataFrame(columns=['Name', 'Contact', 'Company', 'Email'])  # Create new file if not exists

    # Append new user data
    new_row = pd.DataFrame([new_user])
    df = pd.concat([df, new_row], ignore_index=True)

    # Save updated data back to Excel
    df.to_excel(file_path, index=False)
    print("User data updated in Users Excel Sheet")

@core_bp.route('/check_user', methods=['POST'])
def check_user():
    db = current_app.config['db']
    contact = request.json.get('contact')

    if not contact:
        return jsonify({'exists': False})

    # Check if user exists in MongoDB `users` collection
    user = db.users.find_one({'contact': contact})

    if user:
        return jsonify({'exists': True, 'name': user.get('name'), 'email': user.get('email'), 'company': user.get('company')})
    else:
        return jsonify({'exists': False})


# Route to handle form submission (Your Info form)
@core_bp.route('/submit_info', methods=['POST'])
def submit_info():
    
    db = current_app.config['db']  # Get the db instance from the app config

    # Get form data
    name = request.form.get('name')
    contact = request.form.get('contact')
    company = request.form.get('company')
    email = request.form.get('email')
    latitude = request.form.get('latitude')
    longitude = request.form.get('longitude')
    location = request.form.get('location')

    # Check if the user exists in the database
    existing_user = db.users.find_one({'contact': contact})

    # ✅ Prepare new user data using the latest form input (always use fresh data)
    user_data = {
        'name': name,
        'contact': contact,
        'company': company,
        'email': email,
        'latitude': latitude,
        'longitude': longitude,
        'location': location
    }

    if existing_user:
        # ✅ Update Google Sheets with latest form submission
        google_sheet_status = handle_new_user_entry(user_data)
        
        return jsonify({'status': 'exists', 'message': 'User exists'})
    else:
        result = db.users.insert_one(user_data)
        session['user_id'] = str(result.inserted_id)  # Save new user_id in the session
        session['name'] = name
        session['email'] = email
        session['contact'] = contact

        # Add user to Users Excel Sheet
        update_users_excel(user_data)
        # ✅ First, Try to Sync Google Sheet Immediately (synchronously)
        google_sheet_status = handle_new_user_entry(user_data)

        # ✅ Then, Run It in the Background (thread)
        app = current_app._get_current_object()
        gsheet_thread = threading.Thread(target=handle_new_user_entry, args=(user_data,))
        gsheet_thread.start()

        return jsonify({'status': 'success', 'user_id': session['user_id'], 'redirect': None})

@core_bp.route('/thankyou')
def thankyou():
    return render_template('thankyou.html')

# Route to handle user preferences submission (Your Preference form)
@core_bp.route('/submit_preferences', methods=['POST'])
def submit_preferences():
    db = current_app.config['db']

    # Get form data
    seats = request.form.get('seats')
    contact = request.form.get('contact')
    location = request.form.get('location')
    area = request.form.get('area')
    budget = request.form.get('budget')
    inventory_type = request.form.get('inventory-type')  # New field
    hear_about = request.form.get('hear-about')  # New field
    
    user = db.users.find_one({'contact': contact})
    if not user:
        return jsonify({'status': 'error', 'message': 'User not found'})
    
    user_id = user['_id']

    # Parse budget range
    min_budget, max_budget = 0, float('inf')  # Default range
    try:
        if budget == "5000-10000":
            min_budget, max_budget = 5000, 10000
        elif budget == "10000-15000":
            min_budget, max_budget = 10000, 15000
        elif budget == "15000+":
            min_budget, max_budget = 15000, float('inf')
    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)})
    
    user_id = user['_id']

    # Check if the user already has an existing property record
    existing_property = db.properties.find_one({'user_id': user_id})

    # Fetch user information
    user = db.users.find_one({'_id': user_id})
    if not user:
        flash('User not found. Please fill out the "Your Info" form again.', 'error')
        return jsonify({'status': 'error', 'message': 'User not found'})

    name = user.get('name')
    email = user.get('email')
    contact = user.get('contact')
    print(f"User details - Name: {name}, Email: {email}, Contact: {contact}")

    # Initial query for location and area
    query = {
        'city': {'$regex': f'^{location.strip()}$', '$options': 'i'},
        'micromarket': {'$regex': f'^{area.strip()}$', '$options': 'i'},
        'inventory.type': inventory_type  # Only properties with the selected inventory type
    }

    # Fetch properties
    all_properties = list(db.fillurdetails.find(query))

    # Filter properties based on price only (using lowest price from inventory)
    filtered_properties = []
    operator_numbers=[]
    center_manager_numbers = []  # List for center manager numbers
    for prop in all_properties:
        inventory = prop.get('inventory', [])

        # Filter inventory to only include the selected type
        filtered_inventory = [item for item in inventory if item.get('type') == inventory_type]

        if filtered_inventory:  # If property contains at least one matching inventory type
            lowest_price = get_lowest_price(filtered_inventory)
            if min_budget and max_budget:
                # Add the lowest price to the property object for reference
                prop['lowest_price'] = lowest_price
                prop['inventory'] = filtered_inventory  # Update the property with only filtered inventory
                filtered_properties.append(prop)

                operator_phone= prop.get('owner',{}).get('phone')
                if operator_phone:
                    operator_numbers.append(operator_phone)
                
                # Add center manager phone number
                center_manager_phone = prop.get('center_manager', {}).get('contact')
                if center_manager_phone:
                    center_manager_numbers.append(center_manager_phone)
    
    
    # Sort properties by lowest price
    filtered_properties.sort(key=lambda x: x.get('lowest_price', float('inf')))

    # Prepare property names for logging
    property_names = ", ".join([p.get('coworking_name', 'Unknown') for p in filtered_properties]) if filtered_properties else 'N/A'

    user_id = user['_id']

    # Check if the user already has an existing property record
    existing_property = db.properties.find_one({'user_id': user_id})

    if existing_property:
        # Update existing record instead of creating a new one
        update_data = {
            'seats': seats,
            'city': location,
            'micromarket': area,
            'budget': budget,
            'inventory_type': inventory_type,
            'hear_about': hear_about,
            'date': datetime.now()  # Update timestamp
        }
        db.properties.update_one({'user_id': user_id}, {'$set': update_data})
        return jsonify({'status': 'success', 'message': 'Preferences updated successfully.'})
    else:

        # Store preferences in the `properties` collection
        new_property = {
            'user_id': user_id,
            'contact': contact,
            'seats': seats,
            'city': location,
            'micromarket': area,
            'budget': budget,
            'inventory_type': inventory_type,  # Save new field
            'hear_about': hear_about,  # Save new field
            'property_names': property_names,
            'operator_numbers': operator_numbers,
            'center_manager_numbers': center_manager_numbers, 
            'date': datetime.now()
        }

        # Insert property data into the collection
        db.properties.insert_one(new_property)

    # Background threads for email and Google Sheets updates
    app = current_app._get_current_object()
    email_thread = threading.Thread(
        target=send_email_and_whatsapp_background,
        args=(app, email, name, contact, filtered_properties)
    )
    email_thread.start()

    gsheet_thread = threading.Thread(
        target=update_gsheet_background,
        args=(app, db, new_property)
    )
    gsheet_thread.start()

    return jsonify({'status': 'success'})
    # return jsonify({'status': 'success', 'message': 'Preferences saved. Redirecting to the report.','redirect_url': url_for('core_bp.outerpage', contact=contact)})

# Helper function to format input for case-insensitive, trimmed match
def format_query_param(param):
    return {'$regex': f'^{param.strip()}$', '$options': 'i'} if param else None

# Route to fetch unique locations (cities)
@core_bp.route('/get_locations', methods=['GET'])
def get_locations():
    db = current_app.config['db']
    cities = db.fillurdetails.distinct('city')
    # Use a list comprehension to ensure unique, trimmed, and case-insensitive results
    camel_case_cities = list(set(to_camel_case(city.strip().lower()) for city in cities))
    return jsonify({'locations': sorted(camel_case_cities)})
    

# Route to fetch unique micromarkets based on selected city
@core_bp.route('/get_micromarkets', methods=['GET'])
def get_micromarkets():
    db = current_app.config['db']
    city = request.args.get('city')
    query = {'city': format_query_param(city)}
    micromarkets = db.fillurdetails.distinct('micromarket', query)
    # Convert all micromarket names to camel case
    camel_case_micromarkets = list(set(to_camel_case(micromarket.strip().lower()) for micromarket in micromarkets))
    return jsonify({'micromarkets': sorted(camel_case_micromarkets)})

# Route to fetch unique prices based on selected city and micromarket

# @core_bp.route('/get_prices', methods=['GET'])
# def get_prices():
#     try:
#         db = current_app.config['db']
#         city = request.args.get('city')
#         micromarket = request.args.get('micromarket')
        
#         query = {
#             'city': {'$regex': f'^{city.strip()}$', '$options': 'i'},
#             'micromarket': {'$regex': f'^{micromarket.strip()}$', '$options': 'i'}
#         }
        
#         # Find all matching documents
#         documents = db.fillurdetails.find(query)
        
#         # Get lowest prices for each property
#         prices = set()
#         for doc in documents:
#             lowest_price = get_lowest_price(doc.get('inventory', []))
#             if lowest_price > 0:
#                 prices.add(lowest_price)
        
#         prices_list = sorted(list(prices))
#         return jsonify({'prices': prices_list})
        
#     except Exception as e:
#         current_app.logger.error(f"Error in get_prices: {str(e)}")
#         return jsonify({'prices': [], 'error': 'An error occurred while fetching prices'}), 500
    
@core_bp.route('/terms-and-conditions')
def terms_and_conditions():
    return render_template('T&C.html')

@core_bp.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy-polciy.html')

@core_bp.route('/cancellation-and-refund-policy')
def refund():
    return render_template('refund.html')

@core_bp.route('/faqs')
def freq_asked_ques():
    return render_template('FAQs.html')

@core_bp.route('/managed-office-space/ahmedabad')
def ahmedabad():
    return render_template('ahmedabad.html')

@core_bp.route('/managed-office-space/bangalore')
def bangalore():
    return render_template('bangalore.html')

@core_bp.route('/managed-office-space/hyderabad')
def hyderabad():
    return render_template('hyderabad.html')

@core_bp.route('/managed-office-space/indore')
def indore():
    return render_template('indore.html')

@core_bp.route('/managed-office-space/lucknow')
def lucknow():
    return render_template('lucknow.html')

@core_bp.route('/managed-office-space/mumbai')
def mumbai():
    return render_template('mumbai.html')

@core_bp.route('/managed-offices/<city>')
def redirect_old_managed_office(city):
    return redirect(url_for(f'core_bp.{city}'))

@core_bp.route('/user1')
def user1():
    db = current_app.config['db']
    contact = request.args.get('contact')

    if not contact:
        return "Contact number is required!", 400

    # Fetch user details
    user = db.users.find_one({'contact': contact}, {'_id': 1, 'name': 1, 'contact': 1, 'email': 1, 'company': 1, 'location': 1})
    
    if not user:
        return "User not found!", 404

    user_id = str(user['_id'])

    # Fetch visits
    visits = list(db.visits.find({'user_id': ObjectId(user_id)}))

    # Fetch bookings
    bookings = list(db.booking.find({'user_id': user_id}))

    # Process property details for visits
    for visit in visits:
        property_id = visit.get('property_id')
        property_details = db.fillurdetails.find_one(
            {'_id': ObjectId(property_id)},
            {'coworking_name': 1, 'micromarket': 1, 'city': 1, 'address': 1, 'inventory': 1}
        )
        if property_details:
            inventory_type = visit.get('inventory_type')
            price_per_seat = None
            for inventory in property_details.get('inventory', []):
                if inventory.get('type') == inventory_type:
                    price_per_seat = inventory.get('price_per_seat')
                    break
            visit['property'] = {
                'coworking_name': property_details.get('coworking_name'),
                'micromarket': property_details.get('micromarket'),
                'city': property_details.get('city'),
                'address': property_details.get('address'),
                'price_per_seat': price_per_seat
            }

    # Process property details for bookings
    for booking in bookings:
        property_id = booking.get('property_id')
        property_details = db.fillurdetails.find_one(
            {'_id': ObjectId(property_id)},
            {'coworking_name': 1, 'micromarket': 1, 'city': 1, 'address': 1, 'inventory': 1}
        )
        if property_details:
            inventory_type = booking.get('inventoryType')
            price_per_seat = None
            for inventory in property_details.get('inventory', []):
                if inventory.get('type') == inventory_type:
                    price_per_seat = inventory.get('price_per_seat')
                    break
            booking['property'] = {
                'coworking_name': property_details.get('coworking_name'),
                'micromarket': property_details.get('micromarket'),
                'city': property_details.get('city'),
                'address': property_details.get('address'),
                'price_per_seat': price_per_seat
            }

    return render_template('user1.html', user=user, visits=visits, bookings=bookings)


def to_camel_case(input_str):
    return ' '.join(word.capitalize() for word in input_str.split())

@core_bp.route('/list-your-space', methods=['GET', 'POST'])
def list_your_space():
    db = current_app.config['db']  # Access the database here

    if request.method == 'POST':
        try:
            # Extract owner information
            name = request.form.get('name')
            owner_phone = request.form.get('owner_phone')
            owner_email = request.form.get('owner_email')
            coworking_name = request.form.get('coworking_name')

            # Extract General Information
            hear_from = request.form.get('hear_from')
            workspace_tool = request.form.get('workspace_tool')
            notification_preference = request.form.getlist('notification_preference')

            print(f"Owner Info - Name: {name}, Phone: {owner_phone}, Email: {owner_email}, Coworking Name: {coworking_name}")

            # Get list of space indices
            space_indices = request.form.getlist('space_indices[]')

            # Get lists of space data
            cities = request.form.getlist('city[]')
            micromarkets = request.form.getlist('micromarket[]')
            addresses = request.form.getlist('address[]') 

            total_seats_list = request.form.getlist('total_seats[]')
            current_vacancies = request.form.getlist('current_vacancy[]')
            center_manager_names = request.form.getlist('center_manager_name[]')
            center_manager_contacts = request.form.getlist('center_manager_contact[]')
            workspace_types = request.form.getlist('workspace_type[]')

            # Distance Fields - Extracted Correctly
            distances_metro = request.form.getlist('distance_metro[]')
            distances_airport = request.form.getlist('distance_airport[]')
            distances_bus = request.form.getlist('distance_bus[]')
            distances_railway = request.form.getlist('distance_railway[]')

            # Handle custom inputs for "Other"
            custom_cities = request.form.getlist('location_custom_1[]')  # Custom city inputs
            custom_micromarkets = request.form.getlist('micromarket_custom_1[]')  # Custom micromarket inputs

             # Validation: Ensure "Other" selections have corresponding custom inputs
            if "Other" in cities and len(custom_cities) < cities.count("Other"):
                flash("Please provide custom city names for all 'Other' selections.", 'error')
                return redirect(url_for('core_bp.list_your_space'))

            if "Other" in micromarkets and len(custom_micromarkets) < micromarkets.count("Other"):
                flash("Please provide custom micromarkets for all 'Other' selections.", 'error')
                return redirect(url_for('core_bp.list_your_space'))

            print(f"Received cities: {cities}")
            print(f"Received micromarkets: {micromarkets}")
            print(f"Custom cities: {custom_cities}")
            print(f"Custom micromarkets: {custom_micromarkets}")

            # Process each space
            for idx, city, micromarket,address, total_seats, current_vacancy,center_manager_name, center_manager_contact, workspace_type, metro_dist, airport_dist, bus_dist, railway_dist in zip(space_indices, cities, micromarkets,addresses, total_seats_list, current_vacancies,center_manager_names, center_manager_contacts, workspace_types,
                    distances_metro, distances_airport, distances_bus, distances_railway):
                idx_str = str(idx)  # Convert idx to string in case it's not

                # Validate the address
                if not address:
                    flash(f"Address is missing for space {idx}.", 'error')
                    continue

                # Handle "Other" case for city and micromarket
                if city == "Other" and custom_cities:
                    city = to_camel_case(custom_cities.pop(0).strip())
                if micromarket == "Other" and custom_micromarkets:
                    micromarket = to_camel_case(custom_micromarkets.pop(0).strip())

                # Convert Distances to Float Safely
                distance_data = {
                    'metro': float(metro_dist) if metro_dist else 0.0,
                    'airport': float(airport_dist) if airport_dist else 0.0,
                    'bus': float(bus_dist) if bus_dist else 0.0,
                    'railway': float(railway_dist) if railway_dist else 0.0
                }

                 # Upload Property Images
                property_images = request.files.getlist(f'property_images_{idx}[]')
                property_image_links = process_and_upload_images(property_images, {'name': name}, coworking_name,category="property",space_id=idx)

                # Get Workspace Type Details
                inventory = []
                # Get Workspace Type Details
                if workspace_type == "Coworking Spaces":
                    inventory_types = request.form.getlist(f'inventory_type_{idx}[]')
                    inventory_counts = request.form.getlist(f'inventory_count_{idx}[]')
                    price_per_seats = request.form.getlist(f'price_per_seat_{idx}[]')

                    for inv_idx, inv_type in enumerate(inventory_types):
                        room_number = None 
                        opening_time = request.form.get(f'opening_time_{idx}_{inv_idx + 1}')
                        closing_time = request.form.get(f'closing_time_{idx}_{inv_idx + 1}')
                        # Get Inventory Images for the current inventory item
                        inventory_image_field = f'inventory_images_{idx}_{inv_idx + 1}[]'
                        inventory_images = request.files.getlist(inventory_image_field)

                        # Upload Inventory Images
                        inventory_image_links = process_and_upload_images(
                            inventory_images, 
                            {'name': name}, 
                            coworking_name, 
                            category="inventory",
                            space_id=idx,
                            inventory_id=inv_idx + 1
                        )

                        #e Meeting Rooms and Private Cabins separately
                        room_details = []
                        if inv_type in ["Meeting rooms", "Private cabin"]:
                            room_number = request.form.get(f'number_of_rooms_{idx}_{inv_idx + 1}')
                            try:
                                room_number = int(room_number) if room_number else 0
                            except (ValueError, TypeError):
                                room_number = 0
                            room_count = request.form.get(f'number_of_rooms_{idx}_{inv_idx + 1}')
                            print(f"Room Count Raw: {room_count}")
                            if room_count:
                                room_count = int(room_count[0])
                            else:
                                room_count = 0
                            print(f"Room Count Received: {room_count}")  # Debug: Check received value

                            # Convert room_count to int safely
                            try:
                                room_count = int(room_count or 0)
                            except (ValueError, TypeError):
                                room_count = 0                            

                            for room_idx in range(1, room_number + 1):
                                try:
                                    seating_capacity = int(request.form.get(f'seating_capacity_{idx}_{inv_idx + 1}_{room_idx}') or 0)
                                except (ValueError, TypeError):
                                    seating_capacity = 0
                                try:
                                    price = float(request.form.get(f'price_{idx}_{inv_idx + 1}_{room_idx}') or 0.0)
                                except (ValueError, TypeError):
                                    price = 0.0

                                # ✅ Correcting the room_images_field
                                if inv_type == "Meeting rooms":
                                    room_images_field = f'meeting_room_images_{idx}_{inv_idx + 1}_{room_idx}[]'
                                elif inv_type == "Private cabin":
                                    room_images_field = f'private_cabin_images_{idx}_{inv_idx + 1}_{room_idx}[]'

                                room_images = request.files.getlist(room_images_field)

                                # Debugging to verify if files are being fetched correctly
                                print(f"Uploading Room Images for {inv_type} - Space {idx}, Inventory {inv_idx + 1}, Room {room_idx}")
                                print(f"Files Received: {[img.filename for img in room_images if img.filename]}")
                                # Upload images only if there are valid files
                                if room_images:
                                    room_image_links = process_and_upload_images(
                                        room_images, {'name': name}, coworking_name, 
                                        category=inv_type.lower().replace(" ", "_"),
                                        space_id=idx, inventory_id=inv_idx + 1, room_id=room_idx
                                    )
                                else:
                                    room_image_links = []
                                
                                print(f"Room Number: {room_idx}")  # Debug: Room number loop
                                print(f"Seating Capacity Received: {seating_capacity}")  # Debug
                                print(f"Price Received: {price_per_seats}")  # Debug
                                if seating_capacity:
                                    room_details.append({
                                        'room_number': room_idx,
                                        'seating_capacity': int(seating_capacity),
                                        'price': float(price_per_seats[inv_idx] or 0.0),
                                        'images': room_image_links
                                    })

                            print(f"Final Room Details: {room_details}") 

                            inventory.append({
                                'type': inv_type,
                                'room_count': room_number,
                                'price_per_seat': float(price_per_seats[inv_idx] or 0.0),
                                'opening_time': opening_time,
                                'closing_time': closing_time,
                                'room_details': room_details,
                                'images': inventory_image_links
                            })
                        else:
                            inventory.append({
                                'type': inv_type,
                                'count': int(inventory_counts[inv_idx] or 0),
                                'price_per_seat': float(price_per_seats[inv_idx] or 0.0),
                                'images': inventory_image_links
                            })

                    amenities = request.form.getlist(f'amenities_{idx}[]')
                    open_from = request.form.get(f'open_from_{idx}')
                    open_to = request.form.get(f'open_to_{idx}')
                    opening_time = request.form.get(f'opening_time_{idx}')
                    closing_time = request.form.get(f'closing_time_{idx}')
                else:
                    rent_or_own = request.form.get(f'rent_or_own_{idx}')
                    print("Debug Info: total_building_area =", request.form.get(f'total_building_area_{idx}'))
                    print("Debug Info: floorplate_area =", request.form.get(f'floorplate_area_{idx}'))
                    print("Debug Info: min_inventory_unit =", request.form.get(f'min_inventory_unit_{idx}'))
                    print("Debug Info: total_rental =", request.form.get(f'total_rental_{idx}'))
                    print("Debug Info: total_floors =", request.form.get(f'total_floors_{idx}'))
                    print("Debug Info: floors_occupied =", request.form.get(f'floors_occupied_{idx}'))
                    print("Debug Info: lockin_period =", request.form.get(f'lockin_period_{idx}'))

                    # Use a try-except block to catch any conversion errors
                    try:
                        total_building_area = int(request.form.get(f'total_building_area_{idx}') or '0')
                    except (ValueError, TypeError):
                        total_building_area = 0  # Default to 0 if conversion fails

                    try:
                        floorplate_area = int(request.form.get(f'floorplate_area_{idx}') or 0)
                    except (ValueError, TypeError):
                        floorplate_area = 0  # Default to 0 if conversion fails

                    try:
                        min_inventory_unit = int(request.form.get(f'min_inventory_unit_{idx}') or 0)
                    except (ValueError, TypeError):
                        min_inventory_unit = 0  # Default to 0 if conversion fails

                    try:
                        total_rental = int(request.form.get(f'total_rental_{idx}') or 0)
                    except (ValueError, TypeError):
                        total_rental = 0  # Default to 0 if conversion fails

                    space_type = request.form.get(f'space_type_{idx}')

                    try:
                        total_floors = int(request.form.get(f'total_floors_{idx}') or '0')
                    except (ValueError, TypeError):
                        total_floors = 0

                    try:
                        floors_occupied = int(request.form.get(f'floors_occupied_{idx}') or '0')
                    except (ValueError, TypeError):
                        floors_occupied = 0

                    try:
                        lockin_period = int(request.form.get(f'lockin_period_{idx}') or '0')
                    except (ValueError, TypeError):
                        lockin_period = 0

                    try:
                        security_deposit = int(request.form.get(f'security_deposit_{idx}') or '0')
                    except (ValueError, TypeError):
                        security_deposit = 0
                    
                    lease_term = request.form.get(f'lease_term_{idx}')
                    seating_capacity = request.form.get(f'seating_capacity_{idx}') or 'N/A'
                    furnishing_level = request.form.get(f'furnishing_level_{idx}') or 'N/A'
                    managed_office_amenities = request.form.getlist(f'managed_amenities_{idx}[]')

                # Get Space Description
                space_description = request.form.get(f'space_description_{idx}')

                # Create Document for MongoDB
                property_details = {
                    'owner': {
                        'name': name,
                        'phone': owner_phone,
                        'email': owner_email
                    },
                    'coworking_name': coworking_name,
                    'city': city,
                    'micromarket': micromarket,
                    'address': address, 
                    'distance': distance_data,
                    'total_seats': int(total_seats or 0),
                    'current_vacancy': int(current_vacancy or 0),
                    'center_manager': {
                        'name': center_manager_name,
                        'contact': center_manager_contact
                    },
                    'property_images': property_image_links,
                    'workspace_type': workspace_type,
                    'hear_from': hear_from,
                    'workspace_tool': workspace_tool,
                    'notification_preference': notification_preference,
                    'space_description': space_description,
                    'date': datetime.now()
                }

                # Add Workspace Type Specific Details
                if workspace_type == "Coworking Spaces":
                    property_details.update({
                        'inventory': inventory,
                        'amenities': amenities,
                        'office_timings': {
                            'open_from': open_from,
                            'open_to': open_to,
                            'opening_time': opening_time,
                            'closing_time': closing_time
                        }
                    })
                else:
                    # Add Managed Offices Details to Document
                    property_details.update({
                        'rent_or_own': rent_or_own,
                        'total_building_area': total_building_area,
                        'total_floors': total_floors,
                        'floorplate_area': floorplate_area,
                        'min_inventory_unit': min_inventory_unit,
                        'total_rental': total_rental,
                        'security_deposit': security_deposit,
                        'lease_term': lease_term,
                        'space_type': space_type,
                        'floors_occupied': floors_occupied,
                        'seating_capacity': seating_capacity,
                        'furnishing_level': furnishing_level,
                        'lockin_period': lockin_period,
                        'managed_office_amenities': managed_office_amenities
                    })

                # Insert into MongoDB
                db.fillurdetails.insert_one(property_details)

            flash("Property details submitted successfully.", 'success')
            return redirect(url_for('core_bp.thank_you'))

        except Exception as e:
            flash(f"Failed to submit property details: {str(e)}", 'error')
            print(f"Error: {e}")

    return render_template('FillUrDetails.html')

    #             # Validate city and micromarket
    #             if not city or not micromarket:
    #                 flash(f"City or Micromarket is missing for space {idx_str}.", 'error')
    #                 continue

    #             print(f"Processing space {coworking_name} in {city} ({micromarket}) with {total_seats} seats")

    #             # Get inventories for this space
    #             inventory_types = request.form.getlist(f'inventory_type_{idx}[]')
    #             inventory_counts = request.form.getlist(f'inventory_count_{idx}[]')
    #             price_per_seats = request.form.getlist(f'price_per_seat_{idx}[]')

    #             inventory = []
    #             for i in range(len(inventory_types)):
    #                 inventory.append({
    #                     'type': inventory_types[i],
    #                     'count': int(inventory_counts[i]),
    #                     'price_per_seat': float(price_per_seats[i])
    #                 })

    #             print(f"Inventory for space {idx}: {inventory}")

    #             # Handle file uploads (Images for Layouts)
    #             layout_images = request.files.getlist(f'layout_images_{idx}[]')

    #             # Call the process and upload images function (handles compression & DigitalOcean upload)
    #             layout_image_links = process_and_upload_images(layout_images, {'name': name}, coworking_name)

    #             print(f"Uploaded image links for space {idx}: {layout_image_links}")

    #             # Create a document for each coworking space with owner info
    #             property_details = {
    #                 'owner': {
    #                     'name': name,
    #                     'phone': owner_phone,
    #                     'email': owner_email
    #                 },
    #                 'coworking_name': coworking_name,
    #                 'city': city,
    #                 'micromarket': micromarket,
    #                 'address': address, 
    #                 'total_seats': int(total_seats),
    #                 'current_vacancy': int(current_vacancy),
    #                 'center_manager': {
    #                     'name': center_manager_name,
    #                     'contact': center_manager_contact
    #                 },
    #                 'inventory': inventory,
    #                 'layout_images': layout_image_links,
    #                 'interactive_layout': False,  # Set interactive_layout as False initially
    #                 'hear_from': hear_from,
    #                 'date': datetime.datetime.now()
    #             }

    #             # Insert into MongoDB
    #             try:
    #                 print(f"Inserting property details into MongoDB: {property_details}")
    #                 db.fillurdetails.insert_one(property_details)
    #             except Exception as db_error:
    #                 flash(f"Failed to insert property: {db_error}", 'error')
    #                 print(f"Error inserting property into MongoDB: {db_error}")

    #         flash("Property details submitted successfully.", 'success')
    #         return redirect(url_for('core_bp.thank_you'))

    #     except Exception as e:
    #         flash(f"Failed to submit property details: {str(e)}", 'error')
    #         print(f"Error: {e}")

    # return render_template('FillUrDetails.html')

@core_bp.route('/get_inventory_types', methods=['GET'])
def get_inventory_types():
    db = current_app.config['db']
    city = request.args.get('city')
    micromarket = request.args.get('micromarket')

    if not city or not micromarket:
        return jsonify({'inventory_types': []})

    query = {
        'city': {'$regex': f'^{city.strip()}$', '$options': 'i'},
        'micromarket': {'$regex': f'^{micromarket.strip()}$', '$options': 'i'}
    }

    # Fetch properties matching city and micromarket
    properties = list(db.fillurdetails.find(query))

    if not properties:
        print("No properties found for given city and micromarket.")
        return jsonify({'inventory_types': []})

    # Extract unique inventory types
    inventory_types = set()
    for prop in properties:
        for inventory in prop.get('inventory', []):
            inventory_types.add(inventory.get('type'))

    return jsonify({'inventory_types': sorted(inventory_types)})


# @core_bp.route('/robots.txt')
# def robots():
#     return send_from_directory(directory=current_app.root_path, path='robots.txt', mimetype='text/plain')

# @core_bp.route('/sitemap.xml')
# def sitemap():
#     return send_from_directory(directory=current_app.root_path, path='sitemap.xml', mimetype='application/xml')

@core_bp.route('/robots.txt')
def robots():
    return send_from_directory(directory=current_app.root_path, path='robots.txt', mimetype='text/plain')

@core_bp.route('/thank-you')
def thank_you():
    return render_template('thank_you.html')

@core_bp.route('/press-room')
def press_room():
    return render_template('press-room.html')

@core_bp.route('/property_images/<property_id>', methods=['GET'])
def property_images(property_id):
    db = current_app.config['db']  # Access the database instance
    
    try:
        # Fetch the property document using the property_id
        property_data = db.fillurdetails.find_one({'_id': ObjectId(property_id)})

        if not property_data:
            flash('Property not found', 'error')
            return redirect(url_for('core_bp.index'))

        # Extract the layout images
        layout_images = property_data.get('layout_images', [])
        
        # Render the template and pass the image URLs and other details
        return render_template('property_images.html', images=layout_images, property_name=property_data['coworking_name'])

    except Exception as e:
        flash(f'Error fetching property images: {str(e)}', 'error')
        return redirect(url_for('core_bp.index'))

@core_bp.route('/blog')
def blog():
    try:
        api_url = 'https://findurspace-blog-app-pemmb.ondigitalocean.app/api/blog-posts?populate=*'
        api_key = os.getenv('STRAPI_API_KEY')
        if not api_key:
            return "API key not found in environment variables", 500
        
        headers = {
            'Authorization': f'Bearer {api_key}',
        }
        # Get page and limit from query parameters
        page = int(request.args.get('page', 1))  # Default to page 1
        limit = 6  # Number of blogs per page
        start = (page - 1) * limit

        # Fetch paginated blogs from API
        response = requests.get(f"{api_url}&pagination[start]={start}&pagination[limit]={limit}", headers=headers)
        data = response.json()

        blogs = data.get('data', [])
        total_count = data.get('meta', {}).get('pagination', {}).get('total', 0)
        total_pages = -(-total_count // limit)  # Calculate total pages

         # Calculate read time for each blog
        reading_speed = 200  # Words per minute
        for blog in blogs:
            content_blocks = blog.get('Content', [])
            word_count = 0
            for block in content_blocks:
                if block.get('type') in ['paragraph', 'heading', 'quote']:
                    for child in block.get('children', []):
                        word_count += len(child.get('text', '').split())
            blog['read_time'] = max(1, round(word_count / reading_speed))  # Add read time to blog


        return render_template(
            'blog.html', blogs=blogs, page=page, total_pages=total_pages
        )
    except Exception as e:
        return str(e)
        



@core_bp.route('/blog/<slug>')
def blog_detail(slug):
    try:
        # Construct API URL
        api_url = f'https://findurspace-blog-app-pemmb.ondigitalocean.app/api/blog-posts?filters[slug][$eq]={slug}&populate=*'
        
        # Fetch API key from environment
        api_key = os.getenv('STRAPI_API_KEY')
        if not api_key:
            return "API key not found in environment variables", 500
        
        headers = {
            'Authorization': f'Bearer {api_key}',
        }

        # Fetch blog data
        response = requests.get(api_url, headers=headers)
        if response.status_code != 200:
            return f"Failed to fetch blog post: {response.status_code}", response.status_code
        
        blog_post_data = response.json().get('data')
        if not blog_post_data or len(blog_post_data) == 0:
            return "Blog post not found", 404

        # Extract the first blog post
        blog_post = blog_post_data[0]

        # Fetch other blogs
        other_blogs_url = 'https://findurspace-blog-app-pemmb.ondigitalocean.app/api/blog-posts?populate=*'
        response_other = requests.get(other_blogs_url, headers=headers)
        if response_other.status_code != 200:
            return f"Failed to fetch other blogs: {response_other.status_code}", response_other.status_code

        all_blogs = response_other.json().get('data', [])
        other_blogs = [blog for blog in all_blogs if blog['slug'] != slug]

        # Parse the content blocks for rendering
        content_blocks = blog_post.get('Content', [])
        parsed_content = []

        for block in content_blocks:
            if block['type'] == 'heading':
                parsed_content.append({
                    'type': 'heading',
                    'level': block.get('level', 2),
                    'text': block['children'][0].get('text', '') if block['children'] else ''
                })
            elif block['type'] == 'paragraph':
                paragraph_content = []
                for child in block.get('children', []):
                    if child['type'] == 'text':
                        paragraph_content.append({'type': 'text', 'text': child.get('text', '')})
                    elif child['type'] == 'link':
                        link_text = ''.join([link_child.get('text', '') for link_child in child.get('children', [])])
                        paragraph_content.append({'type': 'link', 'url': child.get('url', ''), 'text': link_text})
            elif block['type'] == 'image':
                parsed_content.append({
                    'type': 'image',
                    'url': block.get('image', {}).get('url', ''),
                    'alt': block.get('image', {}).get('alternativeText', ''),
                    'caption': block.get('image', {}).get('caption', '')
                })
            elif block['type'] == 'list':
                list_items = []
                for item in block.get('children', []):
                    list_items.append({
                        'type': 'list-item',
                        'text': ''.join([child.get('text', '') for child in item.get('children', [])])
                    })
                parsed_content.append({'type': 'list', 'format': block.get('format', 'unordered'), 'items': list_items})

        # Pass parsed content to the template
        read_time = max(1, round(sum(len(c.get('text', '').split()) for c in parsed_content if c.get('text')) / 200))
        return render_template('blog_detail.html', blog=blog_post, content=parsed_content, read_time=read_time,other_blogs=other_blogs)


    except requests.exceptions.RequestException as e:
        return f"An error occurred while connecting to the API: {e}", 500
    except KeyError as e:
        return f"Unexpected response structure: Missing key {e}", 500
    except Exception as e:
        return f"An unexpected error occurred: {e}", 500
    

@core_bp.route('/blog/like/<slug>', methods=['GET', 'POST'])
def manage_blog_likes(slug):
    db = current_app.config['db']  # Access MongoDB from Flask app config

    if request.method == 'GET':
        # Fetch current likes and check if the user has already liked
        like_entry = db.blog_likes.find_one({"slug": slug})
        user_liked = session.get(f"liked_{slug}", False)
        return jsonify({
            "success": True,
            "likes": like_entry["likes"] if like_entry else 0,
            "userLiked": user_liked
        })

    elif request.method == 'POST':
        # Check if the user has already liked this post
        if session.get(f"liked_{slug}", False):
            return jsonify({"success": False, "message": "You have already liked this post."}), 400

        try:
            # Increment the likes count in MongoDB
            updated_entry = db.blog_likes.find_one_and_update(
                {"slug": slug},
                {"$inc": {"likes": 1}},  # Increment the likes field by 1
                upsert=True,  # Create the document if it doesn't exist
                return_document=True  # Return the updated document
            )

            # Mark as liked in the session
            session[f"liked_{slug}"] = True

            return jsonify({"success": True, "likes": updated_entry["likes"]})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500
        

@core_bp.route('/submit_booking_form', methods=['POST'])
def submit_booking_form():
    db = current_app.config['db']  # Access MongoDB instance

    try:
        data = request.json
        # Extract form data
        coworking_name = data.get("coworking_name")
        contact = data.get("contact")
        inventory = data.get("inventory")

        # Validate required fields
        if not all([coworking_name, contact, inventory]):
            return jsonify({"success": False, "message": "Missing required fields"}), 400

        # Check if a record with the same contact exists
        existing_record = db.users.find_one({"contact": contact})

        if existing_record:
            # Update the existing record by appending inventory type
            updated_inventory = existing_record.get("inventory", [])
            if inventory not in updated_inventory:  # Avoid duplicate inventory types
                updated_inventory.append(inventory)

            db.users.update_one(
                {"contact": contact},
                {"$set": {"inventory": updated_inventory}}
            )

            return jsonify({"success": True, "message": "Inventory type added to existing booking!"}), 200
        else:
            # Store in MongoDB as a new record
            booking_data = {
                "coworking_name": coworking_name,
                "contact": contact,
                "inventory": [inventory],  # Store as a list to allow multiple inventory types
                "created_at": datetime.utcnow()
            }

            db.users.insert_one(booking_data)

            return jsonify({"success": True, "message": "Booking request submitted successfully!"}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@core_bp.route('/check_existing_contact', methods=['GET'])
def check_existing_contact():
    """Checks if a contact already exists in the users collection."""
    db = current_app.config['db']
    contact = request.args.get("contact")

    if not contact:
        return jsonify({"exists": False, "message": "Contact not provided"}), 400

    existing_record = db.users.find_one({"contact": contact})

    return jsonify({"exists": bool(existing_record)})

@core_bp.route('/update_inventory', methods=['POST'])
def update_inventory():
    """Updates inventory type for an existing user."""
    db = current_app.config['db']
    try:
        data = request.json
        contact = data.get("contact")
        inventory = data.get("inventory")

        if not all([contact, inventory]):
            return jsonify({"success": False, "message": "Missing required fields"}), 400

        existing_record = db.users.find_one({"contact": contact})

        if existing_record:
            updated_inventory = existing_record.get("inventory", [])
            if inventory not in updated_inventory:
                updated_inventory.append(inventory)

            db.users.update_one(
                {"contact": contact},
                {"$set": {"inventory": updated_inventory}}
            )

            return jsonify({"success": True, "message": "Inventory type added to existing booking!"}), 200

        return jsonify({"success": False, "message": "Contact not found"}), 404

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    
@core_bp.route('/submit_signup', methods=['POST'])
def submit_signup():
    db = current_app.config['db']
    data = request.json

    contact = data.get('contact')
    if not contact:
        return jsonify({"success": False, "message": "Contact is missing"})

    update_data = {
        "name": data.get("name"),
        "email": data.get("email"),
        "company": data.get("company"),
        "location": data.get("location"),
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
    }

    result = db.users.update_one({"contact": contact}, {"$set": update_data}, upsert=True)

    return jsonify({"success": True})


@core_bp.route('/register_or_update_user', methods=['POST'])
def register_or_update_user():
    db = current_app.config['db']
    data = request.json
    contact = data.get('contact')
    if not contact:
        return jsonify({'success': False, 'message': 'Contact number missing'}), 400

    existing_user = db.users.find_one({'contact': contact})
    if existing_user:
        db.users.update_one({'contact': contact}, {'$set': {
            'name': data.get('name'),
            'company': data.get('company'),
            'email': data.get('email'),
        }})
    else:
        db.users.insert_one({
            'name': data.get('name'),
            'company': data.get('company'),
            'email': data.get('email'),
            'contact': contact,
        })

    return jsonify({'success': True})

@core_bp.app_errorhandler(404)
def page_not_found(e):
    flash("Page not found. Redirected to homepage.", "warning")
    return redirect(url_for('core_bp.index'))

@core_bp.route('/cubispace')
def cubispace():
    from bson import ObjectId
    db = current_app.config['db']  # Get MongoDB database from app context
    collection = db.fillurdetails  # Access the 'fillurdetails' collection
    razorpay_key = current_app.config.get("RAZORPAY_KEY_ID")

    contact = request.args.get('contact')
    inventory_type = request.args.get('inventory')
    seater = request.args.get('seater')

    property_data = collection.find_one({"coworking_name": "Cubispace"})
    if not property_data:
        return "Property not found", 404

    selected_inventory = None
    total_price = None
    display_inventory_type = ""
    selected_price_value = 0

    # Define display-friendly names
    inventory_map = {
        "daypass": "Day Pass",
        "meetingroom": "Meeting Room"
    }

    # Price logic (hardcoded)
    price_map = {
        "daypass": {
            "label": "500 /seat/day",
            "value": 500
        },
        "meetingroom": {
            "4": {"label": "500 /hour", "value": 500},
            "6": {"label": "700 /hour", "value": 700},
            "25": {"label": "1000 /hour", "value": 1000}
        }
    }

    # Extract office timings
    office_timings = property_data.get("office_timings", {
        "opening_time": "09:00",
        "closing_time": "21:00"
    })

    meeting_timings = None

    if inventory_type:
        inventory_key = inventory_type.lower()
        display_inventory_type = inventory_map.get(inventory_key, inventory_type.title())

        for item in property_data.get('inventory', []):
            if inventory_type.lower() in item.get('type', '').lower():
                selected_inventory = item
                break

        if inventory_key == 'meetingroom' and seater:
            price_info = price_map['meetingroom'].get(seater)
            if price_info:
                total_price = price_info["label"]
                selected_price_value = price_info["value"]
        elif inventory_key == 'daypass':
            price_info = price_map['daypass']
            total_price = price_info["label"]
            selected_price_value = price_info["value"]
        else:
            selected_price_value = 0

    return render_template(
        "cubispace.html",
        property=property_data,
        inventoryType=display_inventory_type,
        selected_inventory=selected_inventory,
        total_price=total_price,
        price_value=selected_price_value,
        seater=seater,
        razorpay_key=razorpay_key,
        contact=contact,
        office_timings=property_data.get("office_timings", {}),
        meeting_timings=meeting_timings  # Pass meeting room timing to frontend
    )

@core_bp.route('/workdesq')
def workdesq():
    from bson import ObjectId
    db = current_app.config['db']  # Get MongoDB database from app context
    collection = db.fillurdetails  # Access the 'fillurdetails' collection
    razorpay_key = current_app.config.get("RAZORPAY_KEY_ID")

    contact = request.args.get('contact')
    inventory_type = request.args.get('inventory')
    seater = request.args.get('seater')

    property_data = collection.find_one({"coworking_name": "Workdesq"})
    if not property_data:
        return "Property not found", 404

    selected_inventory = None
    total_price = None
    selected_price_value = 0
    display_inventory_type = ""

    # Define display-friendly names
    inventory_map = {
        "daypass": "Day Pass",
        "meetingroom": "Meeting Room"
    }

    # Price logic (hardcoded)
    price_map = {
        "daypass": {
            "label": "500 /seat/day",
            "value": 500
        },
        "meetingroom": {
            "4": {"label": "499 /hour", "value": 499},
            "8": {"label": "800 /hour", "value": 800}
        }
    }

    # Extract office timings
    office_timings = property_data.get("office_timings", {
        "opening_time": "09:00",
        "closing_time": "21:00"
    })

    meeting_timings = None

    if inventory_type:
        inventory_key = inventory_type.lower()
        display_inventory_type = inventory_map.get(inventory_key, inventory_type.title())

        for item in property_data.get('inventory', []):
            if inventory_type.lower() in item.get('type', '').lower():
                selected_inventory = item
                break

        if inventory_key == 'meetingroom' and seater:
            price_info = price_map['meetingroom'].get(seater)
            if price_info:
                total_price = price_info["label"]
                selected_price_value = price_info["value"]
                meeting_timings = {
                    "opening_time": "09:00",
                    "closing_time": "21:00"
                }
        elif inventory_key == 'daypass':
            price_info = price_map['daypass']
            total_price = price_info["label"]
            selected_price_value = price_info["value"]

    return render_template(
        "workdesq.html",
        property=property_data,
        inventoryType=display_inventory_type,
        selected_inventory=selected_inventory,
        total_price=total_price,
        price_value=selected_price_value,
        seater=seater,
        razorpay_key=razorpay_key,
        contact=contact,
        office_timings=property_data.get("office_timings", {}),
        meeting_timings=meeting_timings  # Pass meeting room timing to frontend
    )

@core_bp.route('/worqspot')
def worqspot():
    from bson import ObjectId
    db = current_app.config['db']  # Get MongoDB database from app context
    collection = db.fillurdetails  # Access the 'fillurdetails' collection
    razorpay_key = current_app.config.get("RAZORPAY_KEY_ID")

    contact = request.args.get('contact')
    inventory_type = request.args.get('inventory')
    seater = request.args.get('seater')

    property_data = collection.find_one({"coworking_name": "Worqspot"})
    if not property_data:
        return "Property not found", 404

    selected_inventory = None
    total_price = None
    display_inventory_type = ""
    selected_price_value = 0

    # Define display-friendly names
    inventory_map = {
        "daypass": "Day Pass",
        "meetingroom": "Meeting Room"
    }

    price_map = {
        "daypass": {
            "label": "600 /seat/day",
            "value": 600
        },
        "meetingroom": {
            "6": {"label": "600 /hour", "value": 600},
            "12": {"label": "1200 /hour", "value": 1200}
        }
    }

    # Extract office timings
    office_timings = property_data.get("office_timings", {
        "opening_time": "09:00",
        "closing_time": "21:00"
    })

    meeting_timings = None

    if inventory_type:
        inventory_key = inventory_type.lower()
        display_inventory_type = inventory_map.get(inventory_key, inventory_type.title())

        for item in property_data.get('inventory', []):
            if inventory_type.lower() in item.get('type', '').lower():
                selected_inventory = item
                break

        if inventory_key == 'meetingroom' and seater:
            price_info = price_map['meetingroom'].get(seater)
            if price_info:
                total_price = price_info["label"]
                selected_price_value = price_info["value"]
                meeting_timings = {
                    "opening_time": "09:00",
                    "closing_time": "21:00"
                }
        elif inventory_key == 'daypass':
            price_info = price_map['daypass']
            total_price = price_info["label"]
            selected_price_value = price_info["value"]

    return render_template(
        "worqspot.html",
        property=property_data,
        inventoryType=display_inventory_type,
        selected_inventory=selected_inventory,
        total_price=total_price,
        price_value=selected_price_value,
        seater=seater,
        razorpay_key=razorpay_key,
        contact=contact,
        office_timings=property_data.get("office_timings", {}),
        meeting_timings=meeting_timings  # Pass meeting room timing to frontend
    )

@core_bp.route('/create_order', methods=['POST'])
def create_order():
    client = current_app.config['razorpay_client']
    try:
        data = request.json
        amount = int(data.get("amount", 0)) * 100  # Convert to paise
        receipt_id = data.get("receipt", f"receipt_{datetime.now().timestamp()}")

        razorpay_order = client.order.create({
            "amount": amount,
            "currency": "INR",
            "receipt": receipt_id,
            "payment_capture": 1
        })

        return jsonify({
            "success": True,
            "id": razorpay_order["id"],
            "amount": razorpay_order["amount"],
            "currency": razorpay_order["currency"]
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@core_bp.route("/store_verified_user", methods=["POST"])
def store_verified_user():
    db = current_app.config['db']
    data = request.get_json()
    contact = data.get("contact")

    if not contact:
        return jsonify({"success": False, "message": "Contact missing"})

    existing_user = db.users.find_one({"contact": contact})
    if not existing_user:
        db.users.insert_one({"contact": contact})  # insert new user with only contact

    return jsonify({"success": True})

@core_bp.route('/save_user_contact', methods=['POST'])
def save_user_contact():
    db = current_app.config['db']
    data = request.json
    phone = data.get('phone')
    
    if not phone:
        return jsonify(success=False, message="Phone number missing"), 400

    users = db.users  # Create or use the `users` collection
    users.update_one(
        {"phone": phone},
        {"$setOnInsert": {"phone": phone}},
        upsert=True
    )
    return jsonify(success=True)

@core_bp.route('/update_user_details', methods=['POST'])
def update_user_details():
    db = current_app.config['db']
    data = request.json

    phone = data.get('phone')
    if not phone:
        return jsonify(success=False, message="Missing phone"), 400

    update_fields = {
        "inventory_type": data.get('inventory_type'),
        "seater": data.get('seater'),
        "timestamp": datetime.datetime.utcnow()
    }

    users = db.users
    users.update_one(
        {"phone": phone},
        {"$set": update_fields}
    )

    return jsonify(success=True)
