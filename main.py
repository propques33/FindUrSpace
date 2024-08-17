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
import base64
import json
from whatsapp_integration import send_whatsapp_verification
from gsheet_updater import handle_new_property_entry

load_dotenv()

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'project.propques@gmail.com'
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = 'project.propques@gmail.com'

mail = Mail(app)

# MongoDB configuration
client = MongoClient(os.environ.get('MONGO_URI'))
db = client['FindYourSpace']

# Create indexes for efficient querying
db.email_logs.create_index([('email', ASCENDING), ('date', ASCENDING)])

# Load the cleaned CSV data
coworking_data = pd.read_csv('data/coworking_spaces.csv')

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
                          cc=['buzz@propques.com', 'enterprise.propques@gmail.com'],
                          html=f"<strong>Dear {name},</strong><br>"
                               "<strong>Please find attached the details of the properties you requested:</strong><br><br>"
                               "If you're interested in maximizing the benefits of the above properties at no cost, please reply to this email with 'Deal.' We will assign an account manager to coordinate with you.")
        message.attach("property_data.pdf", "application/pdf", combined_pdf_buffer.read())

        mail.send(message)
        return True, combined_pdf_buffer
    except Exception as e:
        flash(f"Failed to send email: {e}", "error")
        return False, None

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

            if property_type == 'coworking':
                data = coworking_data

            filtered_properties = data[(data['city'] == selected_city) &
                                       (data['micromarket'] == selected_micromarket) &
                                       (data['price'] <= float(budget))]
            
            success, pdf_buffer = send_email(email, name, filtered_properties.to_dict('records'))

            if success:
                property_names = ", ".join(filtered_properties['name'].tolist())

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

                if "@gmail.com" in email:
                    email_log = {
                        'email': email,
                        'date': datetime.datetime.now()
                    }
                    db.email_logs.insert_one(email_log)
                
                # Flash the success message only once
                flash("Email sent successfully.", "success")
            else:
                flash("Email limit reached for this Gmail address. Please try again later.", "error")

            return redirect(url_for('index'))

    return render_template('index.html', name=session.get('name'), mobile=session.get('mobile'), 
                           email=session.get('email'), cname=session.get('cname'))

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
    data = coworking_data
    cities = sorted(data['city'].dropna().unique().tolist())
    return jsonify(cities)

@app.route('/get_micromarkets', methods=['POST'])
def get_micromarkets():
    selected_city = request.form.get('city')
    data = coworking_data
    micromarkets = sorted(data[data['city'] == selected_city]['micromarket'].dropna().unique().tolist())
    return jsonify(micromarkets)

@app.route('/get_prices', methods=['POST'])
def get_prices():
    selected_city = request.form.get('city')
    selected_micromarket = request.form.get('micromarket')
    data = coworking_data
    prices = sorted(data[(data['city'] == selected_city) & (data['micromarket'] == selected_micromarket)]['price'].dropna().unique().tolist())
    return jsonify(prices)

if __name__ == '__main__':
    # Use the PORT environment variable if available, default to 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
