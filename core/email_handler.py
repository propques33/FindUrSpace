# email_handler.py
from flask_mail import Mail, Message
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,KeepTogether
from reportlab.lib.units import inch
from reportlab.lib.colors import black, lightgrey
from io import BytesIO
from PyPDF2 import PdfWriter, PdfReader
import os
from flask import current_app, flash
from PIL import Image as PILImage
import requests
from integrations.google_drive_integration import upload_pdf_to_google_drive, send_pdf_via_cunnekt, authenticate_google_drive, get_temp_pdfs_folder_id  # Import functions

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

# Helper function to fetch and resize an image
def fetch_and_resize_image(url, width=6 * inch, height=4 * inch):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            image = BytesIO(response.content)
            return Image(image, width=width, height=height)
    except Exception as e:
        print(f"Error fetching image from {url}: {e}")
    return None

# Generate PDF with property details
# Adjusted PDF generation function to handle layout_images
# def generate_property_pdf(properties, doc, styles):
#     elements = []

#     # Define updated styles with larger font size and appropriate spacing
#     styles.add(ParagraphStyle(name='EnhancedHeading', fontName='Helvetica-Bold', fontSize=32, spaceAfter=24))
#     styles.add(ParagraphStyle(name='EnhancedNormal', fontName='Helvetica', fontSize=24, spaceAfter=16, leading=28))

#     for i, property_data in enumerate(properties, start=1):
#         elements.append(Paragraph(f"Option {i}", styles['EnhancedHeading']))
#         elements.append(Spacer(1, 12))
        
#         coworking_name = property_data.get('coworking_name', 'Unknown Property')
#         print(f"Generating PDF for property: {coworking_name}")
#         elements.append(Paragraph(f"Name: {coworking_name}", styles['EnhancedNormal']))
        
#         city = property_data.get('city', 'Unknown City')
#         micromarket = property_data.get('micromarket', 'Unknown Micromarket')
#         elements.append(Spacer(1, 16))
#         elements.append(Paragraph(f"Address: {micromarket}, {city}", styles['EnhancedNormal']))
        
#         # Inventory details
#         inventory = property_data.get('inventory', [])
#         if inventory:
#             elements.append(Spacer(1, 16))
#             elements.append(Paragraph("Inventory Details:", styles['EnhancedNormal']))
#             for item in inventory:
#                 inventory_type = item.get('type', 'N/A')
#                 price_per_seat = item.get('price_per_seat', '0')
#                 elements.append(Paragraph(
#                     f"- {inventory_type}: ₹{price_per_seat} price per seat", 
#                     styles['EnhancedNormal']
#                 ))
#         else:
#             elements.append(Paragraph("Inventory details not available.", styles['EnhancedNormal']))
#         elements.append(Spacer(1, 16))

#         # Access layout_images from property data
#         layout_images = property_data.get('layout_images', [])

#         if layout_images:
#             elements.append(Spacer(1, 8))
#             elements.append(Paragraph("Property Images:", styles['EnhancedNormal']))

#             # Fetch and display up to two images per property
#             image_row = []
#             for img_url in layout_images[:2]:  # Limit to the first two images
#                 img = fetch_and_resize_image(img_url)
#                 if img:
#                     image_row.append(img)

#             if image_row:
#                 image_table = Table([image_row], colWidths=[8 * inch] * len(image_row))
#                 image_table.setStyle(TableStyle([
#                     ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
#                     ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
#                     ('LEFTPADDING', (0, 0), (-1, -1), 6),
#                     ('RIGHTPADDING', (0, 0), (-1, -1), 6),
#                 ]))
#                 elements.append(image_table)
#             else:
#                 elements.append(Paragraph("No images available.", styles['EnhancedNormal']))
#         else:
#             elements.append(Paragraph("No images available.", styles['EnhancedNormal']))

#         elements.append(Spacer(1, 20))  # Add a gap between properties

#     doc.build(elements)

