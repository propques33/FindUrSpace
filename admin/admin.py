from flask import Blueprint, jsonify, render_template, request, redirect, url_for, session, send_file, current_app, flash
import threading
from bson import ObjectId
from io import BytesIO
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from core.email_handler_listing import send_email_and_whatsapp_with_pdf
from core.email_handler import send_email_and_whatsapp_with_pdf1
from datetime import datetime
from bson.errors import InvalidId
import boto3
from werkzeug.utils import secure_filename
import os
from flask_mail import Message
from bson.objectid import ObjectId
from .image_upload1 import process_and_upload_pdf

# Blueprint definition
admin_bp = Blueprint('admin', __name__, url_prefix='/admin', template_folder='templates')

# Admin Credentials
admin_credentials = {
    "project.propques@gmail.com": "Prop@1122",
    "buzz@propques.com": "Prop@112233",
    "listing@gmail.com": "Prop@9044",
    "client@gmail.com": "client123"  # ✅ Add client 
}

# Helper function to send the email and WhatsApp with app context
def send_email_and_whatsapp_background(app, email, mobile, selected_properties):
    with app.app_context():  # Set up the app context
        try:
            success, error = send_email_and_whatsapp_with_pdf(email, None, mobile, selected_properties)
            if success:
                print("Email and WhatsApp sent successfully.")
            else:
                print(f"Failed to send: {error}")
        except Exception as e:
            print(f"Error in sending email and WhatsApp: {e}")

# Helper function to send the email and WhatsApp with app context
def send_email_and_whatsapp_background1(app, email, mobile, selected_properties):
    with app.app_context():  # Set up the app context
        try:
            success, error = send_email_and_whatsapp_with_pdf1(email, None, mobile, selected_properties)
            if success:
                print("Email and WhatsApp sent successfully.")
            else:
                print(f"Failed to send: {error}")
        except Exception as e:
            print(f"Error in sending email and WhatsApp: {e}")

# Add your routes here
@admin_bp.route('/')
def admin_home():
    from main import db  # Lazy import to avoid circular dependency
    return "Admin Home"


@admin_bp.route('/send_selected_properties', methods=['POST'])
def send_selected_properties():
    data = request.get_json()
    email = data.get('email')
    mobile = data.get('mobile')
    selected_property_ids = data.get('selectedProperties')

    if not selected_property_ids or not email:
        return jsonify({'status': 'error', 'message': 'Missing required information'})

    db = current_app.config['db']

    try:
        # Fetch from coworking_spaces
        properties = list(db.coworking_spaces.find({
            '_id': {'$in': [ObjectId(id) for id in selected_property_ids]}
        }))

        # Transform the data to match live_inventory format
        transformed_properties = []
        for p in properties:
            transformed_p = {
                'coworking_name': p.get('name'),  # Map 'name' to 'coworking_name'
                'city': p.get('city'),
                'micromarket': p.get('micromarket'),
                'details': p.get('details'),
                'layout_images': [p.get('img1', ''), p.get('img2', '')] if p.get('img1') else []
            }
            transformed_properties.append(transformed_p)

        # Send email with transformed data
        app = current_app._get_current_object()
        email_thread = threading.Thread(
            target=send_email_and_whatsapp_background, 
            args=(app, email, mobile, transformed_properties)
        )
        email_thread.start()

        return jsonify({'status': 'success', 'message': 'Email sent successfully'})

    except Exception as e:
        print(f"Error in send_selected_properties: {e}")
        return jsonify({'status': 'error', 'message': f'An error occurred: {str(e)}'}), 500

@admin_bp.route('/send_selected_properties_live', methods=['POST'])
def send_selected_properties_live():
    data = request.get_json()
    email = data.get('email')
    mobile = data.get('mobile')
    selected_property_ids = data.get('selectedProperties')

    if not selected_property_ids or not email:
        return jsonify({'status': 'error', 'message': 'Missing required information'})

    db = current_app.config['db']

    try:
        # Validate ObjectIds
        valid_ids = []
        for id in selected_property_ids:
            try:
                valid_ids.append(ObjectId(id))
            except InvalidId:
                print(f"Invalid ObjectId: {id}")
        
        if not valid_ids:
            return jsonify({'status': 'error', 'message': 'No valid property IDs provided.'})
        
         # Fetch properties
        properties = list(db.fillurdetails.find({'_id': {'$in': valid_ids}}))
        transformed_properties = [{
            'coworking_name': p.get('coworking_name', 'Unknown'),
            'city': p.get('city', 'Unknown'),
            'micromarket': p.get('micromarket', 'Unknown'),
            'inventory': p.get('inventory', []),
            'layout_images': p.get('layout_images', []),
            'has_amenities': bool(p.get('amenities'))
        } for p in properties]

        print(f"Email: {email}, Mobile: {mobile}, Selected Properties: {selected_property_ids}")


        # Send email with transformed data
        app = current_app._get_current_object()
        email_thread = threading.Thread(
            target=send_email_and_whatsapp_background1, 
            args=(app, email, mobile, transformed_properties)
        )
        email_thread.start()

        return jsonify({'status': 'success', 'message': 'Email sent successfully'})

    except Exception as e:
        print(f"Error in send_selected_properties: {e}")
        return jsonify({'status': 'error', 'message': f'An error occurred: {str(e)}'}), 500

@admin_bp.route('/greeting')
def greeting():
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))
    return render_template('greeting.html')

# Admin Login Route
@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if 'admin' in session:
        return redirect(url_for('admin.leads_dashboard'))  # Redirect to Leads Dashboard if already logged in

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        if email in admin_credentials and admin_credentials[email] == password:
            session['admin'] = email
            if email == 'listing@gmail.com':
                session['role'] = 'listing'
            elif email == 'client@gmail.com':
                session['role'] = 'client'  # ✅ Set client role
            else:
                session['role'] = 'full'
            return redirect(url_for('admin.leads_dashboard'))
        else:
            return render_template('admin_login.html', error='Invalid login credentials. Please try again.')

    return render_template('admin_login.html')


# Admin Dashboard Route with Two Cards (Changed to Leads Dashboard)
@admin_bp.route('/dashboard')
def admin_dashboard():
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))

    return redirect(url_for('admin.leads_dashboard'))  # Redirect to leads_dashboard


# Admin Logout Route
@admin_bp.route('/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin.admin_login'))

# Route to view database collections as cards
@admin_bp.route('/view_collections')
def view_database_collections():
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))

    db = current_app.config['db']  # Access the db instance from the current app context
    collections = db.list_collection_names()  # Fetch list of collections from MongoDB

    return render_template('view_collections.html', collections=collections)

