from flask import Blueprint, request, session, redirect, url_for, render_template, current_app, flash
from bson import ObjectId
import datetime  # Import datetime for date handling
from bson.json_util import dumps  # Import for handling BSON types
import requests, os

# Define blueprint for operators
operators_bp = Blueprint('operators', __name__, url_prefix='/operators', template_folder='templates')

ZOHO_CONTRACTS_API_URL = "https://contracts.zoho.com/api/v1/contracts"


@operators_bp.route('/login', methods=['GET', 'POST'])
def operators_login():
    if 'operator_phone' in session:
        return redirect(url_for('operators.inventory'))  # Redirect if already logged in
    
    if request.method == 'POST':
        mobile = request.form.get('mobile')  # Get mobile number from form
        db = current_app.config['db']
        
        # Authentication logic based on mobile in fillurdetails collection
        operator = db.fillurdetails.find_one({'owner.phone': mobile})
        
        if operator:
            # Store operator's phone in session
            session['operator_phone'] = mobile
            
            # Check if an agreement exists for this operator, if not create one
            existing_agreement = db.agreement.find_one({'operator_mobile': mobile})
            if not existing_agreement:
                new_agreement = {
                    "operator_name": operator['owner']['name'],
                    "operator_mobile": mobile,
                    "operator_email": operator['owner']['email'],
                    "coworking_name": operator['coworking_name'],
                    "commission_rate": "10%",  # Fixed for now
                    "signed": False,
                    "sign_date": None,
                    "signed_pdf_url": None
                }
                db.agreement.insert_one(new_agreement)
            
            return redirect(url_for('operators.inventory'))
        else:
            return render_template('operators_login.html', error="Invalid mobile number")
    
    return render_template('operators_login.html')


@operators_bp.route('/logout')
def operators_logout():
    session.pop('operator_phone', None)
    return redirect(url_for('operators.operators_login'))


@operators_bp.route('/inventory', methods=['GET'])
def inventory():
    if 'operator_phone' not in session:
        return redirect(url_for('operators.operators_login'))
    
    db = current_app.config['db']
    
    operator_phone = session['operator_phone']
    
    # Fetch operator's name from one of the fillurdetails entries
    operator = db.fillurdetails.find_one({'owner.phone': operator_phone})
    if operator:
        owner_name = operator['owner']['name']
    else:
        owner_name = 'Operator'
    
    # Fetch all fillurdetails entries for this operator
    inventory_cursor = db.fillurdetails.find({
        'owner.phone': operator_phone
    })

    # Convert cursor to list and convert '_id' to string
    inventory = []
    for space in inventory_cursor:
        space['_id'] = str(space['_id'])
        inventory.append(space)
    
    # Pass operator's name and inventory to the template
    return render_template('operators_inventory.html', inventory=inventory, owner_name=owner_name)



# Constants
ZOHO_CONTRACTS_API_URL = "https://contracts.zoho.com/api/v1/contracts"
ZOHO_CLIENT_ID = os.getenv('ZOHO_CLIENT_ID')
ZOHO_CLIENT_SECRET = os.getenv('ZOHO_CLIENT_SECRET')
ZOHO_REDIRECT_URI = os.getenv('ZOHO_REDIRECT_URI')
ZOHO_AUTH_URL = 'https://accounts.zoho.com/oauth/v2/auth'
ZOHO_TOKEN_URL = 'https://accounts.zoho.com/oauth/v2/token'
ZOHO_SCOPES = 'ZohoContracts.contracts.ALL'


@operators_bp.route('/zoho-auth')
def zoho_auth():
    auth_url = (f"{ZOHO_AUTH_URL}?client_id={ZOHO_CLIENT_ID}&response_type=code"
                f"&scope={ZOHO_SCOPES}&redirect_uri={ZOHO_REDIRECT_URI}&access_type=offline")
    return redirect(auth_url)

