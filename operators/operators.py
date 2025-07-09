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

    db = current_app.config['db']  # Access MongoDB
    operator_phone = session['operator_phone']

    bookings_cursor = db.bookings.find().sort('created_at', -1)
    bookings = []

    for booking in bookings_cursor:
        booking['_id'] = str(booking['_id'])
        # Fetch user details by user_email
        user = db.users.find_one({'email': booking.get('user_email')})
        booking['user_name'] = user.get('name', 'N/A') if user else 'N/A'
        booking['user_contact'] = user.get('contact_number', 'N/A') if user else 'N/A'
        # Fetch property details if needed (existing logic)
        property_id = booking.get('property_id')
        if property_id:
            property_data = db.fillurdetails.find_one({'_id': ObjectId(property_id)})
            if property_data:
                booking['coworking_name'] = property_data.get('coworking_name', 'N/A')
                booking['city'] = property_data.get('city', 'N/A')
                booking['micromarket'] = property_data.get('micromarket', 'N/A')
                owner = property_data.get('owner', {})
                booking['owner_name'] = owner.get('name', 'N/A')
                booking['owner_phone'] = owner.get('phone', 'N/A')
                booking['owner_email'] = owner.get('email', 'N/A')
                center_manager = property_data.get('center_manager', {})
                booking['center_manager_name'] = center_manager.get('name', 'N/A')
                booking['center_manager_contact'] = center_manager.get('contact', 'N/A')
        bookings.append(booking)

    return render_template('operators_bookings.html', bookings=bookings)

# ✅ Update booking status (Approve/Decline)
@operators_bp.route('/update_booking_status', methods=['POST'])
def update_booking_status():
    db = current_app.config['db']
    data = request.json
    booking_id = data.get('booking_id')
    new_status = data.get('status')

    if not booking_id or not new_status:
        return jsonify({'status': 'error', 'message': 'Missing booking ID or status'})

    # Update the booking_status field in the bookings collection
    result = db.bookings.update_one({'_id': ObjectId(booking_id)}, {'$set': {'booking_status': new_status}})
    
    if result.modified_count > 0:
        # Send confirmation email if status is booking confirmed
        if new_status == 'booking confirmed':
            booking = db.bookings.find_one({'_id': ObjectId(booking_id)})
            user_email = booking.get('user_email')
            if user_email:
                send_booking_confirmation_email(booking, user_email)
        elif new_status == 'booking declined':
            booking = db.bookings.find_one({'_id': ObjectId(booking_id)})
            user_email = booking.get('user_email')
            if user_email:
                send_booking_declined_email(booking, user_email)
        return jsonify({'status': 'success', 'new_status': new_status})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to update status'})
    
# ✅ Process payment (Mark as Paid)
@operators_bp.route('/update_payment_status', methods=['POST'])
def update_payment_status():
    db = current_app.config['db']
    data = request.json
    booking_id = data.get('booking_id')

    if not booking_id:
        return jsonify({'status': 'error', 'message': 'Missing booking ID'})

    # Update payment status in MongoDB
    result = db.booking.update_one({'_id': ObjectId(booking_id)}, {'$set': {'status': 'paid'}})

    if result.modified_count > 0:
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to update payment status'})
    
@operators_bp.route('/visits', methods=['GET'])
def visits():
    if 'operator_phone' not in session:
        return redirect(url_for('operators.operators_login'))

    db = current_app.config['db']
    operator_phone = session['operator_phone']

    # Fetch all visits from the visits collection
    visits_cursor = db.visits.find().sort("created_at", -1)
    visits = []

    for visit in visits_cursor:
        # Convert ObjectId to string
        visit['_id'] = str(visit['_id'])
        visits.append(visit)

    return render_template('operators_visits.html', visits=visits)

# ✅ Update visit status (Approve/Decline)
@operators_bp.route('/update_visit_status', methods=['POST'])
def update_visit_status():
    if 'operator_phone' not in session:
        return jsonify({'status': 'failure', 'message': 'Unauthorized access'}), 401

    db = current_app.config['db']
    data = request.json
    visit_id = data.get('visit_id')
    new_status = data.get('status')

    if not visit_id or not new_status:
        return jsonify({'status': 'error', 'message': 'Missing visit ID or status'})

    # Update visit status in MongoDB
    result = db.visits.update_one({'_id': ObjectId(visit_id)}, {'$set': {'status': new_status}})
    
    if result.modified_count > 0:
        return jsonify({'status': 'success', 'new_status': new_status})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to update status'})


@operators_bp.route('/users', methods=['GET'])
def view_users():
    if 'operator_phone' not in session:
        return jsonify({'status': 'failure', 'message': 'Unauthorized access'}), 401

    db = current_app.config['db']
    users_cursor = db.users.find().sort('created_at', -1)

    users = []
    for user in users_cursor:
        users.append({
            'name': user.get('name', 'N/A'),
            'company': user.get('company', 'N/A'),
            'email': user.get('email', 'N/A'),
            'contact': user.get('contact', 'N/A'),
            'inventory': ", ".join(user.get('inventory', [])),
            'coworking_name': user.get('coworking_name', 'N/A'),
            'location': user.get('location', 'N/A'),
            'created_at': user.get('created_at') or datetime.utcnow()
        })

    return render_template('view_users.html', users=users)






