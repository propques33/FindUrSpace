from flask import Blueprint, request, session, redirect, url_for, render_template, current_app, flash, jsonify
from bson import ObjectId
import datetime
from bson.json_util import dumps
import requests, os
from urllib.parse import urlencode
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from core.image_upload import process_and_upload_images
from flask_mail import Message

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
# Define blueprint for operators
operators_bp = Blueprint('operators', __name__, url_prefix='/operators', template_folder='templates')

ZOHO_CONTRACTS_API_URL = "https://contracts.zoho.com/api/v1/contracts"

@operators_bp.route('/not_found', methods=['GET'])
def operators_not_found():
    return render_template('operators_not_found.html')

@operators_bp.route('/under-development')
def operator_under_development():
    return render_template('operator_under_development.html')

@operators_bp.route('/login', methods=['GET', 'POST'])
def operators_login():
    if 'operator_phone' in session:
        return redirect(url_for('operators.inventory'))  # Redirect if already logged in

    if request.method == 'POST':
        try:
            mobile = request.form.get('mobile')
            role = request.form.get('role')
            db = current_app.config['db']

            if mobile:
                operator_as_owner = db.fillurdetails.find_one({'owner.phone': mobile})
                operator_as_manager = db.fillurdetails.find_one({'center_manager.contact': mobile})

                if operator_as_owner or operator_as_manager:
                    session['operator_phone'] = mobile
                    session['role'] = 'owner' if operator_as_owner else 'center_manager'
                    return redirect(url_for('operators.inventory'))
                else:
                    return redirect(url_for('core_bp.list_your_space'))
        except Exception as e:
            print(f"Login Error: {e}")
            return redirect(url_for('operators.operator_under_development'))

    return render_template('operators_login.html')



@operators_bp.route('/bookings', methods=['GET'])
def bookings():
    if 'operator_phone' not in session:
        return redirect(url_for('operators.operators_login'))

    db = current_app.config['db']
    operator_phone = session['operator_phone']

    # Fetch properties managed by the operator
     # Step 1: Fetch properties owned by the operator
    # Step 1: Fetch properties owned by the operator
    properties = list(db.fillurdetails.find({'owner.phone': operator_phone}))
    property_map = {str(prop['_id']): prop for prop in properties}  # Store properties in a dictionary

    # Step 2: Extract property IDs
    property_ids = list(property_map.keys())

    if not property_ids:
        flash("No properties found for this operator.", "warning")
        return render_template('operators_bookings.html', bookings=[])

    # Fetch bookings related to these properties
    bookings_cursor = db.booking.find({'property_id': {'$in': property_ids}})
    bookings = []
    
    for booking in bookings_cursor:
        property_details = property_map.get(booking['property_id'], {})
        booking['micromarket'] = property_details.get('micromarket', 'N/A')
        booking['city'] = property_details.get('city', 'N/A')

        booking['_id'] = str(booking['_id'])
        booking['property_id'] = str(booking['property_id'])
        booking['user_id'] = str(booking['user_id'])
        booking['date'] = booking['date'].strftime('%d %b %Y')
        booking['created_at'] = booking['created_at'].strftime('%d %b %Y %I:%M %p')

        # 🔽 Add display status and badge class based on status
        status = booking.get('status', '').lower()
        if status == 'paid':
            booking['display_status'] = 'Booking Confirmed'
            booking['status_class'] = 'bg-success'
        elif status == 'failed':
            booking['display_status'] = 'Payment Failed'
            booking['status_class'] = 'bg-danger'
        else:
            booking['display_status'] = 'Payment Pending'
            booking['status_class'] = 'bg-warning'

        bookings.append(booking)

    return render_template('operators_bookings.html', bookings=bookings)

