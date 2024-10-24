from flask import Blueprint, request, session, redirect, url_for, render_template, current_app, flash
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
            operator = db.fillurdetails.find_one({'owner.phone': mobile})

            if operator:
                # Operator found, send OTP
                mobile_with_country_code = '+91' + mobile  # Assuming India country code

                otp_response = OtpLessAuth.send_otp(mobile_with_country_code)
                if otp_response['success']:
                    # Store requestId and mobile in session
                    session['requestId'] = otp_response['requestId']
                    session['mobile'] = mobile
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

            if not requestId or not mobile:
                return render_template('operators_login.html', error="Session expired. Please try again.")

            otp_response = OtpLessAuth.verify_otp(requestId, otp)
            if otp_response['success']:
                # OTP verified, log in user
                session['operator_phone'] = mobile

                # Check if an agreement exists for this operator, if not create one
                operator = db.fillurdetails.find_one({'owner.phone': mobile})
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


@operators_bp.route('/leads', methods=['GET'])
def leads():
    if 'operator_phone' not in session:
        return redirect(url_for('operators.operators_login'))

    # Render the leads page
    return render_template('operators_leads.html')


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