from flask import Blueprint, render_template, request, jsonify, flash, session, current_app
import datetime

# Define the Blueprint for core routes
core_bp = Blueprint('core_bp', __name__)

# Route to render index.html
@core_bp.route('/')
def index():
    return render_template('index.html')

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
    
    user_id = session.get('user_id')
    if not user_id:
        flash('Please fill out the "Your Info" form first.', 'error')
        return jsonify({'status': 'error', 'message': 'User information is missing'})
    
    # Store preferences in the `properties` collection
    new_property = {
        'user_id': user_id,
        'seats': seats,
        'location': location,
        'area': area,
        'budget': budget,
        'date': datetime.datetime.now()
    }
    
    db.properties.insert_one(new_property)
    
    flash('Preferences saved successfully.', 'success')
    return jsonify({'status': 'success', 'message': 'Preferences saved successfully'})

# Route to fetch unique locations (cities)
@core_bp.route('/get_locations', methods=['GET'])
def get_locations():
    print("fetching locations")
    db = current_app.config['db']
    
    # Get unique city values
    cities = db.coworking_spaces.distinct('city')
    
    return jsonify({'locations': cities})  # Return only 5 cities initially

# Route to fetch unique micromarkets based on selected city
@core_bp.route('/get_micromarkets', methods=['GET'])
def get_micromarkets():
    db = current_app.config['db']
    city = request.args.get('city')
    
    # Get unique micromarket values for the selected city
    micromarkets = db.coworking_spaces.distinct('micromarket', {'city': city})
    
    return jsonify({'micromarkets': micromarkets})

# Route to fetch unique prices based on selected city and micromarket
@core_bp.route('/get_prices', methods=['GET'])
def get_prices():
    db = current_app.config['db']
    city = request.args.get('city')
    micromarket = request.args.get('micromarket')
    
    # Get unique prices for the selected city and micromarket
    prices = db.coworking_spaces.distinct('price', {'city': city, 'micromarket': micromarket})
    
    return jsonify({'prices': prices})