@operators_bp.route('/visits', methods=['GET'])
def visits():
    if 'operator_phone' not in session:
        return redirect(url_for('operators.operators_login'))

    db = current_app.config['db']
    operator_phone = session['operator_phone']

    print(f"Fetching visits for owner with phone: {operator_phone}")

    # Step 1: Fetch properties owned by the operator
    properties = list(db.fillurdetails.find({'owner.phone': operator_phone}))


    if not properties:
        print("No properties found for this owner.")
        flash("No properties found for this operator.", "warning")
        return render_template('operators_visits.html', visits=[])
    
    # Step 2: Extract property IDs and convert them to strings for comparison
    property_map = {str(prop['_id']): prop for prop in properties}
    property_ids = [prop['_id'] for prop in properties]

    print(f"Properties found: {property_ids}")

    if not property_ids:
        flash("No properties found for this operator.", "warning")
        return render_template('operators_visits.html', visits=[])
    
    # Fetch visits related to these properties
    visits_cursor = db.visits.find({'property_id': {'$in': property_ids}})
    visits = []

    for visit in visits_cursor:
        # Fetch property details
        # Fetch property details from fillurdetails
        property_details = property_map.get(str(visit['property_id']), {})
        visit['micromarket'] = property_details.get('micromarket', 'N/A')
        visit['city'] = property_details.get('city', 'N/A')

        # Convert ObjectId fields to string for frontend use
        visit['_id'] = str(visit['_id'])
        visit['property_id'] = str(visit['property_id'])
        visit['user_id'] = str(visit['user_id'])
        visit['date'] = visit['date'].strftime('%d %b %Y')  # Format date
        visit['created_at'] = visit['created_at'].strftime('%d %b %Y %I:%M %p')

        visits.append(visit)

    if not visits:
        print("No visits found for the owner’s properties.")
    else:
        print(f"Total visits fetched: {len(visits)}")


    return render_template('operators_visits.html', visits=visits)


@operators_bp.route('/update_booking_status', methods=['POST'])
def update_booking_status():
    if 'operator_phone' not in session:
        return jsonify({'status': 'failure', 'message': 'Unauthorized access'}), 401

    db = current_app.config['db']
    data = request.json
    booking_id = data.get('booking_id')
    new_status = data.get('status')

    if not booking_id or not new_status:
        return jsonify({'status': 'failure', 'message': 'Missing parameters'}), 400

    # Update booking status
    db.booking.update_one({'_id': ObjectId(booking_id)}, {'$set': {'status': new_status}})
    
    return jsonify({'status': 'success', 'message': f'Booking status updated to {new_status}'}), 200