# Route to view documents in a specific collection
@admin_bp.route('/view_collection/<collection_name>')
def view_collection(collection_name):
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))

    db = current_app.config['db']  # Access the database here
    collection = db[collection_name].find()
    documents = list(collection)

    for document in documents:
        # Convert ObjectId to string for display purposes
        document['_id'] = str(document['_id'])

        if 'user_id' in document:
            document['user_id'] = str(document['user_id'])  # Convert user_id if it exists

        # Convert Binary data in pdf_files if exists (For fillurdetails)
        if 'pdf_files' in document:
            for file in document['pdf_files']:
                file['_id'] = str(file['_id']) if '_id' in file else None  # Convert ObjectId if present
                # Add a download link for the file
                file['download_link'] = url_for('admin.download_file', collection_name=collection_name, document_id=document['_id'], filename=file['filename'])
                # Remove the binary data before sending to the template
                del file['data']

        # Convert floor IDs to strings and remove binary data
        if 'floors' in document:
            for floor in document['floors']:
                floor['_id'] = str(floor.get('_id', ''))
                # Optionally remove binary data before sending to the template
                # del floor['image_data']

    return render_template('view_collection.html', collection_name=collection_name, documents=documents)

# Delete Document Route
@admin_bp.route('/delete_document/<collection_name>/<document_id>', methods=['POST'])
def delete_document(collection_name, document_id):
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))

    db = current_app.config['db']  # Access the database here
    db[collection_name].delete_one({'_id': ObjectId(document_id)})

    return redirect(url_for('admin.view_collection', collection_name=collection_name))


@admin_bp.route('/leads', methods=['GET', 'POST'])
def view_leads():
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))

    db = current_app.config['db']

    properties = db.properties.find().sort('date', -1)
    leads = []
    cities_set = set()
    micromarkets_set = set()

    for property_data in properties:
        user = db.users.find_one({'_id': property_data['user_id']})
        if user:
            lead_status = db.leads_status.find_one({'user_id': property_data['user_id'], 'property_id': property_data['_id']})
            
            if not lead_status:
                lead_status = {
                    'user_id': property_data['user_id'],
                    'property_id': property_data['_id'],
                    'opportunity_status': 'open',
                    'opportunity_stage': 'visit done',
                    'notes': []  # Initialize as an empty list
                }
                db.leads_status.insert_one(lead_status)

            # Ensure 'notes' is a list
            if isinstance(lead_status.get('notes', []), str):
                lead_status['notes'] = [{"text": lead_status['notes'], "timestamp": "N/A"}]
                db.leads_status.update_one(
                    {'user_id': property_data['user_id'], 'property_id': property_data['_id']},
                    {'$set': {'notes': lead_status['notes']}}
                )
            elif not isinstance(lead_status.get('notes', []), list):
                lead_status['notes'] = []
                db.leads_status.update_one(
                    {'user_id': property_data['user_id'], 'property_id': property_data['_id']},
                    {'$set': {'notes': lead_status['notes']}}
                )

            # Retrieve 'city' and 'micromarket' instead of 'location' and 'area'
            city = property_data.get('city', 'N/A')
            micromarket = property_data.get('micromarket', 'N/A')
            date_str = property_data.get('date', 'N/A')

            # Try to convert date string to a datetime object
            try:
                if isinstance(date_str, str):
                    date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S.%f')  # Adjusted format to include time and microseconds
                else:
                    date = date_str  # It's already a datetime object
            except Exception as e:
                print(f"Error converting date: {e}")
                date = 'N/A'

            # Collect unique cities and micromarkets for dropdown options (optional)
            if city != 'N/A':
                cities_set.add(city)
            if micromarket != 'N/A':
                micromarkets_set.add(micromarket)

            leads.append({
                'lead_id': str(lead_status['user_id']),
                'property_id': str(lead_status['property_id']),
                'user_name': user.get('name', 'Unknown'),
                'user_company': user.get('company', 'Unknown'),
                'user_email': user.get('email', 'N/A'),
                'user_contact': user.get('contact', 'N/A'),
                'city': city,  # Updated field
                'micromarket': micromarket,  # Added field
                'date': date,
                'property_seats': property_data.get('seats', 'N/A'),
                'property_budget': property_data.get('budget', 'N/A'),
                'opportunity_status': lead_status.get('opportunity_status', 'open'),
                'opportunity_stage': lead_status.get('opportunity_stage', 'visit done'),
                'notes': lead_status.get('notes', [])
            })

    # Convert sets to sorted lists for dropdowns (if needed)
    cities = sorted(list(cities_set))
    micromarkets = sorted(list(micromarkets_set))

    return render_template('view_leads.html', leads=leads, cities=cities, micromarkets=micromarkets)


# @admin_bp.route('/leads_dashboard')
# def leads_dashboard():
#     if 'admin' not in session:
#         return redirect(url_for('admin.admin_login'))

#     db = current_app.config['db']
#     is_listing_user = session.get('admin') == 'listing@gmail.com'

#     # --- Get and parse dates ---
#     start_date_str = request.args.get('start_date')
#     end_date_str = request.args.get('end_date')

#     lead_filter = {}
#     property_filter = {}

#     if start_date_str and end_date_str:
#         try:
#             start = datetime.strptime(start_date_str, '%Y-%m-%d')
#             end = datetime.strptime(end_date_str, '%Y-%m-%d')
#             # Filter leads and inventory using the 'date' field
#             lead_filter['date'] = {'$gte': start, '$lte': end}
#             property_filter['date'] = {'$gte': start, '$lte': end}
#         except Exception as e:
#             print("Date filter error:", e)

#     # --- Fetch Live Inventory Count ---
#     live_inventory_count = db.fillurdetails.count_documents(property_filter)

#     # Fetch from the correct collection
#     leads_data = db.properties.find(lead_filter)
#     total_leads = db.properties.count_documents(lead_filter)
#     live_inventory_count = db.fillurdetails.count_documents(property_filter)
#     # Reset counts
#     status_counts = {'open': 0, 'closed': 0, 'won': 0}
#     stage_counts = {k: 0 for k in ['qualified', 'follow-up', 'visit done', 'negotiation', 'won', 'lost', 'unqualified']}

#     for lead in leads_data:
#         # Default logic: assume all are open unless marked otherwise
#         status = lead.get('opportunity_status', 'open').lower()
#         status_counts[status] = status_counts.get(status, 0) + 1

#         stage = lead.get('opportunity_stage', 'visit done').lower()
#         stage_counts[stage] = stage_counts.get(stage, 0) + 1

#     # --- City-wise Inventory ---
#     city_inventory = db.fillurdetails.aggregate([
#         {"$match": property_filter},
#         {"$group": {"_id": {"$toUpper": "$city"}, "count": {"$sum": 1}}}
#     ])

#     city_name_mapping = {"BANGALORE": "Bengaluru", "GURGAON": "Gurugram"}
#     city_inventory_data = list(city_inventory)
#     city_inventory_normalized = []

#     for item in city_inventory_data:
#         city = item['_id'].title()
#         city = city_name_mapping.get(city.upper(), city)
#         match = next((i for i in city_inventory_normalized if i['_id'] == city), None)
#         if match:
#             match['count'] += item['count']
#         else:
#             city_inventory_normalized.append({'_id': city, 'count': item['count']})

