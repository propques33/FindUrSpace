from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session
from flask_mail import Mail, Message
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle
from reportlab.lib.units import inch
import requests
from io import BytesIO
import pandas as pd
from pymongo import MongoClient, ASCENDING
import datetime
import secrets
import os
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
from PyPDF2 import PdfReader, PdfWriter
import OTPLessAuthSDK
from PIL import Image as PILImage
from google.oauth2.service_account import Credentials

# Importing the Google Drive integration module
from google_drive_integration import authenticate_google_drive, upload_pdf_to_google_drive, send_pdf_via_noapp


import base64
import json
import urllib.parse
from whatsapp_integration import send_whatsapp_verification
from gsheet_updater import handle_new_property_entry
from godial import send_data_to_godial

load_dotenv()

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'findurspace1@gmail.com'
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = 'findurspace1@gmail.com'

mail = Mail(app)

# MongoDB configuration
client = MongoClient(os.environ.get('MONGO_URI'))
db = client['FindYourSpace']

# Create indexes for efficient querying
db.email_logs.create_index([('email', ASCENDING), ('date', ASCENDING)])

# # Load the cleaned CSV data
# coworking_data = list(db.coworking_spaces.find({}))

# # Convert the list of dictionaries into a DataFrame
# data = pd.DataFrame(data_list)

def check_email_limit(email):
    if "@gmail.com" in email:
        limit_date = datetime.datetime.now() - datetime.timedelta(days=30)
        email_count = db.email_logs.count_documents({
            'email': email,
            'date': {'$gte': limit_date}
        })
        return email_count < 10
    return True

def fetch_image(url):
    try:
        response = requests.get(url)
        if response.status_code == 200 and 'image' in response.headers['Content-Type']:
            return PILImage.open(BytesIO(response.content))
    except Exception as e:
        print(f"Failed to fetch image from {url}: {e}")
    return None

def generate_property_pdf(properties, doc, styles):
    elements = []

    # Define updated styles with larger font size and appropriate spacing
    styles.add(ParagraphStyle(name='EnhancedHeading', fontName='Helvetica-Bold', fontSize=32, spaceAfter=24))
    styles.add(ParagraphStyle(name='EnhancedNormal', fontName='Helvetica', fontSize=24, spaceAfter=16, leading=28))  # Increased leading to avoid overlapping

    for i, p in enumerate(properties, start=1):
        elements.append(Paragraph(f"Option {i}", styles['EnhancedHeading']))
        elements.append(Spacer(1, 16))
        elements.append(Paragraph(f"Name: {p['name']}", styles['EnhancedNormal']))
        elements.append(Spacer(1, 16))
        elements.append(Paragraph(f"Address: {p['micromarket']}, {p['city']}", styles['EnhancedNormal']))
        elements.append(Spacer(1, 16))
        elements.append(Paragraph(f"Details: {p['details']}", styles['EnhancedNormal']))
        elements.append(Spacer(1, 32))

        # Fetch images
        image1 = fetch_image(p['img1'])
        image2 = fetch_image(p['img2'])

        if image1 and image2:
            # Adjust image size, position, and add white space between them
            table_data = [[Image(BytesIO(requests.get(p['img1']).content), width=6.0*inch, height=5.0*inch),  # Increased size
                           Spacer(0.5*inch, 0),  # Add some space between images
                           Image(BytesIO(requests.get(p['img2']).content), width=6.0*inch, height=5.0*inch)]]  # Increased size

            image_table = Table(table_data)
            image_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]))
            elements.append(image_table)
        else:
            elements.append(Paragraph("Images could not be loaded.", styles['EnhancedNormal']))

        elements.append(PageBreak())  # Add a page break after each property

    doc.build(elements)

