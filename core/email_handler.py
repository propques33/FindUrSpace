from flask_mail import Mail, Message
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.units import inch
from io import BytesIO
from PyPDF2 import PdfWriter, PdfReader
import os
from flask import current_app, flash
from PIL import Image as PILImage
import requests

# Initialize Flask-Mail
mail = Mail()

# Fetch image from URL
def fetch_image(url):
    try:
        response = requests.get(url)
        if response.status_code == 200 and 'image' in response.headers['Content-Type']:
            return PILImage.open(BytesIO(response.content))
    except Exception as e:
        print(f"Failed to fetch image from {url}: {e}")
    return None

# Generate PDF with property details
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
            table_data = [[Image(BytesIO(requests.get(p['img1']).content), width=6.0 * inch, height=5.0 * inch),  
                           Spacer(0.5 * inch, 0),
                           Image(BytesIO(requests.get(p['img2']).content), width=6.0 * inch, height=5.0 * inch)]]

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

        elements.append(Spacer(1, 48))  # Add a gap between properties

    doc.build(elements)

# Send email with PDF attachment
def send_email_with_pdf(to_email, name, properties):
    try:
        # Load the predesigned PDF and extract static pages
        static_pdf_path = os.path.join(current_app.root_path, 'static', 'pdffin.pdf')  # Adjusted to use root_path
        static_pdf = PdfReader(static_pdf_path)

        # Keep the page size consistent with the static pages
        static_page_size = (static_pdf.pages[0].mediabox.width, static_pdf.pages[0].mediabox.height)

        # Create a new PDF for the dynamic content
        dynamic_pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(dynamic_pdf_buffer, pagesize=static_page_size, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()

        # Generate the PDF with property details
        generate_property_pdf(properties, doc, styles)
        dynamic_pdf_buffer.seek(0)
        dynamic_pdf = PdfReader(dynamic_pdf_buffer)

        # Merge static and dynamic PDFs
        output_pdf = PdfWriter()

        # Add static pages (pages 1, 2, and 5 from the original PDF)
        output_pdf.add_page(static_pdf.pages[0])
        output_pdf.add_page(static_pdf.pages[1])

        # Add dynamic content (generated property details)
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
                          bcc=['enterprise.propques@gmail.com', 'buzz@propques.com', 'thomas@propques.com'],
                          html=f"<strong>Dear {name},</strong><br>"
                               "<strong>Please find attached the details of the properties you requested:</strong><br><br>"
                               "If you're interested in maximizing the benefits of the above properties at no cost, please reply to this email with 'Deal.' We will assign an account manager to coordinate with you.")
        message.attach("property_data.pdf", "application/pdf", combined_pdf_buffer.read())

        mail.send(message)
        return True, None  # Returning None since the buffer isn't being used outside
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False, str(e)