#     # --- KPI Cards ---
#     kpis = [
#         {"label": "Total Leads", "value": total_leads, "color": "#17becf"},
#         {"label": "Open Leads", "value": status_counts.get('open', 0), "color": "#1f77b4"},
#         {"label": "Closed Leads", "value": status_counts.get('closed', 0), "color": "#ff7f0e"},
#         {"label": "Won Leads", "value": status_counts.get('won', 0), "color": "#2ca02c"},
#         {"label": "Live Inventory", "value": live_inventory_count, "color": "#e377c2"}
#     ]

#     kpi_figures = []
#     for kpi in kpis:
#         fig = go.Figure(go.Indicator(
#             mode="number",
#             value=kpi['value'],
#             title={"text": kpi['label']},
#             number={'font': {'size': 40, 'color': kpi['color']}}
#         ))
#         fig.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=200)
#         kpi_figures.append(fig.to_html(full_html=False))

#     # --- Bar Chart: Stages ---
#     stage_bar_fig = go.Figure(go.Bar(
#         x=list(stage_counts.keys()),
#         y=list(stage_counts.values()),
#         marker_color='rgb(55, 83, 109)'
#     ))
#     stage_bar_fig.update_layout(
#         title='Opportunity Stage Distribution',
#         xaxis_title='Stage',
#         yaxis_title='Count',
#         width=1200,
#         height=450
#     )

#     # --- Bar Chart: City Inventory ---
#     city_names = [x['_id'] for x in city_inventory_normalized]
#     city_counts = [x['count'] for x in city_inventory_normalized]
#     city_bar_fig = go.Figure(go.Bar(
#         x=city_names,
#         y=city_counts,
#         marker_color='rgb(26, 118, 255)'
#     ))
#     city_bar_fig.update_layout(
#         title='Live Inventory by City',
#         xaxis_title='City',
#         yaxis_title='Count',
#         width=1200,
#         height=450
#     )

#     return render_template(
#         'leads_dashboard.html',
#         kpi_figures=kpi_figures,
#         stage_bar_fig=stage_bar_fig.to_html(full_html=False),
#         city_bar_fig=city_bar_fig.to_html(full_html=False)
#     )

@admin_bp.route('/leads_dashboard')
def leads_dashboard():
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))

    db = current_app.config['db']
    is_listing_user = session.get('admin') == 'listing@gmail.com'

    # --- Get and parse dates ---
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    lead_filter = {}
    property_filter = {}

    if start_date_str and end_date_str:
        try:
            start = datetime.strptime(start_date_str, '%Y-%m-%d')
            end = datetime.strptime(end_date_str, '%Y-%m-%d')
            lead_filter['date'] = {'$gte': start, '$lte': end}
            property_filter['date'] = {'$gte': start, '$lte': end}
        except Exception as e:
            print("Date filter error:", e)

    # --- Fetch Live Inventory Count ---
    live_inventory_count = db.fillurdetails.count_documents(property_filter)

    # --- Prepare KPI Cards ---
    kpis = []

    if not is_listing_user:
        leads_data = db.properties.find(lead_filter)
        total_leads = db.properties.count_documents(lead_filter)
        status_counts = {'open': 0, 'closed': 0, 'won': 0}
        stage_counts = {k: 0 for k in ['qualified', 'follow-up', 'visit done', 'negotiation', 'won', 'lost', 'unqualified']}

        for lead in leads_data:
            status = lead.get('opportunity_status', 'open').lower()
            stage = lead.get('opportunity_stage', 'visit done').lower()
            status_counts[status] = status_counts.get(status, 0) + 1
            stage_counts[stage] = stage_counts.get(stage, 0) + 1

        kpis.extend([
            {"label": "Total Leads", "value": total_leads, "color": "#17becf"},
            {"label": "Open Leads", "value": status_counts.get('open', 0), "color": "#1f77b4"},
            {"label": "Closed Leads", "value": status_counts.get('closed', 0), "color": "#ff7f0e"},
            {"label": "Won Leads", "value": status_counts.get('won', 0), "color": "#2ca02c"},
        ])

    # Add inventory KPI (common to all)
    kpis.append({"label": "Live Inventory", "value": live_inventory_count, "color": "#e377c2"})

    # Generate KPI figures
    kpi_figures = []
    for kpi in kpis:
        fig = go.Figure(go.Indicator(
            mode="number",
            value=kpi['value'],
            title={"text": kpi['label']},
            number={'font': {'size': 40, 'color': kpi['color']}}
        ))
        fig.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=200)
        kpi_figures.append(fig.to_html(full_html=False))

    # --- Stage Chart (only for full admins) ---
    if not is_listing_user:
        stage_bar_fig = go.Figure(go.Bar(
            x=list(stage_counts.keys()),
            y=list(stage_counts.values()),
            marker_color='rgb(55, 83, 109)'
        ))
        stage_bar_fig.update_layout(
            title='Opportunity Stage Distribution',
            xaxis_title='Stage',
            yaxis_title='Count',
            width=1200,
            height=450
        )
        stage_chart = stage_bar_fig.to_html(full_html=False)
    else:
        stage_chart = ""  # Hide for listing user

    # --- City Inventory Chart (visible to all) ---
    city_inventory = db.fillurdetails.aggregate([
        {"$match": property_filter},
        {"$group": {"_id": {"$toUpper": "$city"}, "count": {"$sum": 1}}}
    ])

    city_name_mapping = {"BANGALORE": "Bengaluru", "GURGAON": "Gurugram"}
    city_inventory_data = list(city_inventory)
    city_inventory_normalized = []

    for item in city_inventory_data:
        city = item['_id'].title()
        city = city_name_mapping.get(city.upper(), city)
        match = next((i for i in city_inventory_normalized if i['_id'] == city), None)
        if match:
            match['count'] += item['count']
        else:
            city_inventory_normalized.append({'_id': city, 'count': item['count']})

    city_names = [x['_id'] for x in city_inventory_normalized]
    city_counts = [x['count'] for x in city_inventory_normalized]
    city_bar_fig = go.Figure(go.Bar(
        x=city_names,
        y=city_counts,
        marker_color='rgb(26, 118, 255)'
    ))
    city_bar_fig.update_layout(
        title='Live Inventory by City',
        xaxis_title='City',
        yaxis_title='Count',
        width=1200,
        height=450
    )

    return render_template(
        'leads_dashboard.html',
        kpi_figures=kpi_figures,
        stage_bar_fig=stage_chart,
        city_bar_fig=city_bar_fig.to_html(full_html=False)
    )