@operators_bp.route('/update_visit_status', methods=['POST'])
def update_visit_status():
    if 'operator_phone' not in session:
        return jsonify({'status': 'failure', 'message': 'Unauthorized access'}), 401

    db = current_app.config['db']
    data = request.json
    visit_id = data.get('visit_id')
    new_status = data.get('status')

    if not visit_id or not new_status:
        return jsonify({'status': 'failure', 'message': 'Missing parameters'}), 400

    # Update visit status
    db.visits.update_one({'_id': ObjectId(visit_id)}, {'$set': {'status': new_status}})
    
    return jsonify({'status': 'success', 'message': f'Visit status updated to {new_status}'}), 200


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
    role = session.get('role', 'owner')  # Default to 'owner'

    # Determine which field to query
    if role == 'owner':
        query_field = 'owner.phone'
    elif role == 'center_manager':
        query_field = 'center_manager.contact'
    else:
        flash("Invalid session role. Please login again.", "error")
        return redirect(url_for('operators.operators_login'))

    # Query spaces for this operator
    inventory_cursor = db.fillurdetails.find({query_field: operator_phone})
    inventory = []

    for space in inventory_cursor:
        # Convert ObjectId to string for URLs
        space['_id'] = str(space['_id'])

        # Set workspace type explicitly if not present
        workspace_type = space.get('workspace_type', '').strip()

        # Center manager info
        center_manager = space.get('center_manager', {})
        space['center_manager_name'] = center_manager.get('name', 'N/A')
        space['center_manager_contact'] = center_manager.get('contact', 'N/A')

        # Ensure required fields for both types
        if workspace_type == "Managed Offices":
            space.setdefault('furnishing_level', 'N/A')
            space.setdefault('floors_offered', [])
            space.setdefault('managed_office_amenities', [])
            space.setdefault('total_building_area', 0)
            space.setdefault('total_rental', 0)
            space.setdefault('lockin_period', 'N/A')
            space.setdefault('security_deposit', 0)
            space.setdefault('lease_term', 'N/A')
            space.setdefault('floorplate_area', 0)
            space.setdefault('floors_occupied', 'N/A')
            space.setdefault('rent_or_own', 'N/A')
        else:
            # Coworking fallback
            space.setdefault('inventory', [])
            space.setdefault('amenities', [])
            space.setdefault('total_seats', 'N/A')
            space.setdefault('current_vacancy', 'N/A')

        # General defaults
        space.setdefault('property_images', [])
        space.setdefault('micromarket', '')
        space.setdefault('city', '')
        space.setdefault('address', '')
        space.setdefault('space_description', '')
        space.setdefault('office_timings', None)

        inventory.append(space)

    return render_template('operators_inventory.html', inventory=inventory, role=role)

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

    space = db.fillurdetails.find_one({
        '_id': ObjectId(space_id),
        '$or': [
            {'owner.phone': operator_phone},
            {'center_manager.contact': operator_phone}
        ]
    })

    if not space:
        flash("You do not have permission to edit this space.")
        return redirect(url_for('operators.inventory'))

    if request.method == 'POST':
        try:
            # ✅ Step 1: Light Update for Basic Owner Info Only
            if request.form.get("edit_type") == "basic_info":
                updated_info = {
                    "coworking_name": request.form.get("coworking_name"),
                    "owner.name": request.form.get("name"),
                    "owner.phone": request.form.get("owner_phone"),
                    "owner.email": request.form.get("owner_email"),
                    "date": datetime.datetime.now(),
                    'status': 'Pending'  # 👈 Add this
                }
                db.fillurdetails.update_one({'_id': ObjectId(space_id)}, {'$set': updated_info})
                send_resubmission_email(name, owner_email, coworking_name, city, micromarket)
                flash("Owner info updated successfully.")
                return redirect(url_for('operators.inventory'))

            if request.form.get("edit_type") == "location_info":
                city = request.form.get("city")
                if city == "Other":
                    city = to_camel_case(request.form.get("custom_city", "").strip())

                micromarket = request.form.get("micromarket")
                if micromarket == "Other":
                    micromarket = to_camel_case(request.form.get("custom_micromarket", "").strip())

                address = request.form.get("address")
                distance = {
                    "metro": float(request.form.get("metro") or 0),
                    "airport": float(request.form.get("airport") or 0),
                    "bus": float(request.form.get("bus") or 0),
                    "railway": float(request.form.get("railway") or 0)
                }

                center_manager_name = request.form.get("center_manager_name")
                center_manager_contact = request.form.get("center_manager_contact")

                db.fillurdetails.update_one({'_id': ObjectId(space_id)}, {
                    '$set': {
                        'city': city,
                        'micromarket': micromarket,
                        'address': address,
                        'distance': distance,
                        'center_manager': {
                            'name': center_manager_name,
                            'contact': center_manager_contact
                        },
                        'date': datetime.datetime.now(),
                        "status": "Pending",
                    }
                })
                send_resubmission_email(name, owner_email, coworking_name, city, micromarket)
                flash("Location info updated successfully.")
                return redirect(url_for('operators.inventory'))

            # Owner & Basic Info
            name = request.form.get('name')
            owner_phone = request.form.get('owner_phone')
            owner_email = request.form.get('owner_email')
            coworking_name = request.form.get('coworking_name')

            space_idx = request.form.getlist('space_indices[]')[0]
            city = request.form.getlist('city[]')[0]
            micromarket = request.form.getlist('micromarket[]')[0]
            address = request.form.getlist('address[]')[0]
            current_vacancy = 0
            center_manager_name = request.form.getlist('center_manager_name[]')[0]
            center_manager_contact = request.form.getlist('center_manager_contact[]')[0]
            workspace_type = request.form.getlist('workspace_type[]')[0]

            # Distances
            distance_data = {
                'metro': float(request.form.getlist('distance_metro[]')[0] or 0),
                'airport': float(request.form.getlist('distance_airport[]')[0] or 0),
                'bus': float(request.form.getlist('distance_bus[]')[0] or 0),
                'railway': float(request.form.getlist('distance_railway[]')[0] or 0)
            }

            # Combine existing and new property images
            existing_property_images = space.get('property_images', [])
            property_images = request.files.getlist(f'property_images_{space_idx}[]')
            if property_images and property_images[0].filename != '':
                new_image_links = process_and_upload_images(property_images, {'name': name}, coworking_name, category="property", space_id=space_idx)
                combined_property_images = existing_property_images + new_image_links
            else:
                combined_property_images = existing_property_images

            # Other Fields
            space_description = request.form.get(f'space_description_{space_idx}')
            hear_from = request.form.get('hear_from')
            workspace_tool = request.form.get('workspace_tool')
            notification_preference = request.form.getlist('notification_preference')

            inventory = []
            if workspace_type == "Coworking Spaces":
                inventory_types = request.form.getlist(f'inventory_type_{space_idx}[]')
                inventory_counts = request.form.getlist(f'inventory_count_{space_idx}[]')
                price_per_seats = request.form.getlist(f'price_per_seat_{space_idx}[]')

                for inv_idx, inv_type in enumerate(inventory_types):
                    opening_time = request.form.get(f'opening_time_{space_idx}_{inv_idx + 1}')
                    closing_time = request.form.get(f'closing_time_{space_idx}_{inv_idx + 1}')

                    # Inventory Images
                    existing_inventory_images = []
                    if inv_idx < len(space.get('inventory', [])):
                        existing_inventory_images = space['inventory'][inv_idx].get('images', [])
                    inventory_images = request.files.getlist(f'inventory_images_{space_idx}_{inv_idx + 1}[]')
                    if inventory_images and inventory_images[0].filename != '':
                        new_inventory_links = process_and_upload_images(inventory_images, {'name': name}, coworking_name, category="inventory", space_id=space_idx, inventory_id=inv_idx + 1)
                        combined_inventory_images = existing_inventory_images + new_inventory_links
                    else:
                        combined_inventory_images = existing_inventory_images


                    if inv_type in ["Meeting rooms", "Private cabin"]:
                        try:
                            room_number = int(request.form.get(f'number_of_rooms_{space_idx}_{inv_idx + 1}') or 0)
                        except:
                            room_number = 0

                        room_details = []
                        for room_idx in range(1, room_number + 1):
                            try:
                                seating_capacity = int(request.form.get(f'seating_capacity_{space_idx}_{inv_idx + 1}_{room_idx}') or 0)
                            except:
                                seating_capacity = 0

                            try:
                                price = float(request.form.get(f'price_{space_idx}_{inv_idx + 1}_{room_idx}') or 0.0)
                            except:
                                price = 0.0

                            room_images_field = f"{'meeting_room' if inv_type == 'Meeting rooms' else 'private_cabin'}_images_{space_idx}_{inv_idx + 1}_{room_idx}[]"
                            try:
                                existing_room_images = space['inventory'][inv_idx]['room_details'][room_idx - 1]['images']
                            except:
                                existing_room_images = []
                            room_images = request.files.getlist(room_images_field)
                            if room_images and room_images[0].filename != '':
                                new_room_links = process_and_upload_images(room_images, {'name': name}, coworking_name, category=inv_type.lower().replace(" ", "_"), space_id=space_idx, inventory_id=inv_idx + 1, room_id=room_idx)
                                combined_room_images = existing_room_images + new_room_links
                            else:
                                combined_room_images = existing_room_images


                            room_details.append({
                                'room_number': room_idx,
                                'seating_capacity': seating_capacity,
                                'price': price,
                                'images': combined_room_images
                            })

                        try:
                            price_per_seat = float(price_per_seats[inv_idx])
                        except (IndexError, ValueError):
                            price_per_seat = 0.0
                        inventory.append({
                            'type': inv_type,
                            'room_count': room_number,
                            'price_per_seat': price_per_seat,
                            'opening_time': opening_time,
                            'closing_time': closing_time,
                            'room_details': room_details,
                            'images': combined_inventory_images
                        })
                    else:
                        try:
                            count = int(inventory_counts[inv_idx])
                        except (IndexError, ValueError):
                            count = 0

                        try:
                            price_per_seat = float(price_per_seats[inv_idx])
                        except (IndexError, ValueError):
                            price_per_seat = 0.0

                        inventory.append({
                            'type': inv_type,
                            'count': count,
                            'price_per_seat': price_per_seat,
                            'images': combined_inventory_images
                        })

                amenities = request.form.getlist(f'amenities_{space_idx}[]')
                open_from = request.form.get(f'open_from_{space_idx}')
                open_to = request.form.get(f'open_to_{space_idx}')
                opening_time = request.form.get(f'opening_time_{space_idx}')
                closing_time = request.form.get(f'closing_time_{space_idx}')
                office_timings = {
                    'open_from': open_from,
                    'open_to': open_to,
                    'opening_time': opening_time,
                    'closing_time': closing_time
                }

                managed_office_data = {}
            else:
                rent_or_own = request.form.get(f'rent_or_own_{space_idx}')
                total_building_area = int(request.form.get(f'total_building_area_{space_idx}') or 0)
                floorplate_area = int(request.form.get(f'floorplate_area_{space_idx}') or 0)
                min_inventory_unit = int(request.form.get(f'min_inventory_unit_{space_idx}') or 0)
                total_rental = int(request.form.get(f'total_rental_{space_idx}') or 0)
                security_deposit = int(request.form.get(f'security_deposit_{space_idx}') or 0)
                lease_term = request.form.get(f'lease_term_{space_idx}')
                space_type = request.form.get(f'space_type_{space_idx}')
                total_floors = int(request.form.get(f'total_floors_{space_idx}') or 0)
                floors_occupied = int(request.form.get(f'floors_occupied_{space_idx}') or 0)
                lockin_period = request.form.get(f'lockin_period_{space_idx}') or 'No Lock-in Period'
                furnishing_level = request.form.get(f'furnishing_level_{space_idx}') or 'N/A'
                seating_capacity = request.form.get(f'seating_capacity_{space_idx}') or 'N/A'
                managed_office_amenities = request.form.getlist(f'managed_amenities_{space_idx}[]')
                floors_offered = request.form.getlist(f'offered_floors_{space_idx}[]')

                amenities = []
                office_timings = {}

                managed_office_data = {
                    'rent_or_own': rent_or_own,
                    'total_building_area': total_building_area,
                    'floorplate_area': floorplate_area,
                    'min_inventory_unit': min_inventory_unit,
                    'total_rental': total_rental,
                    'security_deposit': security_deposit,
                    'lease_term': lease_term,
                    'space_type': space_type,
                    'total_floors': total_floors,
                    'floors_occupied': floors_occupied,
                    'lockin_period': lockin_period,
                    'furnishing_level': furnishing_level,
                    'seating_capacity': seating_capacity,
                    'managed_office_amenities': managed_office_amenities,
                    'floors_offered': floors_offered
                }

            # Recalculate vacancy (backend-safe)
            if workspace_type == "Coworking Spaces":
                    for item in inventory:
                        if item['type'] in ['Dedicated desk', 'Private cabin']:
                            current_vacancy += item.get('count', 0) if 'count' in item else 0

            updated_data = {
                'owner': {'name': name, 'phone': owner_phone, 'email': owner_email},
                'coworking_name': coworking_name,
                'city': city,
                'micromarket': micromarket,
                'address': address,
                'distance': distance_data,
                'current_vacancy': current_vacancy,
                'center_manager': {'name': center_manager_name, 'contact': center_manager_contact},
                'property_images': combined_property_images,
                'workspace_type': workspace_type,
                'hear_from': hear_from,
                'workspace_tool': workspace_tool,
                'notification_preference': notification_preference,
                'space_description': space_description,
                'inventory': inventory,
                'amenities': amenities,
                'office_timings': office_timings,
                'date': datetime.datetime.now(),
                "status": "Pending"
            }

            if managed_office_data:
                updated_data.update(managed_office_data)

            db.fillurdetails.update_one({'_id': ObjectId(space_id)}, {'$set': updated_data})
            send_resubmission_email(name, owner_email, coworking_name, city, micromarket)
            flash("Space updated successfully.")
            return redirect(url_for('operators.inventory'))

        except Exception as e:
            flash(f"An error occurred while updating: {str(e)}")
            return redirect(url_for('operators.inventory'))

    def convert_objectid(obj):
        if isinstance(obj, dict):
            return {k: convert_objectid(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_objectid(i) for i in obj]
        elif isinstance(obj, ObjectId):
            return str(obj)
        return obj

    space = convert_objectid(space)
    return render_template('FillUrDetails.html', space=space, role=session.get('role', 'owner'), context='edit_space')

def send_resubmission_email(owner_name, owner_email, coworking_name, city, micromarket):
    try:
        mail = current_app.extensions['mail']
        now = datetime.datetime.now().strftime('%d %b %Y, %I:%M %p')
        message = Message(
            subject=f"Listing Resubmitted for Review – {coworking_name} | {city}",
            recipients=[
                "findurspace1@gmail.com",
                "thomas@propques.com",
                "buzz@propques.com",
                "listings@findurspace.tech"
            ],
            html=f"""
                <div style="font-family: Arial, sans-serif; line-height: 1.6;">
                    <img src="https://findurspace.blr1.digitaloceanspaces.com/findurspace/image-invert.png" alt="FindUrSpace Logo" width="150">

                    <p>Hi {owner_name},</p>

                    <p>The listing for <strong>{coworking_name}</strong> has been resubmitted by the operator after addressing the previously identified issues.</p>

                    <p><strong>📄 Listing Details:</strong><br>
                    Space Name: {coworking_name}<br>
                    Location: {city}, {micromarket}<br>
                    Resubmitted By: {owner_email}<br>
                    Date of Resubmission: {now}
                    </p>

                    <p>Warm regards,<br><strong>Farhat</strong><br>FindUrSpace</p>
                </div>
            """
        )
        mail.send(message)
        print(f"Resubmission email sent to {owner_email}")
    except Exception as e:
        print(f"Failed to send resubmission email: {e}")

@operators_bp.route('/leads', methods=['GET'])
def leads():
    if 'operator_phone' not in session:
        return redirect(url_for('operators.operators_login'))

    db = current_app.config['db']
    operator_phone = session['operator_phone']
    role = session.get('role', 'owner')  # Default to 'owner' if role is not set

    # Build the query for fetching properties based on role
    if role == 'center_manager':
        # Fetch leads where the center manager's contact is in the center_manager_numbers array
        properties_query = {'center_manager_numbers': operator_phone}
    else:
        # Fetch leads where the operator is an owner
        properties_query = {'operator_numbers': operator_phone}
        
    # Get filter parameters from the query string
    selected_city = request.args.get('city', 'All')
    selected_micromarket = request.args.get('micromarket', 'All')

    # Apply city and micromarket filters for owners
    if role == 'owner':
        if selected_city != 'All':
            properties_query['city'] = selected_city
        if selected_micromarket != 'All':
            properties_query['micromarket'] = selected_micromarket

    # Fetch properties and prepare the leads data
    properties = db.properties.find(properties_query).sort('date', -1)
    
    leads = []
    cities_set = set()
    micromarkets_set = set()

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

            # Collect unique cities and micromarkets (for owner filtering)
            city = property_data.get('city', 'N/A')
            micromarket = property_data.get('micromarket', 'N/A')
            if role == 'owner':
                if city != 'N/A':
                    cities_set.add(city)
                if micromarket != 'N/A' and (selected_city in ['All', city]):
                    micromarkets_set.add(micromarket)

            leads.append({
                'lead_id': str(lead_status['user_id']),
                'property_id': str(lead_status['property_id']),
                'user_name': user.get('name', 'Unknown'),
                'user_company': user.get('company', 'Unknown'),
                'user_email': user.get('email', 'N/A'),
                'user_contact': user.get('contact', 'N/A'),
                'city': city,
                'micromarket': micromarket,
                'date': date,
                'property_seats': property_data.get('seats', 'N/A'),
                'property_budget': property_data.get('budget', 'N/A'),
                'opportunity_status': lead_status.get('opportunity_status', 'open'),
                'opportunity_stage': lead_status.get('opportunity_stage', 'visit done')
            })

    # Convert sets to sorted lists for dropdown options
    cities = sorted(cities_set)
    micromarkets = sorted(micromarkets_set)

    return render_template('operators_leads.html', leads=leads, cities=cities,micromarkets=micromarkets, selected_city=selected_city,selected_micromarket=selected_micromarket,role=role)

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
    
    # Fetch all entries where the owner.phone matches the logged-in user's phone number
    records = db.fillurdetails.find({'owner.phone': operator_phone})

    # Check if any record has uploaded PDFs
    uploaded_pdfs = []
    for record in records:
        if 'uploaded_pdfs' in record and record['uploaded_pdfs']:
            uploaded_pdfs.extend(record['uploaded_pdfs'])

    if uploaded_pdfs:
        # If any uploaded images are found, pass them to the template
        return render_template('show_agreement.html', uploaded_pdfs=uploaded_pdfs)
    else:
        # No uploaded images found, display a fallback message
        return render_template('show_agreement.html', uploaded_pdfs=None)

@operators_bp.route('/calendar/auth')
def calendar_auth():
    email = request.args.get('email')  # ✅ Step 1: Get email from query param
    next_page = request.args.get('next')  # ✅ Get optional redirect
    
    if email:
        session['user_email'] = email
    if next_page:
        session['post_auth_redirect'] = next_page 

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": current_app.config['GOOGLE_CLIENT_ID'],
                "client_secret": current_app.config['GOOGLE_CLIENT_SECRET'],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://127.0.0.1:5000/operators/calendar/callback"],
            }
        },
        scopes=[
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/userinfo.email",
            "openid"
        ],
    )
    flow.redirect_uri = "http://127.0.0.1:5000/operators/calendar/callback"
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true',prompt='consent' )
    session['oauth_state'] = state
    return redirect(authorization_url)


