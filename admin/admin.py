from flask import Blueprint, jsonify, render_template, request, redirect, url_for, session, send_file, current_app, flash
import datetime
from bson import ObjectId
from io import BytesIO
import plotly.graph_objects as go

# Blueprint definition
admin_bp = Blueprint('admin', __name__, url_prefix='/admin', template_folder='templates')

# Admin Credentials
admin_credentials = {
    "project.propques@gmail.com": "Prop@11@@33",
    "buzz@propques.com": "Prop@11@@33"
}

# Admin Login Route
@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if 'admin' in session:
        return redirect(url_for('admin.admin_dashboard'))  # Don't ask to log in again if already logged in

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        if email in admin_credentials and admin_credentials[email] == password:
            session['admin'] = email
            return redirect(url_for('admin.admin_dashboard'))
        else:
            return render_template('admin_login.html', error='Invalid login credentials. Please try again.')

    return render_template('admin_login.html')

# Admin Dashboard Route with Two Cards
@admin_bp.route('/dashboard')
def admin_dashboard():
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))

    return render_template('admin_dashboard.html')

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

# Route to download binary files from MongoDB
@admin_bp.route('/download_file/<collection_name>/<document_id>/<filename>')
def download_file(collection_name, document_id, filename):
    db = current_app.config['db']  # Access the database here
    document = db[collection_name].find_one({'_id': ObjectId(document_id)})

    if document and 'pdf_files' in document:
        for file in document['pdf_files']:
            if file['filename'] == filename:
                # Use a default content_type if it's missing
                content_type = file.get('content_type', 'application/octet-stream')
                return send_file(BytesIO(file['data']),
                                 download_name=filename,
                                 as_attachment=True,
                                 mimetype=content_type)

    return redirect(url_for('admin.view_collection', collection_name=collection_name))

# Route to download images from MongoDB
@admin_bp.route('/download_image/<document_id>/<image_filename>')
def download_image(document_id, image_filename):
    db = current_app.config['db']
    document = db.fillurdetails.find_one({'_id': ObjectId(document_id)})

    if document and 'floors' in document:
        for floor in document['floors']:
            if floor['image_filename'] == image_filename:
                # Use a default content_type if it's missing
                content_type = floor.get('content_type', 'application/octet-stream')
                return send_file(BytesIO(floor['image_data']),
                                 download_name=image_filename,
                                 as_attachment=True,
                                 mimetype=content_type)

    flash('Image not found.', 'error')
    return redirect(url_for('admin.view_collection', collection_name='fillurdetails'))

# Delete Document Route
@admin_bp.route('/delete_document/<collection_name>/<document_id>', methods=['POST'])
def delete_document(collection_name, document_id):
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))

    db = current_app.config['db']  # Access the database here
    db[collection_name].delete_one({'_id': ObjectId(document_id)})

    return redirect(url_for('admin.view_collection', collection_name=collection_name))

@admin_bp.route('/update_interactive_layout/<property_id>', methods=['POST'])
def update_interactive_layout(property_id):
    db = current_app.config['db']  # Access the database here

    try:
        # Find the property by its ID and update the interactive_layout field
        db.fillurdetails.update_one(
            {'_id': ObjectId(property_id)},
            {'$set': {'interactive_layout': True}}
        )
        flash('Interactive layout updated successfully.', 'success')
    except Exception as e:
        flash(f"Error updating interactive layout: {e}", 'error')
        print(f"Error updating interactive layout: {e}")  # Debugging step

    return redirect(url_for('admin.admin_dashboard'))

# Route to show "Manage Interactive Layout" page
@admin_bp.route('/manage-interactive-layout', methods=['GET'])
def manage_interactive_layout():
    db = current_app.config['db']
    # Fetch all properties that have floors or images that haven't been made interactive
    properties = db.fillurdetails.find({'interactive_layout': False}, {'coworking_name': 1, 'floors': 1, '_id': 1})
    return render_template('manage_interactive_layout.html', properties=properties)

