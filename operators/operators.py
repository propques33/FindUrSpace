from flask import Blueprint, request, session, redirect, url_for, render_template, current_app, flash, jsonify
from bson import ObjectId
import datetime
from bson.json_util import dumps
import requests, os
from integrations.otplessauth import OtpLessAuth  # Import OtpLessAuth for OTP handling

# Define blueprint for operators
operators_bp = Blueprint('operators', __name__, url_prefix='/operators', template_folder='templates')

ZOHO_CONTRACTS_API_URL = "https://contracts.zoho.com/api/v1/contracts"

@operators_bp.route('/not_found', methods=['GET'])
def operators_not_found():
    return render_template('operators_not_found.html')


@operators_bp.route('/login', methods=['GET', 'POST'])
def operators_login():
    if 'operator_phone' in session:
        return redirect(url_for('operators.inventory'))  # Redirect if already logged in

    if request.method == 'POST':
        mobile = request.form.get('mobile')
        otp = request.form.get('otp')
        db = current_app.config['db']

        if mobile and not otp:
            # User submitted mobile number, check if operator exists
            operator_as_owner = db.fillurdetails.find_one({'owner.phone': mobile})
            operator_as_manager = db.fillurdetails.find_one({'center_manager.contact': mobile})

            if operator_as_owner or operator_as_manager:
                # Operator found (either owner or center manager), send OTP
                mobile_with_country_code = '+91' + mobile  # Assuming India country code

                otp_response = OtpLessAuth.send_otp(mobile_with_country_code)
                if otp_response['success']:
                    # Store requestId and mobile in session
                    session['requestId'] = otp_response['requestId']
                    session['mobile'] = mobile
                    session['role'] = 'owner' if operator_as_owner else 'center_manager'
                    # Render OTP form
                    return render_template('operators_login.html', otp_sent=True)
                else:
                    return render_template('operators_login.html', error=otp_response['message'])
            else:
                # Operator not found, redirect to "not found" page
                return redirect(url_for('operators.operators_not_found'))

        elif otp:
            # User submitted OTP, verify it
            requestId = session.get('requestId')
            mobile = session.get('mobile')
            role = session.get('role')

            if not requestId or not mobile or not role:
                return render_template('operators_login.html', error="Session expired. Please try again.")

            otp_response = OtpLessAuth.verify_otp(requestId, otp)
            if otp_response['success']:
                # OTP verified, log in user
                session['operator_phone'] = mobile

                # Check if an agreement exists for this operator, if not create one
                if role == 'owner':
                    operator = db.fillurdetails.find_one({'owner.phone': mobile})
                elif role == 'center_manager':
                    operator = db.fillurdetails.find_one({'center_manager.contact': mobile})
                else:
                    return render_template('operators_login.html', error="Invalid role detected. Please try again.")

                if role == 'owner':
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

                # Clean up session
                session.pop('requestId', None)
                session.pop('mobile', None)

                return redirect(url_for('operators.inventory'))
            else:
                return render_template('operators_login.html', error=otp_response['message'], otp_sent=True)
        else:
            return render_template('operators_login.html', error="Please enter your mobile number.")

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
    role = session.get('role', 'owner')  # Default to 'owner' if role is missing

    # Fetch inventory based on role
    if role == 'owner':
        query_field = 'owner.phone'
    elif role == 'center_manager':
        query_field = 'center_manager.contact'
    else:
        flash("Invalid role in session. Please log in again.", "error")
        return redirect(url_for('operators.operators_login'))

    # Fetch coworking spaces for the operator
    inventory_cursor = db.fillurdetails.find({query_field: operator_phone})

    # Convert cursor to list and convert '_id' to string
    inventory = []
    for space in inventory_cursor:
        space['_id'] = str(space['_id'])
        # Extract `center_manager` details safely
        center_manager = space.get('center_manager', {})
        space['center_manager_name'] = center_manager.get('name', 'N/A')
        space['center_manager_contact'] = center_manager.get('contact', 'N/A')
        inventory.append(space)

    # Pass operator's role and inventory to the template
    return render_template(
        'operators_inventory.html',
        inventory=inventory,
        role=role
    )


