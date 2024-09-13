from flask import Blueprint, render_template, request, jsonify, flash, session, current_app
from collections import defaultdict
import datetime
from core.email_handler import send_email_with_pdf
from bson import ObjectId  # Import ObjectId to handle MongoDB _id type conversion
import threading
from integrations.gsheet_updater import handle_new_property_entry

# Function to handle Google Sheet updates in the background
def update_gsheet_background(app, db, property_data):
    with app.app_context():  # Ensure app context is available in the background thread
        try:
            handle_new_property_entry(db, property_data)  # Update the Google Sheet
        except Exception as e:
            print(f"Failed to update Google Sheet: {e}")

# Helper function to send the email in the background
def send_email_background(app, email, name, filtered_properties):
    with app.app_context():  # Push the application context
        try:
            success, pdf_buffer = send_email_with_pdf(email, name, filtered_properties)
        except Exception as e:
            pass

# Define the Blueprint for core routes
core_bp = Blueprint('core_bp', __name__)

# Route to render index.html
@core_bp.route('/')
def index():
    db = current_app.config['db']  # Get the db instance from the app config

    # Fetch city data and count number of workspaces per city
    city_workspace_counts = defaultdict(int)
    coworking_spaces = db.coworking_spaces.find()  # Query all coworking spaces

    # Counting workspaces for each city
    for space in coworking_spaces:
        city_workspace_counts[space['city']] += 1

    # Preparing the data in a format suitable for the template
    city_data = []
    images = ['BangaloreAsset 13.svg', 'MumbaiAsset 14.svg', 'DelhiAsset 15.svg', 'AhemdabadAsset 16.svg', 'PuneAsset 17.svg']
    
    for idx, (city, count) in enumerate(city_workspace_counts.items()):
        city_data.append({
            'name': city,
            'workspaces': count,
            'image': images[idx % len(images)]  # Cyclic order for images
        })

    # Render the template with the dynamic city data
    return render_template('index.html', city_data=city_data)

# Route to handle form submission (Your Info form)
@core_bp.route('/submit_info', methods=['POST'])
def submit_info():
    db = current_app.config['db']  # Get the db instance from the app config

    # Get form data
    name = request.form.get('name')
    contact = request.form.get('contact')
    company = request.form.get('company')
    email = request.form.get('email')

    # Check if the user exists in the database
    existing_user = db.users.find_one({'contact': contact})

    if existing_user:
        # If the user exists, fetch their user_id and save it in the session
        session['user_id'] = str(existing_user['_id'])
        flash('Welcome back! Your details are already in our system.', 'success')
        return jsonify({'status': 'exists', 'message': 'User exists', 'user_id': session['user_id']})
    else:
        # If the user doesn't exist, store user data in the `users` collection
        new_user = {
            'name': name,
            'contact': contact,
            'company': company,
            'email': email
        }
        result = db.users.insert_one(new_user)
        session['user_id'] = str(result.inserted_id)  # Save new user_id in the session
        session['name'] = name
        session['email'] = email
        session['contact'] = contact
        flash('User information saved successfully.', 'success')
        return jsonify({'status': 'success', 'message': 'User added successfully', 'user_id': session['user_id']})

# Route to handle user preferences submission (Your Preference form)
@core_bp.route('/submit_preferences', methods=['POST'])
def submit_preferences():
    db = current_app.config['db']

    # Get form data
    seats = request.form.get('seats')
    location = request.form.get('location')
    area = request.form.get('area')
    budget = request.form.get('budget')

    # Check if the session has a user_id
    user_id = session.get('user_id')

    if not user_id:
        flash('Please fill out the "Your Info" form first.', 'error')
        return jsonify({'status': 'error', 'message': 'User information is missing'})

    try:
        # Convert user_id to ObjectId for querying
        user_object_id = ObjectId(user_id)
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Invalid user ID format'})

    # Fetch name, email, and contact from the users collection using user_object_id
    user = db.users.find_one({'_id': user_object_id})

    if not user:
        flash('User not found. Please fill out the "Your Info" form again.', 'error')
        return jsonify({'status': 'error', 'message': 'User not found'})

    name = user.get('name')
    email = user.get('email')

    # Fetch properties that match the user's preferences
    filtered_properties = list(db.coworking_spaces.find({
        'city': location,
        'micromarket': area,
        'price': {'$lte': float(budget)}
    }))

    # Prepare property names for logging (or mark as N/A)
    property_names = ", ".join([p['name'] for p in filtered_properties]) if filtered_properties else 'N/A'

    # Store preferences in the `properties` collection
    new_property = {
        'user_id': user_object_id,  # Ensure user_id is an ObjectId
        'seats': seats,
        'city': location,  # Ensure city is passed
        'micromarket': area,  # Ensure micromarket is passed
        'budget': budget,
        'property_names': property_names,  # Capture the names of properties for sharing
        'date': datetime.datetime.now()
    }

    # Insert property data into the collection
    db.properties.insert_one(new_property)

    # Background threads for email and Google Sheets updates
    app = current_app._get_current_object()
    email_thread = threading.Thread(target=send_email_background, args=(app, email, name, filtered_properties))
    email_thread.start()

    gsheet_thread = threading.Thread(target=update_gsheet_background, args=(app, db, new_property))
    gsheet_thread.start()

    return jsonify({'status': 'success', 'message': 'Preferences saved. Redirecting to the report.'})

# Route to fetch unique locations (cities)
@core_bp.route('/get_locations', methods=['GET'])
def get_locations():
    db = current_app.config['db']
    cities = db.coworking_spaces.distinct('city')
    return jsonify({'locations': cities})

# Route to fetch unique micromarkets based on selected city
@core_bp.route('/get_micromarkets', methods=['GET'])
def get_micromarkets():
    db = current_app.config['db']
    city = request.args.get('city')
    micromarkets = db.coworking_spaces.distinct('micromarket', {'city': city})
    return jsonify({'micromarkets': micromarkets})

# Route to fetch unique prices based on selected city and micromarket
@core_bp.route('/get_prices', methods=['GET'])
def get_prices():
    db = current_app.config['db']
    city = request.args.get('city')
    micromarket = request.args.get('micromarket')
    prices = db.coworking_spaces.distinct('price', {'city': city, 'micromarket': micromarket})
    return jsonify({'prices': prices})