# Route to retrieve property images from MongoDB
@admin_bp.route('/get_property_images/<property_id>', methods=['GET'])
def get_property_images(property_id):
    db = current_app.config['db']
    # Fetch the images related to the property
    property_data = db.fillurdetails.find_one({'_id': ObjectId(property_id)}, {'floors': 1})
    if not property_data or 'floors' not in property_data:
        return jsonify({'status': 'error', 'message': 'No images found'}), 404

    images = [{'image_filename': floor['image_filename'], '_id': str(floor['_id'])} for floor in property_data['floors']]
    return jsonify({'images': images})

# Route to retrieve a specific image from MongoDB
@admin_bp.route('/get_image/<image_id>', methods=['GET'])
def get_image(image_id):
    db = current_app.config['db']
    # Fetch the specific image by its ID
    floor = db.fillurdetails.find_one({'floors._id': ObjectId(image_id)}, {'floors.$': 1})
    if not floor or 'floors' not in floor or len(floor['floors']) == 0:
        return "Image not found", 404

    image = floor['floors'][0]
    return send_file(BytesIO(image['image_data']),
                     mimetype=image.get('content_type', 'image/jpeg'),
                     as_attachment=False,
                     download_name=image.get('image_filename', 'floor_image.png'))

# Route to save the interactive layout
@admin_bp.route('/save_interactive_layout', methods=['POST'])
def save_interactive_layout():
    data = request.get_json()
    image_id = data['imageId']
    layout_json = data['layout']

    # Update the specific floor document with the layout
    db = current_app.config['db']
    db.fillurdetails.update_one(
        {'floors._id': ObjectId(image_id)},
        {'$set': {'floors.$.layout_json': layout_json, 'floors.$.interactive_layout': True}}
    )

    return jsonify({'status': 'success'})


@admin_bp.route('/leads', methods=['GET', 'POST'])
def view_leads():
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))

    db = current_app.config['db']

    properties = db.properties.find()
    leads = []

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
                    'notes': ''
                }
                db.leads_status.insert_one(lead_status)

            leads.append({
                'lead_id': str(lead_status['user_id']),
                'property_id': str(lead_status['property_id']),
                'user_name': user.get('name', 'Unknown'),
                'user_company': user.get('company', 'Unknown'),
                'user_email': user.get('email', 'N/A'),
                'user_contact': user.get('contact', 'N/A'),
                'property_location': property_data.get('location', 'N/A'),
                'property_seats': property_data.get('seats', 'N/A'),
                'property_budget': property_data.get('budget', 'N/A'),
                'opportunity_status': lead_status.get('opportunity_status', 'open'),
                'opportunity_stage': lead_status.get('opportunity_stage', 'visit done'),
                'notes': lead_status.get('notes', '')
            })

    return render_template('view_leads.html', leads=leads)

@admin_bp.route('/update_lead', methods=['POST'])
def update_lead():
    if 'admin' not in session:
        return jsonify({'status': 'error', 'message': 'Not authorized'}), 403

    data = request.get_json()
    lead_id = data.get('lead_id')
    property_id = data.get('property_id')
    field = data.get('field')
    value = data.get('value')

    db = current_app.config['db']
    
    # Update the leads_status collection with the new values
    db.leads_status.update_one(
        {'user_id': ObjectId(lead_id), 'property_id': ObjectId(property_id)},
        {'$set': {field: value}}
    )

    return jsonify({'status': 'success'})


@admin_bp.route('/delete_lead', methods=['POST'])
def delete_lead():
    if 'admin' not in session:
        return jsonify({'status': 'error', 'message': 'Not authorized'}), 403

    data = request.get_json()
    lead_id = data.get('lead_id')
    property_id = data.get('property_id')

    db = current_app.config['db']

    # Delete from leads_status
    db.leads_status.delete_one({'user_id': ObjectId(lead_id), 'property_id': ObjectId(property_id)})
    
    # Delete the corresponding property
    db.properties.delete_one({'_id': ObjectId(property_id)})

    return jsonify({'status': 'success'})