@operators_bp.route('/add_space', methods=['GET', 'POST'])
def add_space():
    if 'operator_phone' not in session:
        return redirect(url_for('operators.operators_login'))

    db = current_app.config['db']
    operator_phone = session['operator_phone']

    # Fetch operator details
    operator = db.fillurdetails.find_one({'owner.phone': operator_phone})
    if not operator:
        flash("Operator not found. Please contact support.", 'error')
        return redirect(url_for('operators.inventory'))

    owner_details = operator['owner']
    coworking_name = operator['coworking_name'] 

    if request.method == 'POST':
        try:
            # Extract owner information
            name = request.form.get('name')
            owner_phone = request.form.get('owner_phone')
            owner_email = request.form.get('owner_email')

            # Get space details
            space_indices = request.form.getlist('space_indices[]')
            cities = request.form.getlist('city[]')
            micromarkets = request.form.getlist('micromarket[]')
            total_seats_list = request.form.getlist('total_seats[]')
            current_vacancies = request.form.getlist('current_vacancy[]')
            center_manager_names = request.form.getlist('center_manager_name[]')
            center_manager_contacts = request.form.getlist('center_manager_contact[]')

            for idx, city, micromarket, total_seats, current_vacancy, manager_name, manager_contact in zip(
                space_indices, cities, micromarkets, total_seats_list, current_vacancies, center_manager_names, center_manager_contacts
            ):
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

                # Handle file uploads
                layout_images = request.files.getlist(f'layout_images_{idx}[]')
                uploaded_images = process_and_upload_images(layout_images, {'name': name}, coworking_name)

                new_space = {
                    'owner': owner_details,
                    'coworking_name': coworking_name,
                    'city': city,
                    'micromarket': micromarket,
                    'total_seats': total_seats,
                    'current_vacancy': current_vacancy,
                    'center_manager': {'name': manager_name, 'contact': manager_contact},
                    'inventory': inventory,
                    'layout_images': uploaded_images,
                    'interactive_layout': False,
                    'date': datetime.datetime.now(),
                }

                db.fillurdetails.insert_one(new_space)

            flash('Coworking space added successfully.', 'success')
            return redirect(url_for('operators.inventory'))

        except Exception as e:
            flash(f'Error while adding coworking space: {str(e)}', 'error')

    # Render the form for adding a new space
    return render_template('FillUrDetails.html',space=None,role=session.get('role', 'owner'),context='add_space',owner_details=owner_details,coworking_name=coworking_name)