@admin_bp.route('/upload_file', methods=['POST'])
def upload_file():
    if 'admin' not in session:
        return jsonify({'status': 'error', 'message': 'Not authorized'}), 403

    file = request.files.get('file')
    property_id = request.form.get('property_id')

    if not file or not property_id:
        return jsonify({'status': 'error', 'message': 'File and Property ID are required'}), 400

    # Validate file type (PDF)
    if file.content_type != 'application/pdf':
        return jsonify({'status': 'error', 'message': 'Only PDF files are allowed'}), 400

    # Upload to DigitalOcean Spaces
    try:
        # Use the process_and_upload_image function
        from .image_upload1 import process_and_upload_pdf 
        uploaded_url = process_and_upload_pdf(file)
        if not uploaded_url:
            return jsonify({'status': 'error', 'message': 'File upload failed'}), 500
        
        # Ensure the URL includes 'findurspace/'
        if 'findurspace/' not in uploaded_url:
            uploaded_url = f"https://findurspace.blr1.digitaloceanspaces.com/findurspace/{uploaded_url.split('/')[-1]}"

        # Update MongoDB with the uploaded image URL
        db = current_app.config['db']
        result = db.fillurdetails.update_one(
            {'_id': ObjectId(property_id)},  # Match by property ID
            {'$push': {'uploaded_pdfs': uploaded_url}}  # Append the URL to the 'uploaded_images' field
        )

        # Check the result of the MongoDB update
        if result.modified_count > 0:
            return jsonify({'status': 'success', 'file_url': uploaded_url}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Failed to update the database'}), 500

    except Exception as e:
        print(f"Error uploading file: {e}")
        return jsonify({'status': 'error', 'message': f'File upload failed: {str(e)}'}), 500
    
# Fetching listings
@admin_bp.route('/listings', methods=['GET'])
def listings():
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))

    db = current_app.config['db']
    coworking_spaces = db.coworking_spaces

    # Get filter parameters from the request
    city = request.args.get('city', None)
    micromarket = request.args.get('micromarket', None)
    price = request.args.get('price', None)

    # Build query filters
    filters = {}
    if city:
        filters['city'] = city
    if micromarket:
        filters['micromarket'] = micromarket
    if price:
        try:
            filters['price'] = {'$lte': int(price)}  # Convert to integer safely
        except ValueError:
            pass  # Handle invalid price input gracefully

    # Fetch data with pagination
    try:
        page = int(request.args.get('page', 1))  # Get current page, default is 1
    except ValueError:
        page = 1  # Fallback to page 1 if the conversion fails
    
    per_page = 10  # Number of records per page
    skip = (page - 1) * per_page

    total_records = coworking_spaces.count_documents(filters)
    coworking_list = coworking_spaces.find(filters).skip(skip).limit(per_page)

    # Fetch distinct cities for the filter form
    cities = coworking_spaces.distinct('city')

    # Fetch micromarkets based on the selected city for dynamic micromarket filtering
    micromarkets = []
    if city:
        micromarkets = coworking_spaces.distinct('micromarket', {'city': city})

    return render_template('listings.html', 
                           coworking_list=coworking_list, 
                           cities=cities, 
                           micromarkets=micromarkets, 
                           city=city, 
                           micromarket=micromarket, 
                           price=price, 
                           page=page, 
                           total_records=total_records, 
                           per_page=per_page)

# Fetch Micromarkets based on the City
@admin_bp.route('/get_micromarkets/<city>', methods=['GET'])
def get_micromarkets(city):
    if 'admin' not in session:
        return jsonify({'status': 'error', 'message': 'Not authorized'}), 403

    db = current_app.config['db']

    # Find micromarkets for the selected city
    micromarkets = db.coworking_spaces.distinct("micromarket", {"city": city})

    if not micromarkets:
        return jsonify({'status': 'error', 'message': 'No micromarkets found for the city'}), 404

    return jsonify(micromarkets)

# Fetch Prices based on City and Micromarket
@admin_bp.route('/get_prices/<city>/<micromarket>', methods=['GET'])
def get_prices(city, micromarket):
    if 'admin' not in session:
        return jsonify({'status': 'error', 'message': 'Not authorized'}), 403

    db = current_app.config['db']

    # If micromarket is empty or not provided, return an error
    if not micromarket:
        return jsonify({'status': 'error', 'message': 'Micromarket is required'}), 400

    # Find prices for the selected city and micromarket
    prices = db.coworking_spaces.distinct("price", {"city": city, "micromarket": micromarket})

    if not prices:
        return jsonify({'status': 'error', 'message': 'No prices found'}), 404

    return jsonify(prices)


# Route to dynamically fetch filtered listings without refreshing the whole page
@admin_bp.route('/fetch_listings', methods=['GET'])
def fetch_listings():
    db = current_app.config['db']
    city = request.args.get('city', None)
    micromarket = request.args.get('micromarket', None)
    price = request.args.get('price', None)
    page = int(request.args.get('page', 1))
    per_page = 10
    skip = (page - 1) * per_page

    filters = {}
    if city:
        filters['city'] = city
    if micromarket:
        filters['micromarket'] = micromarket
    if price:
        try:
            filters['price'] = {'$lte': int(price)}
        except ValueError:
            pass

    coworking_spaces = db.coworking_spaces.find(filters).skip(skip).limit(per_page)
    total_records = db.coworking_spaces.count_documents(filters)
    coworking_list = [{
        '_id': str(space['_id']),
        'name': space['name'],
        'city': space['city'],
        'micromarket': space['micromarket'],
        'price': space['price'],
        'contact': space.get('contact', 'N/A')
    } for space in coworking_spaces]

    # Convert the documents to JSON format and include _id
    result_list = [{
        '_id': str(space['_id']),  # Convert ObjectId to string
        'name': space['name'],
        'city': space['city'],
        'micromarket': space['micromarket'],
        'price': space['price'],
        'contact': space.get('contact', 'N/A'), 
        'seats': space.get('seats', 'N/A'),
        'coworking_list': coworking_list,
        'page': page,
        'per_page': per_page,
        'total_records': total_records
    } for space in coworking_list]

    return jsonify({
        'coworking_list': result_list,
        'page': int(request.args.get('page', 1)),
        'per_page': 10,
        'total_records': db.coworking_spaces.count_documents(filters)
    })

# ---------------------------------------------------------Lead Management------------------------------------------------------------------------------------
@admin_bp.route('/leads_management', methods=['GET'])
def leads_management():
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))

    db = current_app.config['db']
    
    # Fetch all leads and their current opportunity stages
    leads = list(db.leads_status.find())
    
    # Organize leads by stages (use lowercase keys to match the DB)
    stages = {
        'visit done': [],
        'qualified': [],
        'negotiation': [],
        'won': [],
        'lost': [],
        'unqualified': [],
        'follow-up': []
    }

    for lead in leads:
        # Normalize opportunity stage to lowercase to match dictionary keys
        stage = lead.get('opportunity_stage', '').lower()
        user = db.users.find_one({'_id': lead['user_id']})
        
        # Handle cases where user might not be found
        if not user:
            continue  # Skip this lead if user data is missing

        # Ensure 'notes' is a list
        notes = lead.get('notes', [])
        if isinstance(notes, str):
            notes = [{"text": notes, "timestamp": "N/A"}]
            db.leads_status.update_one(
                {'_id': lead['_id']},
                {'$set': {'notes': notes}}
            )
        elif not isinstance(notes, list):
            notes = []
            db.leads_status.update_one(
                {'_id': lead['_id']},
                {'$set': {'notes': notes}}
            )

        lead_data = {
            'lead_id': str(lead['user_id']),
            'property_id': str(lead['property_id']),
            'user_name': user.get('name', 'Unknown'),
            'user_company': user.get('company', 'Unknown'),
            'user_email': user.get('email', 'N/A'),
            'user_contact': user.get('contact', 'N/A'),
            'opportunity_stage': lead.get('opportunity_stage', 'visit done'),
            'notes': notes
        }

        # Append lead to the appropriate stage in lowercase
        if stage in stages:
            stages[stage].append(lead_data)
        else:
            print(f"Stage '{stage}' not found in stages dictionary")  # Debugging

    return render_template('leads_management.html', stages=stages)

