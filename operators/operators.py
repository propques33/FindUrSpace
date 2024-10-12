from flask import Blueprint, request, session, redirect, url_for, render_template, current_app, flash
from bson import ObjectId
import datetime  # Import datetime for date handling
from bson.json_util import dumps  # Import for handling BSON types

# Define blueprint for operators
operators_bp = Blueprint('operators', __name__, url_prefix='/operators', template_folder='templates')

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