# Route for Leads Dashboard
@admin_bp.route('/leads_dashboard')
def leads_dashboard():
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))

    db = current_app.config['db']
    
    # Fetch leads data from the 'leads_status' collection
    leads_status = db.leads_status.find()

    # Count total number of leads
    total_leads = db.leads_status.count_documents({})

    # Aggregating opportunity status
    status_counts = {
        'open': 0,
        'closed': 0,
        'won': 0
    }

    stage_counts = {
        'qualified': 0,
        'follow-up': 0,
        'visit done': 0,
        'negotiation': 0,
        'won': 0,
        'lost': 0,
        'unqualified': 0
    }

    # Count based on the opportunity_status and opportunity_stage
    for lead in leads_status:
        status_counts[lead['opportunity_status']] += 1
        stage_counts[lead['opportunity_stage']] += 1

    # Preparing Plotly visualizations

    # KPI (Total Leads)
    kpi_total = go.Indicator(
        mode="number",
        value=total_leads,
        title={"text": "Total Leads"},
        domain={'x': [0, 0.5], 'y': [0.7, 1]},
        number={'font': {'size': 40, 'color': '#17becf'}},
    )

    # KPI (Open Leads)
    kpi_open = go.Indicator(
        mode="number",
        value=status_counts['open'],
        title={"text": "Open Leads"},
        domain={'x': [0.5, 1], 'y': [0.7, 1]},
        number={'font': {'size': 40, 'color': '#1f77b4'}}
    )

    # KPI (Closed Leads)
    kpi_closed = go.Indicator(
        mode="number",
        value=status_counts['closed'],
        title={"text": "Closed Leads"},
        domain={'x': [0, 0.5], 'y': [0.4, 0.7]},
        number={'font': {'size': 40, 'color': '#ff7f0e'}}
    )

    # KPI (Won Leads)
    kpi_won = go.Indicator(
        mode="number",
        value=status_counts['won'],
        title={"text": "Won Leads"},
        domain={'x': [0.5, 1], 'y': [0.4, 0.7]},
        number={'font': {'size': 40, 'color': '#2ca02c'}}
    )

    # Combine all KPI indicators into a single figure
    kpi_fig = go.Figure(data=[kpi_total, kpi_open, kpi_closed, kpi_won])
    kpi_fig.update_layout(
        grid={'rows': 2, 'columns': 2, 'pattern': "independent"},
        margin=dict(l=20, r=20, t=40, b=20),
        height=400
    )

    # Pie Chart (Opportunity Status)
    pie_fig = go.Figure(go.Pie(
        labels=list(status_counts.keys()),
        values=list(status_counts.values()),
        title="Opportunity Status",
        marker={'colors': ['#1f77b4', '#ff7f0e', '#2ca02c']}
    ))

    pie_fig.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=40, b=20),
        showlegend=True,
    )

    # Stacked Bar Chart (Opportunity Stages)
    bar_fig = go.Figure()
    bar_fig.add_trace(go.Bar(
        x=list(stage_counts.keys()),
        y=list(stage_counts.values()),
        name='Opportunity Stage',
        marker_color='rgb(55, 83, 109)'
    ))

    bar_fig.update_layout(
        title="Opportunity Stage Breakdown",
        xaxis_tickfont_size=12,
        yaxis=dict(
            title='Number of Leads',
            titlefont_size=14,
            tickfont_size=12,
        ),
        barmode='stack',
        bargap=0.15,  # gap between bars
        bargroupgap=0.1,  # gap between grouped bars
        height=300,
        margin=dict(l=20, r=20, t=40, b=20)
    )

    # Render the dashboard template
    return render_template('leads_dashboard.html', 
                           kpi_fig=kpi_fig.to_html(full_html=False),
                           pie_fig=pie_fig.to_html(full_html=False),
                           bar_fig=bar_fig.to_html(full_html=False))