def generate_property_pdf(properties, doc, styles):
    elements = []

    # Define updated styles with larger font size and appropriate spacing
    styles.add(ParagraphStyle(name='EnhancedHeading', fontName='Helvetica-Bold', fontSize=32, spaceAfter=24))
    styles.add(ParagraphStyle(name='EnhancedNormal', fontName='Helvetica', fontSize=24, spaceAfter=16, leading=28))

    for i, property_data in enumerate(properties, start=1):
        property_elements = []

        # Add property details to the current property elements
        property_elements.append(Paragraph(f"Option {i}", styles['EnhancedHeading']))
        property_elements.append(Spacer(1, 12))
        
        coworking_name = property_data.get('coworking_name', 'Unknown Property')
        print(f"Generating PDF for property: {coworking_name}")
        property_elements.append(Paragraph(f"Name: {coworking_name}", styles['EnhancedNormal']))
        
        city = property_data.get('city', 'Unknown City')
        micromarket = property_data.get('micromarket', 'Unknown Micromarket')
        property_elements.append(Spacer(1, 16))
        property_elements.append(Paragraph(f"Address: {micromarket}, {city}", styles['EnhancedNormal']))
        
        # Inventory details
        inventory = property_data.get('inventory', [])
        if inventory:
            property_elements.append(Spacer(1, 16))
            property_elements.append(Paragraph("Inventory Details:", styles['EnhancedNormal']))
            for item in inventory:
                inventory_type = item.get('type', 'N/A')
                price_per_seat = item.get('price_per_seat', '0')
                property_elements.append(Paragraph(
                    f"- {inventory_type}: ₹{price_per_seat} price per seat", 
                    styles['EnhancedNormal']
                ))
        else:
            property_elements.append(Paragraph("Inventory details not available.", styles['EnhancedNormal']))
        property_elements.append(Spacer(1, 16))

        # Access layout_images from property data
        layout_images = property_data.get('layout_images', [])

        if layout_images:
            property_elements.append(Spacer(1, 8))
            property_elements.append(Paragraph("Property Images:", styles['EnhancedNormal']))

            # Fetch and display up to two images per property
            image_row = []
            for img_url in layout_images[:2]:  # Limit to the first two images
                img = fetch_and_resize_image(img_url)
                if img:
                    image_row.append(img)

            if image_row:
                image_table = Table([image_row], colWidths=[8 * inch] * len(image_row))
                image_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ]))
                property_elements.append(image_table)
            else:
                property_elements.append(Paragraph("No images available.", styles['EnhancedNormal']))
        else:
            property_elements.append(Paragraph("No images available.", styles['EnhancedNormal']))

        property_elements.append(Spacer(1, 20))  # Add a gap between properties

        # Use KeepTogether to ensure all elements for the property stay on one page
        elements.append(KeepTogether(property_elements))

    doc.build(elements)


# Send email and WhatsApp with the same PDF
def send_email_and_whatsapp_with_pdf1(to_email, name, contact, properties):
    try:
        # Ensure the contact number is valid and formatted correctly
        if len(contact) == 10:
            contact = '91' + contact
        elif not contact.startswith('91') or len(contact) != 12:
            raise ValueError("Invalid contact number format")
        

        # Load the predesigned PDF and extract static pages
        static_pdf_path = os.path.join(current_app.root_path, 'static', 'pdffin.pdf')
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

        base_url = "https://findurspace.tech" 

        seen_links = set()
        workspace_links = ""
        for property_data in properties:
            if not property_data.get('has_amenities'):
                continue  # Skip link generation for properties without amenities

            coworking_name = property_data.get('coworking_name', 'N/A').replace(' ', '%20')
            city = property_data.get('city', 'N/A').replace(' ', '%20')
            micromarket = property_data.get('micromarket', 'N/A').replace(' ', '%20')
            inventory = property_data.get('inventory', [])

            if inventory:
                for item in inventory:
                    inventory_type = item.get('type', '')
                    if inventory_type in ["Day pass", "Dedicated desk", "Private cabin", "Meeting rooms"]:
                        inventory_type_encoded = inventory_type.replace(' ', '%20')
                        base_link = f"{base_url}/flexspace/{city}/{micromarket}/{coworking_name}?inventoryType={inventory_type_encoded}"

                        if inventory_type in ["Private cabin", "Meeting rooms"] and item.get('room_details'):
                            for room in item['room_details']:
                                seating = room.get('seating_capacity')
                                if seating:
                                    full_link = f"{base_link}&seating={seating}"
                                    label = f"{coworking_name} - {inventory_type} {seating} Seater"
                                    if full_link not in seen_links:
                                        workspace_links += f"<br><a href='{full_link}'>{label}</a>"
                                        seen_links.add(full_link)
                        else:
                            if base_link not in seen_links:
                                label = f"{coworking_name} - {inventory_type}"
                                workspace_links += f"<br><a href='{base_link}'>{label}</a>"
                                seen_links.add(base_link)

        greeting = f"Dear {name}" if name else "Hi"

        # Compose email body with links
        email_body = f"""
        <strong>{greeting},</strong><br><br>
        <strong>Please find attached the details of the properties you requested:</strong><br><br>
        If you're interested in maximizing the benefits of the above properties at no cost, please reply to this email with 'Deal.' We will assign an account manager to coordinate with you.<br><br>
        <strong>Workspace Links:</strong><br>
        {workspace_links}
        """
        # Create email message and attach the combined PDF
        message = Message(subject='Your Property Data',
                          recipients=[to_email],
                          bcc=['enterprise.propques@gmail.com', 'buzz@propques.com', 'thomas@propques.com'],
                          html=email_body)
        message.attach("property_data.pdf", "application/pdf", combined_pdf_buffer.read())

        # Send the email
        mail.send(message)

        # Upload the same PDF to Google Drive
        creds = authenticate_google_drive()
        combined_pdf_buffer.seek(0)  # Reset buffer before uploading to Google Drive
        shareable_link = upload_pdf_to_google_drive(combined_pdf_buffer, creds, "property_data.pdf")

        # Send the PDF via WhatsApp using the Cunnekt API
        if shareable_link:
            send_pdf_via_cunnekt(shareable_link, contact)
        else:
            print("Failed to generate Google Drive shareable link for the PDF.")
        
        return True, None  # Successfully sent email and WhatsApp

    except Exception as e:
        print(f"Failed to send email and WhatsApp: {e}")
        return False, str(e)