@operators_bp.route('/callback')
def zoho_callback():
    authorization_code = request.args.get('code')
    if not authorization_code:
        return "Authorization code not provided.", 400

    # Exchange authorization code for access token
    token_response = requests.post(ZOHO_TOKEN_URL, data={
        'grant_type': 'authorization_code',
        'client_id': ZOHO_CLIENT_ID,
        'client_secret': ZOHO_CLIENT_SECRET,
        'redirect_uri': ZOHO_REDIRECT_URI,
        'code': authorization_code
    })

    token_data = token_response.json()

    if 'access_token' in token_data:
        session['zoho_access_token'] = token_data['access_token']
        session['zoho_refresh_token'] = token_data.get('refresh_token')
        return redirect(url_for('core_bp.show_agreement'))  # Redirect after successful authentication
    else:
        return f"Failed to obtain access token: {token_data.get('error', 'Unknown error')}", 400

def refresh_zoho_token():
    refresh_token = session.get('zoho_refresh_token')
    if not refresh_token:
        return "No refresh token found."

    token_response = requests.post(ZOHO_TOKEN_URL, data={
        'grant_type': 'refresh_token',
        'client_id': ZOHO_CLIENT_ID,
        'client_secret': ZOHO_CLIENT_SECRET,
        'refresh_token': refresh_token
    })

    token_data = token_response.json()

    if 'access_token' in token_data:
        session['zoho_access_token'] = token_data['access_token']
        return token_data['access_token']
    else:
        return f"Error refreshing token: {token_data.get('error_description', 'Unknown error')}", 400


# Function to create Zoho Contract
def create_zoho_contract(operator_name, email, coworking_name, agreement_details):
    # Get the access token from session
    access_token = session.get('zoho_access_token')

    # If no access token is found, redirect to OAuth
    if not access_token:
        return redirect(url_for('operators.zoho_auth'))

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }

    # Define the contract data
    contract_data = {
        "template_id": "your_template_id",  # Zoho Contract Template ID, update with your actual template ID
        "contract_title": f"Agreement with {coworking_name}",
        "contract_type": "Standard Agreement",
        "parties": [
            {
                "role": "Operator",
                "name": operator_name,
                "email": email
            }
        ],
        "custom_fields": {
            "commission_rate": agreement_details['commission_rate'],
            "coworking_name": agreement_details['coworking_name'],
        }
    }

    # Send the request to Zoho Contracts API
    response = requests.post(ZOHO_CONTRACTS_API_URL, headers=headers, json=contract_data)

    if response.status_code == 201:
        contract_info = response.json()
        return contract_info['contract_url']  # Return contract URL for signing
    else:
        print(f"Error creating contract: {response.text}")
        return None

# Route to send contract
@operators_bp.route('/send_contract', methods=['GET'])
def send_contract():
    if 'operator_phone' not in session:
        return redirect(url_for('operators.operators_login'))

    db = current_app.config['db']
    operator_phone = session['operator_phone']

    # Fetch operator details
    operator = db.fillurdetails.find_one({'owner.phone': operator_phone})
    if not operator:
        flash("Operator not found.")
        return redirect(url_for('operators.inventory'))

    # Fetch agreement details for the operator
    agreement = db.agreement.find_one({'operator_mobile': operator_phone})
    if not agreement:
        flash("Agreement not found for this operator.")
        return redirect(url_for('operators.inventory'))
    
    zoho_access_token= session.get('zoho_access_token')
    if not zoho_access_token:
        flash("Zoho access token is missing. Please authenticate again.")
        return redirect(url_for('operators.zoho_auth'))

    # Create Zoho contract for the operator
    contract_url = create_zoho_contract(
        operator_name=operator['owner']['name'],
        email=operator['owner']['email'],
        coworking_name=operator['coworking_name'],
        agreement_details=agreement
    )

    if contract_url:
        # Store contract URL in the agreement document
        db.agreement.update_one(
            {'operator_mobile': operator_phone},
            {'$set': {'signed_pdf_url': contract_url}}
        )

        flash(f"Contract sent successfully. Please sign at: {contract_url}")
    else:
        flash("Failed to create contract.")

    return redirect(url_for('operators.show_agreement'))


