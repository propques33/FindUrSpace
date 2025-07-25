from flask import Flask, request, make_response
import os
import secrets
from dotenv import load_dotenv
from flask_mail import Mail
from core.database import get_db
from core.routes import core_bp  # Importing routes from core/routes.py
from admin.admin import admin_bp
from operators.operators import operators_bp
from admin import admin_bp
import razorpay  # ✅ Import Razorpay
import re

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')
# ✅ Use Server-Side Sessions Instead of Cookies
app.config['SESSION_TYPE'] = 'filesystem'  # Stores session on server
app.config['SESSION_PERMANENT'] = False  # Session expires after browser close
app.config['SESSION_USE_SIGNER'] = True  # Signs session cookies for security
# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.zoho.in'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'sales@nextmovein.com'
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')  # Fetch from environment variable
app.config['MAIL_DEFAULT_SENDER'] = 'sales@nextmovein.com'
app.config['GOOGLE_CLIENT_ID'] = os.environ.get('GOOGLE_CLIENT_ID')
app.config['GOOGLE_CLIENT_SECRET'] = os.environ.get('GOOGLE_CLIENT_SECRET')
app.config['API_KEY'] = os.environ.get('API_KEY')




# Initialize Flask-Mail
mail = Mail(app)

# MongoDB setup
db = get_db()
app.config['db'] = db  # Store the db instance in app config for global use

# ✅ Razorpay setup
app.config['RAZORPAY_KEY_ID'] = os.environ.get('RAZORPAY_KEY_ID')
app.config['RAZORPAY_KEY_SECRET'] = os.environ.get('RAZORPAY_KEY_SECRET')
app.config['razorpay_client'] = razorpay.Client(
    auth=(app.config['RAZORPAY_KEY_ID'], app.config['RAZORPAY_KEY_SECRET'])
)

# Register routes (from core/routes.py)
app.register_blueprint(core_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(operators_bp)

# ✅ Register Jinja filter here
def split_camel_case(s):
    return re.sub(r'(?<!^)(?=[A-Z])', ' ', s)

app.jinja_env.filters['split_camel_case'] = split_camel_case

# In your app factory or utils file
def format_inr(value):
    if value is None:
        return "0"
    return f"{value:,.0f}".replace(",", "X").replace("X", ",").replace(",", ",").replace(",", ",").replace(",", ",")

app.jinja_env.filters['inr'] = format_inr

@app.template_filter('indian_number_format')
def indian_number_format(value):
    return "{:,}".format(value).replace(",", "_").replace("_", ",")


if __name__ == '__main__':
    # Debug mode based on environment variables
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1']
    
    # Use the PORT environment variable if available, default to 5000
    port = int(os.environ.get('PORT', 5003))
    app.run(host='0.0.0.0', port=port, debug=False)

@app.after_request
def set_security_headers(response):
    response.headers['Content-Security-Policy'] = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://*; "
    "style-src 'self' 'unsafe-inline' https://*; "
    "img-src 'self' data: https: blob:; "
    "font-src 'self' https://*; "
    "connect-src 'self' https://*; "
    "frame-src https://*; "
    "frame-ancestors 'none';"
)
    # Basic security headers
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = (
        "geolocation=(), microphone=(), camera=(), fullscreen=(), payment=()"
    )

    if request.is_secure:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

    return response