@operators_bp.route('/edit_space/<space_id>', methods=['GET', 'POST'])
def edit_space(space_id):
    if 'operator_phone' not in session:
        return redirect(url_for('operators.operators_login'))

    db = current_app.config['db']
    operator_phone = session['operator_phone']
    role = session.get('role', 'owner')  # Get the role from the session

    # Fetch the space data based on space_id and ensure it belongs to the logged-in operator
    space = db.fillurdetails.find_one({
    '_id': ObjectId(space_id),
    '$or': [
        {'owner.phone': operator_phone},  # If logged-in user is the owner
        {'center_manager.contact': operator_phone}  # If logged-in user is the center manager
    ]
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

             # Extract center manager details
            center_manager_name = request.form.getlist('center_manager_name[]')
            center_manager_contact = request.form.getlist('center_manager_contact[]')

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

            # Extract inventory data
            inventory_types = request.form.getlist(f'inventory_type_1[]')
            inventory_counts = request.form.getlist(f'inventory_count_1[]')
            price_per_seats = request.form.getlist(f'price_per_seat_1[]')

            inventory = []
            for i in range(len(inventory_types)):
                inventory.append({
                    'type': inventory_types[i],
                    'count': int(inventory_counts[i]),
                    'price_per_seat': float(price_per_seats[i])
                })

            # Handle file uploads (Images for Layouts)
            layout_images = request.files.getlist(f'layout_images_1[]')
            existing_images = space.get('layout_images', [])

            # Process new images if any
            if layout_images and any(file.filename != '' for file in layout_images):
                new_image_links = process_and_upload_images(layout_images, {'name': name}, coworking_name)
                layout_image_links = existing_images + new_image_links
            else:
                layout_image_links = existing_images

            # Prepare the updated data structure for MongoDB
            updated_space_data = {
                'owner': {
                    'name': name,
                    'phone': owner_phone,
                    'email': owner_email
                },
                'coworking_name': coworking_name,
                'city': cities[0] if cities else space.get('city'),
                'micromarket': micromarkets[0] if micromarkets else space.get('micromarket'),
                'total_seats': total_seats_list[0] if total_seats_list else space.get('total_seats'),
                'current_vacancy': current_vacancies[0] if current_vacancies else space.get('current_vacancy'),
                'center_manager': {
                    'name': center_manager_name[0] if center_manager_name else space.get('center_manager', {}).get('name'),
                    'contact': center_manager_contact[0] if center_manager_contact else space.get('center_manager', {}).get('contact')
                },
                'inventory': inventory,
                'layout_images': layout_image_links,
                'interactive_layout': space.get('interactive_layout', False),  # Preserve the existing value
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
        return render_template('FillUrDetails.html', space=space,role=session.get('role', 'owner'),context='edit_space')
    
@operators_bp.route('/leads', methods=['GET'])
def leads():
    if 'operator_phone' not in session:
        return redirect(url_for('operators.operators_login'))

    db = current_app.config['db']
    operator_phone = session['operator_phone']

    # Find properties associated with the operator's phone number
    properties_query = {'operator_numbers': operator_phone}
    selected_city = request.args.get('city')
    if selected_city and selected_city != "All":
        properties_query['city'] = selected_city

    properties = db.properties.find(properties_query).sort('date', -1)
    
    leads = []
    cities_set = set()

    for property_data in properties:
        user = db.users.find_one({'_id': property_data['user_id']})
        if user:
            lead_status = db.operator_lead_status.find_one({'user_id': property_data['user_id'], 'property_id': property_data['_id']})

            if not lead_status:
                lead_status = {
                    'user_id': property_data['user_id'],
                    'property_id': property_data['_id'],
                    'opportunity_status': 'open',
                    'opportunity_stage': 'visit done'
                }
                db.operator_lead_status.insert_one(lead_status)

            # Ensure the date is properly formatted
            date_str = property_data.get('date', 'N/A')
            try:
                date = datetime.datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S.%f') if isinstance(date_str, str) else date_str
            except Exception as e:
                print(f"Error converting date: {e}")
                date = 'N/A'

            # Collect unique cities and micromarkets for filtering
            city = property_data.get('city', 'N/A')
            if city != 'N/A':
                cities_set.add(city)

            leads.append({
                'lead_id': str(lead_status['user_id']),
                'property_id': str(lead_status['property_id']),
                'user_name': user.get('name', 'Unknown'),
                'user_company': user.get('company', 'Unknown'),
                'user_email': user.get('email', 'N/A'),
                'user_contact': user.get('contact', 'N/A'),
                'city': city,
                'micromarket': property_data.get('micromarket', 'N/A'),
                'date': date,
                'property_seats': property_data.get('seats', 'N/A'),
                'property_budget': property_data.get('budget', 'N/A'),
                'opportunity_status': lead_status.get('opportunity_status', 'open'),
                'opportunity_stage': lead_status.get('opportunity_stage', 'visit done')
            })

    # Convert sets to sorted lists for filtering options in the template
    cities = sorted(list(cities_set))

    return render_template('operators_leads.html', leads=leads, cities=cities, selected_city=selected_city)

@operators_bp.route('/update_lead_status', methods=['POST'])
def update_lead_status():
    if 'operator_phone' not in session:
        print("User is not logged in. Redirecting to login page.")  # Debugging print
        return redirect(url_for('operators.operators_login'))

    db = current_app.config['db']
    data = request.json  
    try:
        lead_id = ObjectId(data.get('lead_id'))
        property_id = ObjectId(data.get('property_id'))
    except Exception as e:
        return jsonify({'status': 'failure', 'message': 'Invalid lead_id or property_id format'}), 400

    # Prepare the update data with only the provided fields
    update_data = {}
    if 'opportunity_status' in data:
        update_data['opportunity_status'] = data['opportunity_status']
    if 'opportunity_stage' in data:
        update_data['opportunity_stage'] = data['opportunity_stage']

    if not update_data:
        return jsonify({'status': 'failure', 'message': 'No fields to update'}), 400

    # Perform the update operation on the document
    try:
        result = db.operator_lead_status.update_one(
            {'user_id': lead_id, 'property_id': property_id},
            {'$set': update_data}
        )
        print("Update result:", result.raw_result)  # Log raw MongoDB update result

        # Check the outcome of the update operation
        if result.modified_count > 0:
            return jsonify({'status': 'success', 'message': 'Lead status updated successfully'})
        else:
            return jsonify({'status': 'failure', 'message': 'No changes made or lead not found'}), 400
    except Exception as e:
        print("Error during database update:", e)  # Log exception for debugging
        return jsonify({'status': 'failure', 'message': 'Error during database update'}), 500

@operators_bp.route('/get_micromarkets', methods=['GET'])
def get_micromarkets():
    if 'operator_phone' not in session:
        return jsonify({'status': 'failure', 'message': 'Unauthorized access'}), 401

    city = request.args.get('city')
    if not city:
        return jsonify({'status': 'failure', 'message': 'City is required'}), 400

    db = current_app.config['db']
    operator_phone = session['operator_phone']

    # Fetch micromarkets for the selected city based on the operator's spaces
    micromarkets = db.properties.distinct('micromarket', {'operator_numbers': operator_phone, 'city': city})
    micromarkets = [mm for mm in micromarkets if mm]  # Filter out None or empty values

    return jsonify({'status': 'success', 'micromarkets': sorted(micromarkets)})

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