@admin_bp.route('/update_lead_stage', methods=['POST'])
def update_lead_stage():
    if 'admin' not in session:
        return jsonify({'status': 'error', 'message': 'Not authorized'}), 403

    data = request.get_json()
    lead_id = data.get('lead_id')
    property_id=data.get('property_id')
    new_stage = data.get('new_stage')

    if not lead_id or not new_stage:
        return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

    db = current_app.config['db']
    
    # Update the lead's opportunity_stage in the database
    result = db.leads_status.update_one(
        {'user_id': ObjectId(lead_id), 'property_id': ObjectId(property_id)},
        {'$set': {'opportunity_stage': new_stage}}
    )

    if result.modified_count > 0:
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error', 'message': 'Lead not updated'}), 400

@admin_bp.route('/get_lead/<lead_id>', methods=['GET'])
def get_lead(lead_id):
    if 'admin' not in session:
        return jsonify({'status': 'error', 'message': 'Not authorized'}), 403

    db = current_app.config['db']
    
    lead = db.leads_status.find_one({'user_id': ObjectId(lead_id)})
    if lead:
        user = db.users.find_one({'_id': lead['user_id']})
        if not user:
            return jsonify({'status': 'error', 'message': 'User not found'}), 404

        # Ensure 'notes' is a list
        notes = lead.get('notes', [])
        if isinstance(notes, str):
            notes = [{"text": notes, "timestamp": "N/A"}]
            db.leads_status.update_one(
                {'_id': lead['_id']},
                {'$set': {'notes': notes}}
            )
        elif not isinstance(notes, list):
            notes = []
            db.leads_status.update_one(
                {'_id': lead['_id']},
                {'$set': {'notes': notes}}
            )

        return jsonify({
            'lead_id': str(lead['user_id']),
            'property_id': str(lead['property_id']),
            'user_name': user.get('name', 'Unknown'),
            'user_company': user.get('company', 'Unknown'),
            'user_email': user.get('email', 'N/A'),
            'user_contact': user.get('contact', 'N/A'),
            'opportunity_stage': lead.get('opportunity_stage', 'Visit Done'),
            'notes': notes
        })
    else:
        return jsonify({'status': 'error', 'message': 'Lead not found'}), 404


# ---------------------------------------------------------Lead Management Enhancements------------------------------------------------------------------------------------

@admin_bp.route('/add_lead_note', methods=['POST'])
def add_lead_note():
    if 'admin' not in session:
        return jsonify({'status': 'error', 'message': 'Not authorized'}), 403

    data = request.get_json()
    lead_id = data.get('lead_id')
    property_id = data.get('property_id')
    note_text = data.get('note')
    # Generate timestamp in desired format
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")  # UTC time

    if not lead_id or not property_id or not note_text :
        return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

    db = current_app.config['db']

    # Construct the note object
    note = {
        'text': note_text,
        'timestamp': timestamp  # Store in 'YYYY-MM-DD HH:MM:SS' format
    }

    # Ensure 'notes' is a list before pushing
    lead = db.leads_status.find_one({'user_id': ObjectId(lead_id), 'property_id': ObjectId(property_id)})
    if not lead:
        return jsonify({'status': 'error', 'message': 'Lead not found'}), 404

    if isinstance(lead.get('notes'), str):
        # Convert 'notes' to a list containing the existing string note
        db.leads_status.update_one(
            {'user_id': ObjectId(lead_id), 'property_id': ObjectId(property_id)},
            {'$set': {'notes': [{'text': lead['notes'], 'timestamp': 'N/A'}]}}
        )
    
    elif not isinstance(lead.get('notes'), list):
        # If 'notes' is neither string nor list, initialize it as an empty list
        db.leads_status.update_one(
            {'user_id': ObjectId(lead_id), 'property_id': ObjectId(property_id)},
            {'$set': {'notes': []}}
        )

    # Append the new note to the notes array
    result = db.leads_status.update_one(
        {'user_id': ObjectId(lead_id), 'property_id': ObjectId(property_id)},
        {'$push': {'notes': note}}
    )

    if result.modified_count > 0:
        return jsonify({'status': 'success', 'message': 'Note added successfully'}), 200
    else:
        return jsonify({'status': 'error', 'message': 'Failed to add note'}), 500

@admin_bp.route('/get_lead_notes', methods=['GET'])
def get_lead_notes():
    if 'admin' not in session:
        return jsonify({'status': 'error', 'message': 'Not authorized'}), 403

    lead_id = request.args.get('lead_id')
    property_id = request.args.get('property_id')

    if not lead_id or not property_id:
        return jsonify({'status': 'error', 'message': 'Lead ID and Property ID are required'}), 400

    db = current_app.config['db']

    lead = db.leads_status.find_one({'user_id': ObjectId(lead_id), 'property_id': ObjectId(property_id)}, {'notes': 1, '_id': 0})

    if lead:
        notes = lead.get('notes', [])
        if isinstance(notes, str):
            # Convert 'notes' to a list containing the existing string note
            notes = [{"text": notes, "timestamp": "N/A"}]
            db.leads_status.update_one(
                {'user_id': ObjectId(lead_id)},
                {'$set': {'notes': notes}}
            )
        elif not isinstance(notes, list):
            notes = []
            db.leads_status.update_one(
                {'user_id': ObjectId(lead_id)},
                {'$set': {'notes': notes}}
            )

        # Function to parse timestamp with multiple formats
        def parse_timestamp(ts):
            if ts == "N/A":
                return datetime.datetime.min
            for fmt in ("%Y-%m-%d %H:%M:%S", "%m/%d/%Y, %H:%M:%S"):
                try:
                    return datetime.datetime.strptime(ts, fmt)
                except ValueError:
                    continue
            # If all formats fail, return minimum datetime
            return datetime.datetime.min

        # Sort notes by timestamp descending (latest first)
        try:
            sorted_notes = sorted(
                notes, 
                key=lambda x: parse_timestamp(x['timestamp']), 
                reverse=True
            )
        except Exception as e:
            # If sorting fails due to unexpected issues, return unsorted notes
            print(f"Error sorting notes: {e}")
            sorted_notes = notes

        return jsonify({'status': 'success', 'notes': sorted_notes}), 200
    else:
        return jsonify({'status': 'error', 'message': 'Lead not found'}), 404


# --------------------------------LIVE INVENTORY --------------------------------------------------------------------------------------------
@admin_bp.route('/live_inventory', methods=['GET'])
def live_inventory():
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))
    
    db = current_app.config['db']
    # Fetch all city names and normalize to lowercase
    cities = db.fillurdetails.distinct('city')
    micromarkets = db.fillurdetails.distinct('micromarket')
    
    return render_template('live_inventory.html', cities=cities, micromarkets=micromarkets, role=session.get('role'))

