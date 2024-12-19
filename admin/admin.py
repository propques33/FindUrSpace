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


# Blueprint definition
admin_bp = Blueprint('admin', __name__, url_prefix='/admin', template_folder='templates')

# Admin Credentials
admin_credentials = {
    "project.propques@gmail.com": "Prop@11@@33",
    "buzz@propques.com": "Prop@11@@33"
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
            'layout_images': p.get('layout_images', [])
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
            return redirect(url_for('admin.leads_dashboard'))  # Redirect to Leads Dashboard after successful login
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


@admin_bp.route('/leads_dashboard')
def leads_dashboard():
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))

    db = current_app.config['db']

    # Count of live inventory (all properties)
    live_inventory_count = db.fillurdetails.count_documents({})

    # Fetch leads data from the 'leads_status' collection
    leads_status = db.leads_status.find()

    # Count total number of leads
    total_leads = db.leads_status.count_documents({})

    # Aggregating opportunity status and stages
    status_counts = {'open': 0, 'closed': 0, 'won': 0}
    stage_counts = {
        'qualified': 0, 'follow-up': 0, 'visit done': 0,
        'negotiation': 0, 'won': 0, 'lost': 0, 'unqualified': 0
    }

    for lead in leads_status:
        status = lead.get('opportunity_status', 'open').lower()
        status_counts[status] = status_counts.get(status, 0) + 1

        stage = lead.get('opportunity_stage', 'visit done').lower()
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    # Aggregating city-wise inventory count (convert city names to title case and normalize names)
    city_inventory = db.fillurdetails.aggregate([
        {"$group": {"_id": {"$toUpper": "$city"}, "count": {"$sum": 1}}}
    ])
    city_inventory_data = list(city_inventory)

    # Convert city names to handle common names
    city_name_mapping = {
        "BANGALORE": "Bengaluru",
        "GURGAON": "Gurugram"
    }

    city_inventory_normalized = []
    for item in city_inventory_data:
        city = item['_id'].title()
        city = city_name_mapping.get(city.upper(), city)  # Use normalized name if available
        found = next((i for i in city_inventory_normalized if i['_id'] == city), None)
        if found:
            found['count'] += item['count']
        else:
            city_inventory_normalized.append({'_id': city, 'count': item['count']})

    # Preparing KPI visualizations
    kpi_figures = []
    kpis = [
        {"label": "Total Leads", "value": total_leads, "color": "#17becf"},
        {"label": "Open Leads", "value": status_counts.get('open', 0), "color": "#1f77b4"},
        {"label": "Closed Leads", "value": status_counts.get('closed', 0), "color": "#ff7f0e"},
        {"label": "Won Leads", "value": status_counts.get('won', 0), "color": "#2ca02c"},
        {"label": "Live Inventory", "value": live_inventory_count, "color": "#e377c2"}
    ]

    for kpi in kpis:
        kpi_fig = go.Figure(go.Indicator(
            mode="number",
            value=kpi['value'],
            title={"text": kpi['label']},
            number={'font': {'size': 40, 'color': kpi['color']}}
        ))
        kpi_fig.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=200)
        kpi_figures.append(kpi_fig.to_html(full_html=False))

    # Bar Chart for Opportunity Stages
    stage_bar_fig = go.Figure(go.Bar(
        x=list(stage_counts.keys()),
        y=list(stage_counts.values()),
        marker_color='rgb(55, 83, 109)'
    ))
    stage_bar_fig.update_layout(
        title='Opportunity Stage Distribution',
        xaxis_title='Opportunity Stage',
        yaxis_title='Count',
        width=1200,
        height=450,
        margin=dict(l=40, r=40, t=60, b=40)
    )

    # Bar Chart for Live Inventory by City
    city_names = [item['_id'] for item in city_inventory_normalized]
    city_counts = [item['count'] for item in city_inventory_normalized]

    city_bar_fig = go.Figure(go.Bar(
        x=city_names,
        y=city_counts,
        marker_color='rgb(26, 118, 255)'
    ))
    city_bar_fig.update_layout(
        title='Live Inventory by City',
        xaxis_title='City',
        yaxis_title='Inventory Count',
        width=1200,
        height=450,
        margin=dict(l=40, r=40, t=60, b=40),
    )

    # Render the dashboard template with the new figures
    return render_template(
        'leads_dashboard.html',
        kpi_figures=kpi_figures,
        stage_bar_fig=stage_bar_fig.to_html(full_html=False),
        city_bar_fig=city_bar_fig.to_html(full_html=False)
    )


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

    coworking_spaces = db.coworking_spaces.find(filters)
    coworking_list = list(coworking_spaces)

    # Convert the documents to JSON format and include _id
    result_list = [{
        '_id': str(space['_id']),  # Convert ObjectId to string
        'name': space['name'],
        'city': space['city'],
        'micromarket': space['micromarket'],
        'price': space['price'],
        'seats': space.get('seats', 'N/A')
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

    return render_template('live_inventory.html', cities=cities, micromarkets=micromarkets)

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

    filters = {}
    if city:
        filters['city'] = city
    if micromarket:
        filters['micromarket'] = micromarket
    if inventory_type:
        # Match inventory type within the inventory array
        filters['inventory.type'] = inventory_type
    if price:
        try:
            filters['price'] = {'$lte': int(price)}
        except ValueError:
            pass

    # Fetch coworking space data
    coworking_list = list(fillurdetails_collection.find(filters, {'layout_images': 0, 'interactive_layout': 0}).sort('date', -1))

    # Include stringified `_id`
    for coworking in coworking_list:
        coworking['_id'] = str(coworking['_id'])

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