@operators_bp.route('/calendar/callback')
def calendar_callback():
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": current_app.config['GOOGLE_CLIENT_ID'],
                "client_secret": current_app.config['GOOGLE_CLIENT_SECRET'],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://127.0.0.1:5000/operators/calendar/callback"],
            }
        },
        scopes=[
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/userinfo.email",
            "openid"
        ],
        state=session['oauth_state']
    )
    flow.redirect_uri = "http://127.0.0.1:5000/operators/calendar/callback"
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)
    credentials = flow.credentials

    
    # ✅ Use email from session (provided earlier)
    email = session.get('user_email')
    if not email:
        # fallback if session lost
        session_req = requests.Session()
        token_req = session_req.get(
            'https://www.googleapis.com/oauth2/v1/userinfo',
            params={'alt': 'json'},
            headers={'Authorization': f'Bearer {credentials.token}'}
        )
        email = token_req.json().get('email', 'unknown')
        session['user_email'] = email

    # Store in MongoDB
    db = current_app.config['db']
    calendar_data = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes,
        'fetched_at': datetime.datetime.utcnow()
    }
    db.calendar.update_one(
        {'email': email},
        {'$set': calendar_data},
        upsert=True
    )

    # ✅ Update matching fillurdetails records
    db.fillurdetails.update_many(
        {'owner.email': email},
        {'$set': {'google_calendar': calendar_data}}
    )

    # ✅ Conditional redirect based on 'next'
    redirect_target = session.pop('post_auth_redirect', None)
    if redirect_target == 'thank_you':
        return redirect(url_for('core_bp.thank_you'))

    return redirect(url_for('operators.operators_login'))

@operators_bp.route('/calendar/events')
def calendar_events():

    db = current_app.config['db']

    # ✅ Get email from session or hardcode for now (if needed)
    email = session.get('user_email')  # You should ideally store this in session during callback
    if not email:
        return "Email not found in session. Cannot fetch calendar."
    
    # ✅ Fetch credentials from MongoDB
    record = db.calendar.find_one({'email': email})
    if not record:
        return "No calendar credentials found for this user."
    
    from google.oauth2.credentials import Credentials
    creds = Credentials(
        token=record['token'],
        refresh_token=record['refresh_token'],
        token_uri=record['token_uri'],
        client_id=record['client_id'],
        client_secret=record['client_secret'],
        scopes=record['scopes']
    )

    service = build('calendar', 'v3', credentials=creds)

    # ✅ Get upcoming events
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(
        calendarId='primary',
        timeMin=now,
        maxResults=10,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    if not events:
        return "No upcoming events found."
    
    return render_template('calendar_events.html', events=events)