@admin_bp.route('/update_status', methods=['POST'])
def update_status():
    if 'admin' not in session:
        return jsonify({'status': 'unauthorized'}), 403

    data = request.get_json()
    property_id = data.get('property_id')
    new_status = data.get('status')
    message = data.get('message', '')  # optional

    db = current_app.config['db']
    space = db.fillurdetails.find_one({'_id': ObjectId(property_id)})

    if not space:
        return jsonify({'status': 'failed', 'message': 'Property not found'})
    
    update_result = db.fillurdetails.update_one(
        {'_id': ObjectId(property_id)},
        {'$set': {'status': new_status, 'admin_feedback': message}}
    )


    # ✅ Send email if status is Approved
    if update_result.modified_count == 1 and new_status == "Approved":
        try:
            email = space.get('owner', {}).get('email')
            coworking_name = space.get('coworking_name', 'Your Space')
            operator_name = space.get('owner', {}).get('name', 'Partner')
            city = space.get('city', 'your city')

            # Generate panel link (customize as needed)
            panel_link = "https://findurspace.tech/operators/login"

            # Compose email content
            subject = "Congrats - Your Listing Is Now Live on FindUrSpace"
            body = f"""
Hi {operator_name},

Great news! Your coworking space listing – {coworking_name} – has been successfully reviewed and approved. It is now live on the platform and visible to users actively searching for workspaces in {city}.

🔐 Login to Manage: {panel_link}

Warm regards,  
Farhat  
FindUrSpace
"""

            recipients = list({email})  # remove duplicates
            for email in recipients:
                if email:
                    send_admin_approval_email(operator_name, email, coworking_name)

        except Exception as e:
            print(f"Error sending approval email: {e}")

        return jsonify({'status': 'success'})
    
    # ✅ Send email if status is Edit Required
    elif update_result.modified_count == 1 and new_status == "Edit Required":
        try:
            email = space.get('owner', {}).get('email')
            coworking_name = space.get('coworking_name', 'Your Space')
            operator_name = space.get('owner', {}).get('name', 'Partner')

            for email in [email]:
                if email:
                    send_edit_required_email(operator_name, email, coworking_name, message)
        except Exception as e:
            print(f"Error sending edit-required email: {e}")

        return jsonify({'status': 'success'})
    return jsonify({'status': 'failed'})

def send_edit_required_email(owner_name, owner_email, coworking_name, feedback_message):
    try:
        mail = current_app.extensions['mail']
        message = Message(
            subject="Action Required: Your Listing Needs Revisions",
            recipients=[owner_email],
            html=f"""
                <div style="font-family: Arial, sans-serif; line-height: 1.6;">
                    <img src="https://findurspace.blr1.digitaloceanspaces.com/findurspace/image-invert.png" alt="FindUrSpace Logo" width="150">

                    <p>Hi {owner_name},</p>

                    <p>Thank you for submitting your coworking space – <strong>{coworking_name}</strong> – for review.</p>

                    <p>After evaluation, we are unable to approve the listing at this time due to the following reason(s):</p>

                    <blockquote style="background-color: #fff3cd; padding: 10px; border-left: 4px solid #ffc107; font-style: italic;">
                        {feedback_message}
                    </blockquote>

                    <p>🔄 Please update your listing accordingly via the Operator Panel below:</p>
                    <p><a href="https://findurspace.tech/operators/login" style="color: #2b4eff;">Operator Panel Link</a></p>

                    <p>Warm regards,<br><strong>Farhat</strong><br>FindUrSpace</p>
                </div>
            """
        )
        mail.send(message)
        print(f"Edit-required email sent to {owner_email}")
    except Exception as e:
        print(f"Failed to send edit-required email: {e}")


def send_admin_approval_email(owner_name, owner_email, coworking_name):
    try:
        mail = current_app.extensions['mail']
        message = Message(
            subject="Your Listing Has Been Approved – Welcome to FindUrSpace!",
            recipients=[owner_email],
            html=f"""
                <div style="font-family: Arial, sans-serif; line-height: 1.6;">
                    <img src="https://findurspace.blr1.digitaloceanspaces.com/findurspace/image-invert.png" alt="FindUrSpace Logo" width="150">
                    
                    <p>Hi {owner_name},</p>

                    <p>Your coworking space <strong>{coworking_name}</strong> has just been approved and is now <strong>live</strong> on FindUrSpace!</p>

                    <p>Professionals searching for flexible offices can now discover and book your space.</p>

                    <p><strong>Login to your Operator Panel</strong> to manage bookings, view inquiries, and update availability:</p>
                    <p><a href="https://findurspace.tech/operators/login">Operator Dashboard</a></p>

                    <p>Welcome aboard,<br><strong>Team FindUrSpace</strong></p>
                </div>
            """
        )
        mail.send(message)
        print(f"Approval email sent to {owner_email}")
    except Exception as e:
        print(f"Failed to send approval email: {e}")

@admin_bp.route('/managed_inventory', methods=['GET'])
def managed_inventory():
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))
    
    db = current_app.config['db']
    
    # Filter: workspace_type = 'Managed Offices' and total_building_area exists
    spaces = list(db.fillurdetails.find({
        "workspace_type": "Managed Offices",
        "total_building_area": {"$ne": None}
    }))
    
    # Get distinct cities from the filtered spaces
    cities = list({space['city'] for space in spaces if 'city' in space and space['city']})
    
    # Get distinct micromarkets from the filtered spaces
    micromarkets = list({space['micromarket'] for space in spaces if 'micromarket' in space and space['micromarket']})

    return render_template('managed_inventory.html', cities=cities, micromarkets=micromarkets, role=session.get('role'))


@admin_bp.route('/managed_inventory_seats', methods=['GET'])
def managed_inventory_seats():
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))
    
    db = current_app.config['db']
    cities = db.fillurdetails.distinct('city')
    micromarkets = db.fillurdetails.distinct('micromarket')
    
    return render_template('managed_inventory_seats.html', cities=cities, micromarkets=micromarkets, role=session.get('role'))


@admin_bp.route('/get_micromarkets_live/<city>', methods=['GET'])
def get_micromarkets_live(city):
    if 'admin' not in session:
        return jsonify({'status': 'error', 'message': 'Not authorized'}), 403

    db = current_app.config['db']

    # Find micromarkets for the normalized city in the fillurdetails collection
    micromarkets = db.fillurdetails.distinct("micromarket", {"city": {"$regex": f"^{city}$", "$options": "i"}})

    if not micromarkets:
        return jsonify({'status': 'error', 'message': 'No micromarkets found for the city'}), 404

    return jsonify(micromarkets)

