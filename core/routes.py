# current routes.py
from flask import Blueprint, render_template, request, jsonify, flash, session, current_app, send_from_directory, redirect, url_for,make_response
from collections import defaultdict
import datetime
from core.email_handler import send_email_and_whatsapp_with_pdf1
from bson import ObjectId  # Import ObjectId to handle MongoDB _id type conversion
from bson.regex import Regex
import threading
import io
import os
import pandas as pd
import requests
from dotenv import load_dotenv
from integrations.gsheet_updater import handle_new_property_entry
from integrations.google_drive_integration import authenticate_google_drive, upload_image_to_google_drive
from core.image_upload import process_and_upload_images
from integrations.otplessauth import OtpLessAuth
from integrations.gsheet_updater import handle_new_user_entry


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
        # If the user exists, fetch their user_id and save it in the session
        session['user_id'] = str(existing_user['_id'])
        # ✅ Update Google Sheets with latest form submission
        google_sheet_status = handle_new_user_entry(user_data)
        return jsonify({'status': 'exists', 'message': 'User exists', 'redirect': '/thankyou'})
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
    location = request.form.get('location')
    area = request.form.get('area')
    budget = request.form.get('budget')
    inventory_type = request.form.get('inventory-type')  # New field
    hear_about = request.form.get('hear-about')  # New field
    
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
    
    # Check if the session has a user_id
    user_id = session.get('user_id')

    if not user_id:
        flash('Please fill out the "Your Info" form first.', 'error')
        return jsonify({'status': 'error', 'message': 'User information is missing'})

    try:
        user_object_id = ObjectId(user_id)
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Invalid user ID format'})

    # Fetch user information
    user = db.users.find_one({'_id': user_object_id})
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

    # Store preferences in the `properties` collection
    new_property = {
        'user_id': user_object_id,
        'seats': seats,
        'city': location,
        'micromarket': area,
        'budget': budget,
        'inventory_type': inventory_type,  # Save new field
        'hear_about': hear_about,  # Save new field
        'property_names': property_names,
        'operator_numbers': operator_numbers,
        'center_manager_numbers': center_manager_numbers, 
        'date': datetime.datetime.now()
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

    return jsonify({'status': 'success', 'message': 'Preferences saved. Redirecting to the report.'})

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
    
@core_bp.route('/tc')
def terms_and_conditions():
    return render_template('T&C.html')

@core_bp.route('/faqs')
def freq_asked_ques():
    return render_template('FAQs.html')

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
            for idx, city, micromarket,address, total_seats, current_vacancy,center_manager_name, center_manager_contact, workspace_type in zip(space_indices, cities, micromarkets,addresses, total_seats_list, current_vacancies,center_manager_names, center_manager_contacts, workspace_types):
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

                 # Upload Property Images
                property_images = request.files.getlist(f'property_images_{idx}[]')
                property_image_links = process_and_upload_images(property_images, {'name': name}, coworking_name,category="property")

                # Get Workspace Type Details
                inventory = []
                # Get Workspace Type Details
                if workspace_type == "Coworking Spaces":
                    inventory_types = request.form.getlist(f'inventory_type_{idx}[]')
                    inventory_counts = request.form.getlist(f'inventory_count_{idx}[]')
                    price_per_seats = request.form.getlist(f'price_per_seat_{idx}[]')

                    for inv_idx in range(len(inventory_types)):
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
                        inventory.append({
                            'type': inventory_types[inv_idx],
                            'count': int(inventory_counts[inv_idx]),
                            'price_per_seat': float(price_per_seats[inv_idx]),
                            'images': inventory_image_links
                        })

                    amenities = request.form.getlist(f'amenities_{idx}[]')
                    open_from = request.form.get(f'open_from_{idx}')
                    open_to = request.form.get(f'open_to_{idx}')
                    opening_time = request.form.get(f'opening_time_{idx}')
                    closing_time = request.form.get(f'closing_time_{idx}')
                else:
                    rent_or_own = request.form.get(f'rent_or_own_{idx}')
                    area = request.form.get(f'area_{idx}')
                    total_floors = request.form.get(f'total_floors_{idx}')
                    floors_occupied = request.form.get(f'floors_occupied_{idx}')

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
                    'total_seats': int(total_seats),
                    'current_vacancy': int(current_vacancy),
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
                    'date': datetime.datetime.now()
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
                    property_details.update({
                        'rent_or_own': rent_or_own,
                        'area': area,
                        'total_floors': total_floors,
                        'floors_occupied': floors_occupied
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