@operators_bp.route('/show_agreement', methods=['GET'])
def show_agreement():
    if 'operator_phone' not in session:
        return redirect(url_for('operators.operators_login'))

    db = current_app.config['db']
    operator_phone = session['operator_phone']
    
    # Fetch the agreement based on the operator's phone number
    agreement = db.agreement.find_one({'operator_mobile': operator_phone})

    if agreement:
        return render_template('show_agreement.html', agreement=agreement)
    else:
        flash("No agreement found for this operator.")
        return redirect(url_for('operators.inventory'))


@operators_bp.route('/edit_space/<space_id>', methods=['GET', 'POST'])
def edit_space(space_id):
    if 'operator_phone' not in session:
        return redirect(url_for('operators.operators_login'))
    
    db = current_app.config['db']
    
    operator_phone = session['operator_phone']
    
    # Fetch the space data based on space_id and ensure it belongs to the logged-in operator
    space = db.fillurdetails.find_one({
        '_id': ObjectId(space_id),
        'owner.phone': operator_phone  # Ensure the space belongs to the operator
    })
    
    if not space:
        flash("You do not have permission to edit this space.")
        return redirect(url_for('operators.inventory'))
    
    if request.method == 'POST':
        try:
            # Extract owner information
            name = request.form.get('name')
            owner_phone = request.form.get('owner_phone')
            owner_email = request.form.get('owner_email')
            coworking_name = request.form.get('coworking_name')

            # Get where the user heard from us
            hear_from = request.form.get('hear_from')

            # Get list of space indices
            space_indices = request.form.getlist('space_indices[]')

            # Get lists of space data
            cities = request.form.getlist('city[]')
            micromarkets = request.form.getlist('micromarket[]')
            total_seats_list = request.form.getlist('total_seats[]')
            current_vacancies = request.form.getlist('current_vacancy[]')

            # We can assume there is only one space in editing
            idx = space_indices[0]
            city = cities[0]
            micromarket = micromarkets[0]
            total_seats = total_seats_list[0]
            current_vacancy = current_vacancies[0]

            # Get inventories for this space
            inventory_types = request.form.getlist(f'inventory_type_{idx}[]')
            inventory_counts = request.form.getlist(f'inventory_count_{idx}[]')
            price_per_seats = request.form.getlist(f'price_per_seat_{idx}[]')

            inventory = []
            for i in range(len(inventory_types)):
                inventory.append({
                    'type': inventory_types[i],
                    'count': int(inventory_counts[i]),
                    'price_per_seat': float(price_per_seats[i])
                })

            # Handle file uploads (Images for Layouts)
            layout_images = request.files.getlist(f'layout_images_{idx}[]')

            # Existing images handling
            existing_images = space.get('layout_images', [])

            # Process new images if any
            if layout_images and any(file.filename != '' for file in layout_images):
                new_image_links = process_and_upload_images(layout_images, {'name': name}, coworking_name)
                layout_image_links = existing_images + new_image_links
            else:
                layout_image_links = existing_images

            # Update the document in the database
            updated_space_data = {
                'owner': {
                    'name': name,
                    'phone': owner_phone,
                    'email': owner_email
                },
                'coworking_name': coworking_name,
                'city': city,
                'micromarket': micromarket,
                'total_seats': total_seats,
                'current_vacancy': current_vacancy,
                'inventory': inventory,
                'layout_images': layout_image_links,
                'hear_from': hear_from,
                'date': datetime.datetime.now()
            }

            db.fillurdetails.update_one(
                {'_id': ObjectId(space_id)},
                {'$set': updated_space_data}
            )
            
            flash("Space updated successfully!")
            return redirect(url_for('operators.inventory'))

        except Exception as e:
            flash(f"An error occurred while updating the space: {str(e)}")
            return redirect(url_for('operators.inventory'))
    else:
        # GET request: Prepare the space data by converting ObjectId fields to strings
        def convert_objectid_to_str(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if isinstance(value, ObjectId):
                        obj[key] = str(value)
                    elif isinstance(value, (dict, list)):
                        obj[key] = convert_objectid_to_str(value)
            elif isinstance(obj, list):
                obj = [convert_objectid_to_str(item) for item in obj]
            return obj

        space = convert_objectid_to_str(space)

        # Render the FillUrDetails.html with pre-filled data
        return render_template('FillUrDetails.html', space=space)