@admin_bp.route('/fetch_coworking_inventory', methods=['GET'])
def fetch_coworking_inventory():
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))

    db = current_app.config['db']  # Access the db instance from the current app context
    fillurdetails_collection = db['fillurdetails']

    # Get filter parameters
    city = request.args.get('city')
    micromarket = request.args.get('micromarket')
    inventory_type = request.args.get('inventory_type')
    price = request.args.get('price')
    workspace_type = request.args.get('workspace_type')  # NEW 
    building_area = request.args.get('building_area')
    rental_range = request.args.get('rental_range')
    seating_range = request.args.get('seating_range')
    
    filters = {}

    if city:
        filters['city'] = city
    if micromarket:
        filters['micromarket'] = micromarket
    if inventory_type:
        filters['inventory.type'] = inventory_type
    if price:
        try:
            filters['price'] = {'$lte': int(price)}
        except ValueError:
            pass
    if building_area:
        try:
            building_area = building_area.strip()
            if building_area.endswith('+'):
                min_val = int(building_area[:-1])  # Get all characters except '+'
                filters['total_building_area'] = {'$gte': min_val}
            else:
                min_val, max_val = map(int, building_area.split('-'))
                filters['total_building_area'] = {'$gte': min_val, '$lte': max_val}
        except Exception as e:
            print("Error parsing building_area filter:", building_area, e)

    if rental_range:
        if '+' in rental_range:
            min_val = int(rental_range.replace('+', ''))
            filters['total_rental'] = {'$gte': min_val}
        else:
            min_val, max_val = map(int, rental_range.split('-'))
            filters['total_rental'] = {'$gte': min_val, '$lte': max_val}

    if seating_range:
        if '+' in seating_range:
            min_val = int(seating_range.replace('+', ''))
            filters['min_inventory_unit'] = {'$gte': min_val}
        else:
            min_val, max_val = map(int, seating_range.split('-'))
            filters['min_inventory_unit'] = {'$gte': min_val, '$lte': max_val}
    if workspace_type:
        filters['workspace_type'] = workspace_type  # NEW LINE

    # Fetch coworking space data
    coworking_list = list(fillurdetails_collection.find(filters, {'layout_images': 0, 'interactive_layout': 0}).sort('date', -1))

    # Include stringified `_id`
    for coworking in coworking_list:
        coworking['_id'] = str(coworking['_id'])
        coworking['center_manager'] = coworking.get('center_manager', {'name': 'N/A', 'contact': 'N/A'})

        owner_phone = coworking.get('owner', {}).get('phone')
        if owner_phone:
            related_entries = list(fillurdetails_collection.find({'owner.phone': owner_phone}, {'uploaded_pdfs': 1}))
            coworking['agreement_status'] = 'Completed' if any(entry.get('uploaded_pdfs') for entry in related_entries) else 'Pending'
        else:
            coworking['agreement_status'] = 'Pending'

        # ✅ Directly check inside fillurdetails for amenities
        if coworking.get('amenities'):
            coworking['has_amenities'] = True
        else:
            coworking['has_amenities'] = False
            
    return jsonify({
        'spaces': coworking_list
    })

@admin_bp.route('/fetch_inventory_seats', methods=['GET'])
def fetch_inventory_seats():
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))

    db = current_app.config['db']
    fillurdetails_collection = db['fillurdetails']

    # Get filter parameters
    city = request.args.get('city')
    micromarket = request.args.get('micromarket')
    workspace_type = request.args.get('workspace_type')  # Should be "Managed Offices"

    # Base mandatory filters for managed_inventory_seats
    filters = {
        "workspace_type": "Managed Offices",
        "total_building_area": None  # ❗ Only where building area is null
    }

    # Optional dynamic filters
    if city:
        filters['city'] = city
    if micromarket:
        filters['micromarket'] = micromarket

    # Fetch coworking spaces
    coworking_list = list(fillurdetails_collection.find(filters, {'layout_images': 0, 'interactive_layout': 0}).sort('date', -1))

    # Prepare data
    for coworking in coworking_list:
        coworking['_id'] = str(coworking['_id'])
        coworking['center_manager'] = coworking.get('center_manager', {'name': 'N/A', 'contact': 'N/A'})

        owner_phone = coworking.get('owner', {}).get('phone')
        if owner_phone:
            related_entries = list(fillurdetails_collection.find({'owner.phone': owner_phone}, {'uploaded_pdfs': 1}))
            coworking['agreement_status'] = 'Completed' if any(entry.get('uploaded_pdfs') for entry in related_entries) else 'Pending'
        else:
            coworking['agreement_status'] = 'Pending'

    return jsonify({'spaces': coworking_list})


@admin_bp.route('/fetch_inventory', methods=['GET'])
def fetch_inventory():
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))

    db = current_app.config['db']  # Access the db instance from the current app context
    fillurdetails_collection = db['fillurdetails']

    # Get filter parameters
    city = request.args.get('city')
    micromarket = request.args.get('micromarket')
    inventory_type = request.args.get('inventory_type')
    price = request.args.get('price')
    workspace_type = request.args.get('workspace_type')  # NEW 
    building_area = request.args.get('building_area')
    rental_range = request.args.get('rental_range')
    seating_range = request.args.get('seating_range')
    
    # Base mandatory filters
    filters = {
        "workspace_type": "Managed Offices",
        "total_building_area": {"$ne": None}
    }

    if city:
        filters['city'] = city
    if micromarket:
        filters['micromarket'] = micromarket
    if inventory_type:
        filters['inventory.type'] = inventory_type
    if price:
        try:
            filters['price'] = {'$lte': int(price)}
        except ValueError:
            pass
    if building_area:
        try:
            building_area = building_area.strip()
            if building_area.endswith('+'):
                min_val = int(building_area[:-1])  # Get all characters except '+'
                filters['total_building_area'] = {'$gte': min_val}
            else:
                min_val, max_val = map(int, building_area.split('-'))
                filters['total_building_area'] = {'$gte': min_val, '$lte': max_val}
        except Exception as e:
            print("Error parsing building_area filter:", building_area, e)

    if rental_range:
        if '+' in rental_range:
            min_val = int(rental_range.replace('+', ''))
            filters['total_rental'] = {'$gte': min_val}
        else:
            min_val, max_val = map(int, rental_range.split('-'))
            filters['total_rental'] = {'$gte': min_val, '$lte': max_val}

    if seating_range:
        if '+' in seating_range:
            min_val = int(seating_range.replace('+', ''))
            filters['min_inventory_unit'] = {'$gte': min_val}
        else:
            min_val, max_val = map(int, seating_range.split('-'))
            filters['min_inventory_unit'] = {'$gte': min_val, '$lte': max_val}
    if workspace_type:
        filters['workspace_type'] = workspace_type  # NEW LINE

    # Fetch coworking space data
    coworking_list = list(fillurdetails_collection.find(filters, {'layout_images': 0, 'interactive_layout': 0}).sort('date', -1))

    # Include stringified `_id`
    for coworking in coworking_list:
        coworking['_id'] = str(coworking['_id'])
        coworking['center_manager'] = coworking.get('center_manager', {'name': 'N/A', 'contact': 'N/A'})

        # Determine agreement status
        owner_phone = coworking.get('owner', {}).get('phone')
        if owner_phone:
            related_entries = list(fillurdetails_collection.find({'owner.phone': owner_phone}, {'uploaded_pdfs': 1}))
            coworking['agreement_status'] = 'Completed' if any(entry.get('uploaded_pdfs') for entry in related_entries) else 'Pending'
        else:
            coworking['agreement_status'] = 'Pending'

    return jsonify({
        'spaces': coworking_list
    })