def send_email(to_email, name, properties):
    if not check_email_limit(to_email):
        flash(f"Email limit reached for {to_email}", "error")
        return False, None

    try:
        # Load the predesigned PDF and extract static pages
        static_pdf_path = os.path.join('static', 'pdffin.pdf')
        static_pdf = PdfReader(static_pdf_path)

        # Keep the page size consistent with the static pages
        static_page = static_pdf.pages[0]
        static_page_size = (static_page.mediabox.width, static_page.mediabox.height)

        # Create a new PDF for the dynamic content
        dynamic_pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(dynamic_pdf_buffer, pagesize=static_page_size, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()

        generate_property_pdf(properties, doc, styles)
        dynamic_pdf_buffer.seek(0)
        dynamic_pdf = PdfReader(dynamic_pdf_buffer)

        # Merge static and dynamic PDFs
        output_pdf = PdfWriter()

        # Add static pages (pages 1, 2, and 5 from the original PDF)
        output_pdf.add_page(static_pdf.pages[0])
        output_pdf.add_page(static_pdf.pages[1])

        # Add dynamic content
        for page in dynamic_pdf.pages:
            output_pdf.add_page(page)

        # Add the final static page from the original PDF
        output_pdf.add_page(static_pdf.pages[4])

        # Save the combined PDF to a buffer
        combined_pdf_buffer = BytesIO()
        output_pdf.write(combined_pdf_buffer)
        combined_pdf_buffer.seek(0)

        # Create email message and attach the combined PDF
        message = Message(subject='Your Property Data',
                          recipients=[to_email],
                          bcc=['enterprise.propques@gmail.com','buzz@propques.com','thomas@propques.com'],
                          html=f"<strong>Dear {name},</strong><br>"
                               "<strong>Please find attached the details of the properties you requested:</strong><br><br>"
                               "If you're interested in maximizing the benefits of the above properties at no cost, please reply to this email with 'Deal.' We will assign an account manager to coordinate with you.")
        message.attach("property_data.pdf", "application/pdf", combined_pdf_buffer.read())

        mail.send(message)
        return True, combined_pdf_buffer
    except Exception as e:
        flash(f"Failed to send email: {e}", "error")
        return False, None
    
# Function to handle PDF upload and WhatsApp message sending
def handle_pdf_upload_and_send(pdf_buffer, mobile_number):
    # Authenticate with Google Drive
    creds = authenticate_google_drive()

    # Upload the PDF to Google Drive and get the shareable link
    shareable_link = upload_pdf_to_google_drive(pdf_buffer, creds, "property_data.pdf")

    # Send the PDF via WhatsApp using the shareable link
    send_pdf_via_noapp(shareable_link, mobile_number)

def delete_old_email_logs():
    limit_date = datetime.datetime.now() - datetime.timedelta(days=30)
    result = db.email_logs.delete_many({'date': {'$lt': limit_date}})
    print(f"Deleted {result.deleted_count} old email logs.")

scheduler = BackgroundScheduler()
scheduler.add_job(func=delete_old_email_logs, trigger="interval", weeks=1)
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'verify_mobile':
            name = request.form.get('name')
            mobile = request.form.get('mobile')
            email = request.form.get('email')
            cname = request.form.get('cname')

            if not all([name, mobile, email, cname]):
                flash("Name, mobile, email, and company name are required.", "error")
                return render_template('index.html', name=name, mobile=mobile, email=email, cname=cname)

            session['name'] = name
            session['mobile'] = mobile
            session['email'] = email
            session['cname'] = cname

            user = db.users.find_one({'mobile_number': mobile})

            if user:
                flash("Mobile number already verified. You can proceed to submit the form.", "success")
            else:
                result = send_whatsapp_verification(mobile)
                if result.get('success'):
                    flash("A WhatsApp verification message has been sent to your mobile number. Please verify to proceed.", "success")
                else:
                    flash("Failed to send WhatsApp verification. Please try again.", "error")

            return redirect(url_for('index'))

        elif action == 'submit_form':
            name = session.get('name')
            mobile = session.get('mobile')
            email = session.get('email')
            cname = session.get('cname')  # Retrieve cname from the session here
            property_type = request.form.get('property_type')
            selected_city = request.form.get('city')
            selected_micromarket = request.form.get('micromarket')
            seats = request.form.get('seats')
            budget = request.form.get('budget')
            terms_accepted = request.form.get('terms')  # Get the value of the checkbox

            if not terms_accepted:
                flash("You must agree to the Terms and Conditions.", "error")
                return render_template('index.html', name=name, mobile=mobile, email=email, cname=cname, 
                                       property_type=property_type, selected_city=selected_city, 
                                       selected_micromarket=selected_micromarket, seats=seats, budget=budget)

            if not all([name, mobile, email, cname, property_type, selected_city, selected_micromarket, budget, seats]):
                flash("All form fields are required.", "error")
                return render_template('index.html', name=name, mobile=mobile, email=email, cname=cname, 
                                       property_type=property_type, selected_city=selected_city, 
                                       selected_micromarket=selected_micromarket, seats=seats, budget=budget)

            user = db.users.find_one({'mobile_number': mobile})

            if user:
                db.users.update_one(
                    {'mobile_number': mobile},
                    {'$set': {'name': name, 'email': email, 'cname': cname}},
                    upsert=True
                )
            else:
                db.users.update_one(
                    {'mobile_number': mobile},
                    {'$setOnInsert': {'name': name, 'email': email, 'cname': cname}},
                    upsert=True
                )

            # if property_type == 'coworking':
            #     data = coworking_data

            # Query MongoDB directly for the properties
            filtered_properties = list(db.coworking_spaces.find({
                'city': selected_city,
                'micromarket': selected_micromarket,
                'price': {'$lte': float(budget)}
            }))

            if not filtered_properties:

                # If no properties are found, create a PDF with the static pages 1, 2, and 5, and a custom message
                static_pdf_path = os.path.join('static', 'pdffin.pdf')
                static_pdf = PdfReader(static_pdf_path)
                static_page_size = (static_pdf.pages[0].mediabox.width, static_pdf.pages[0].mediabox.height)
                
                # Create a new PDF for the custom message
                dynamic_pdf_buffer = BytesIO()
                doc = SimpleDocTemplate(dynamic_pdf_buffer, pagesize=static_page_size, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
                styles = getSampleStyleSheet()
                
                # Define custom styles with larger font sizes
                styles.add(ParagraphStyle(name='LargeTitle', fontName='Helvetica-Bold', fontSize=20, spaceAfter=12))
                styles.add(ParagraphStyle(name='LargeNormal', fontName='Helvetica', fontSize=16, spaceAfter=8))

                # Create the elements with the updated styles
                elements = [
                    Paragraph("Sorry, we don't have any properties available for the following details:", styles['LargeTitle']),
                    Spacer(1, 24),
                    Paragraph(f"City: {selected_city}", styles['LargeNormal']),
                    Paragraph(f"Micromarket: {selected_micromarket}", styles['LargeNormal']),
                    Paragraph(f"Budget: {budget}", styles['LargeNormal']),
                    Spacer(1, 24),
                    Paragraph("Please try again with different inputs.", styles['LargeNormal'])
                ]
                
                doc.build(elements)
                dynamic_pdf_buffer.seek(0)
                dynamic_pdf = PdfReader(dynamic_pdf_buffer)
                    
                # Merge static and dynamic PDFs
                output_pdf = PdfWriter()

                # Add static pages (pages 1, 2, and 5 from the original PDF)
                output_pdf.add_page(static_pdf.pages[0])
                output_pdf.add_page(static_pdf.pages[1])

                # Add the custom message page
                output_pdf.add_page(dynamic_pdf.pages[0])

                # Add the final static page from the original PDF
                output_pdf.add_page(static_pdf.pages[4])

                # Save the combined PDF to a buffer
                combined_pdf_buffer = BytesIO()
                output_pdf.write(combined_pdf_buffer)
                combined_pdf_buffer.seek(0)
                
                message = Message(subject='Property Search Results',
                                recipients=[email],
                                bcc=['enterprise.propques@gmail.com','buzz@propques.com','thomas@propques.com'],
                                html=f"<strong>Dear {name},</strong><br>"
                                    "<strong>Unfortunately, we couldn't find any properties matching your criteria. Please try again with different inputs</strong><br>"
                                    # f"<strong>City:</strong> {selected_city}<br>"
                                    # f"<strong>Micromarket:</strong> {selected_micromarket}<br>"
                                    # f"<strong>Budget:</strong> {budget}<br>"
                                    "Thank you for using our service.")
                message.attach("no_properties_found.pdf", "application/pdf", combined_pdf_buffer.read())
                mail.send(message)

                flash("No properties found for the given details. A notification email has been sent.", "error")
                return redirect(url_for('index'))

            success, pdf_buffer = send_email(email, name, filtered_properties)

            if success:
                property_names = ", ".join([p['name'] for p in filtered_properties])

                property_data = {
                    'user_id': user['_id'],
                    'city': selected_city,
                    'micromarket': selected_micromarket,
                    'budget': float(budget),
                    'seats': int(seats),
                    'date': datetime.datetime.now(),
                    'property_names': property_names
                }
                db.properties.insert_one(property_data)

                # Update Google Sheet
                handle_new_property_entry(db, property_data)

                # Send data to GoDial
                send_data_to_godial({
                    'name': name,
                    'email': email,
                    'mobile_number': mobile,
                    'cname': cname,
                    'seats': seats,
                    'city': selected_city,
                    'micromarket': selected_micromarket,
                    'property_names': property_names
                })

                if "@gmail.com" in email:
                    email_log = {
                        'email': email,
                        'date': datetime.datetime.now()
                    }
                    db.email_logs.insert_one(email_log)

                # Upload and send the PDF via WhatsApp to the user's mobile number
                handle_pdf_upload_and_send(pdf_buffer, mobile)
                
                # Flash the success message only once
                flash("Details sent successfully.", "success")
            else:
                flash("Email limit reached for this Gmail address. Please try again later.", "error")

            return redirect(url_for('index'))

    return render_template('index.html', name=session.get('name'), mobile=session.get('mobile'), 
                           email=session.get('email'), cname=session.get('cname'))


@app.route('/list-your-space')
def list_your_space():
    return render_template('FillUrDetails.html')

@app.route('/submit_property_details', methods=['POST'])
def submit_fillurdetails():
    try:
        # Extract form data
        coworking_name = request.form.get('coworking_name')
        city = request.form.get('city')
        micromarket = request.form.get('micromarket')
        name = request.form.get('name')
        owner_phone = request.form.get('owner_phone')
        owner_email = request.form.get('owner_email')
        total_seats = request.form.get('total_seats')
        current_vacancy = request.form.get('current_vacancy')
        inventory_type = request.form.getlist('inventory_type[]')
        inventory_count = request.form.getlist('inventory_count[]')
        price_per_seat = request.form.getlist('price_per_seat[]')

        # Handle file uploads
        uploaded_files = request.files.getlist('file_upload[]')
        files = []
        for file in uploaded_files:
            if file and (file.filename.endswith('.pdf') or file.filename.endswith('.dwg')):
                files.append({
                    'filename': file.filename,
                    'data': file.read(),
                    'content_type': file.content_type
                })

        # Organize inventory data
        inventory = []
        for i in range(len(inventory_type)):
            inventory.append({
                'type': inventory_type[i],
                'count': inventory_count[i],
                'price_per_seat': price_per_seat[i]
            })

        # Create a document to insert into MongoDB
        property_details = {
            'coworking_name': coworking_name,
            'city': city,
            'micromarket': micromarket,
            'name': name,
            'owner_phone': owner_phone,
            'owner_email': owner_email,
            'total_seats': total_seats,
            'current_vacancy': current_vacancy,
            'inventory': inventory,
            'files': files,
            'date': datetime.datetime.now()
        }

        # Insert into MongoDB
        db.fillurdetails.insert_one(property_details)

        flash("Property details submitted successfully.", "success")
    except Exception as e:
        flash(f"Failed to submit property details: {str(e)}", "error")
    
    return redirect(url_for('list_your_space'))



@app.route('/verify_mobile', methods=['GET'])
def verify_mobile():
    token = request.args.get('code')
    client_id = os.environ.get('CLIENT_ID')
    client_secret = os.environ.get('CLIENT_SECRET')

    user_details = OTPLessAuthSDK.UserDetail.verify_code(
        token, client_id, client_secret, None
    )

    if user_details.get('success'):
        mobile_number = user_details.get('phone_number').replace("+91", "")
        name = session.get('name')
        email = session.get('email')
        cname = session.get('cname') 

        db.users.update_one(
            {'mobile_number': mobile_number},
            {'$set': {'name': name, 'email': email, 'cname': cname}},
            upsert=True
        )
        flash("Mobile number verified successfully. You can now submit the form.", "success")
    else:
        flash("Failed to verify mobile number. Please try again.", "error")

    return redirect(url_for('index'))

@app.route('/get_cities', methods=['POST'])
def get_cities():
    cities = sorted(db.coworking_spaces.distinct('city'))
    return jsonify(cities)

@app.route('/get_micromarkets', methods=['POST'])
def get_micromarkets():
    selected_city = request.form.get('city')
    micromarkets = sorted(db.coworking_spaces.distinct('micromarket', {'city': selected_city}))
    return jsonify(micromarkets)

@app.route('/get_prices', methods=['POST'])
def get_prices():
    selected_city = request.form.get('city')
    selected_micromarket = request.form.get('micromarket')
    prices = sorted(db.coworking_spaces.distinct('price', {
        'city': selected_city,
        'micromarket': selected_micromarket
    }))
    return jsonify(prices)

@app.route('/T&C.html')
def terms_and_conditions():
    return render_template('T&C.html')


if __name__ == '__main__':
    # Use the PORT environment variable if available, default to 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