@admin_bp.route('/coworking_details', methods=['GET'])
def coworking_details():
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))

    coworking_name = request.args.get('coworking_name')
    db = current_app.config['db']  # Access the db instance from the current app context
    fillurdetails_collection = db['fillurdetails']

    # Fetch the coworking space details by name
    coworking_space = fillurdetails_collection.find_one({'coworking_name': coworking_name}, {'_id': 0})

    if coworking_space:
        return render_template('coworking_details.html', space=coworking_space)
    else:
        return "Coworking space not found", 404

# ---------------------------------------------------------New Route to Update City and Micromarket------------------------------------------------------------------------------------

@admin_bp.route('/update_property', methods=['POST'])
def update_property():
    if 'admin' not in session:
        return jsonify({'status': 'error', 'message': 'Not authorized'}), 403

    data = request.get_json()
    property_id = data.get('property_id')
    field = data.get('field')
    value = data.get('value')

    # Validate input
    if not property_id or not field or value is None:
        return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

    # Define allowed fields to prevent unauthorized updates
    allowed_fields = ['city', 'micromarket']
    if field not in allowed_fields:
        return jsonify({'status': 'error', 'message': f'Field "{field}" is not allowed to be updated'}), 400

    db = current_app.config['db']

    try:
        result = db.properties.update_one(
            {'_id': ObjectId(property_id)},
            {'$set': {field: value}}
        )
        if result.modified_count > 0:
            return jsonify({'status': 'success', 'message': f'Property {field} updated successfully'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'No changes made or property not found'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'An error occurred: {str(e)}'}), 500

@admin_bp.route('/delete_property', methods=['POST'])
def delete_property():
    if 'admin' not in session:
        return jsonify({'status': 'error', 'message': 'Not authorized'}), 403

    data = request.get_json()
    property_id = data.get('property_id')

    if not property_id:
        return jsonify({'status': 'error', 'message': 'Property ID is required'}), 400

    db = current_app.config['db']

    try:
        result = db.fillurdetails.delete_one({'_id': ObjectId(property_id)})

        if result.deleted_count > 0:
            return jsonify({'status': 'success', 'message': 'Property deleted successfully'}), 200
        else:
            return jsonify({'status': 'error', 'message': 'Property not found'}), 404

    except Exception as e:
        print(f"Error deleting property: {e}")
        return jsonify({'status': 'error', 'message': f'An error occurred: {str(e)}'}), 500


@admin_bp.route('/bookings', methods=['GET'])
def admin_bookings():
    if 'admin' not in session:
        return jsonify({'status': 'error', 'message': 'Not authorized'}), 403

    db = current_app.config['db']  # Access MongoDB

    # Fetch all bookings from the 'bookings' collection
    # Fetch all bookings, sorted by date descending
    bookings_cursor = db.booking.find().sort('date', -1)
    bookings = list(bookings_cursor)

    # Convert ObjectId to string for template rendering
    for booking in bookings:
        booking['_id'] = str(booking['_id'])

        # Fetch property details from 'fillurdetails' using property_id
        property_id = booking.get('property_id')
        if property_id:
            property_data = db.fillurdetails.find_one({'_id': ObjectId(property_id)})

            if property_data:
                # Add property details to the booking record
                booking['coworking_name'] = property_data.get('coworking_name', 'N/A')
                booking['city'] = property_data.get('city', 'N/A')
                booking['micromarket'] = property_data.get('micromarket', 'N/A')

                # Owner details
                owner = property_data.get('owner', {})
                booking['owner_name'] = owner.get('name', 'N/A')
                booking['owner_phone'] = owner.get('phone', 'N/A')
                booking['owner_email'] = owner.get('email', 'N/A')

                # Center manager details
                center_manager = property_data.get('center_manager', {})
                booking['center_manager_name'] = center_manager.get('name', 'N/A')
                booking['center_manager_contact'] = center_manager.get('contact', 'N/A')

    return render_template('admin_bookings.html', bookings=bookings)

# ✅ Update booking status (Approve/Decline)
@admin_bp.route('/update_booking_status', methods=['POST'])
def update_booking_status():
    db = current_app.config['db']
    data = request.json
    booking_id = data.get('booking_id')
    new_status = data.get('status')

    if not booking_id or not new_status:
        return jsonify({'status': 'error', 'message': 'Missing booking ID or status'})

    # Update the booking status in MongoDB
    result = db.booking.update_one({'_id': ObjectId(booking_id)}, {'$set': {'status': new_status}})
    
    if result.modified_count > 0:
        return jsonify({'status': 'success', 'new_status': new_status})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to update status'})
    
# ✅ Process payment (Mark as Paid)
@admin_bp.route('/update_payment_status', methods=['POST'])
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
    
@admin_bp.route('/visits', methods=['GET'])
def admin_visits():
    if 'admin' not in session:
        return jsonify({'status': 'error', 'message': 'Not authorized'}), 403

    db = current_app.config['db']

    # Fetch all visits
    visits_cursor = db.visits.find().sort("date", -1)
    visits = []

    for visit in visits_cursor:
        property_details = db.fillurdetails.find_one({'_id': ObjectId(visit['property_id'])})

        visit_data = {
            '_id': str(visit['_id']),
            'user_name': visit.get('name', 'N/A'),
            'email': visit.get('email', 'N/A'),
            'company': visit.get('company', 'N/A'),
            'contact': visit.get('contact', 'N/A'),
            'inventory_type': visit.get('inventory_type', 'N/A'),
            'date': visit.get('date').strftime('%d %b %Y') if visit.get('date') else 'N/A',
            'time': visit.get('time', 'N/A'),
            'duration': visit.get('duration', 'N/A'),
            'gstin': visit.get('gstin', 'N/A'),
            'num_seats': visit.get('num_seats', 'N/A'),
            'budget': visit.get('budget', 'N/A'),
            'status': visit.get('status', 'pending'),
        }

        # Fetch property details
        if property_details:
            visit_data.update({
                'coworking_name': property_details.get('coworking_name', 'N/A'),
                'city': property_details.get('city', 'N/A'),
                'micromarket': property_details.get('micromarket', 'N/A'),
                'owner_name': property_details.get('owner', {}).get('name', 'N/A'),
                'owner_phone': property_details.get('owner', {}).get('phone', 'N/A'),
                'owner_email': property_details.get('owner', {}).get('email', 'N/A'),
                'center_manager_name': property_details.get('center_manager', {}).get('name', 'N/A'),
                'center_manager_contact': property_details.get('center_manager', {}).get('contact', 'N/A'),
            })

        visits.append(visit_data)

    return render_template('admin_visits.html', visits=visits)

# ✅ Update visit status (Approve/Decline)
@admin_bp.route('/update_visit_status', methods=['POST'])
def update_visit_status():
    if 'admin' not in session:
        return jsonify({'status': 'error', 'message': 'Not authorized'}), 403

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


@admin_bp.route('/users', methods=['GET'])
def view_users():
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))

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

