from flask import Flask
import os
import secrets
from dotenv import load_dotenv
from flask_mail import Mail
from core.database import get_db
from core.routes import core_bp  # Importing routes from core/routes.py

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Flask-Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'findurspace1@gmail.com'
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')  # Fetch from environment variable
app.config['MAIL_DEFAULT_SENDER'] = 'findurspace1@gmail.com'

# Initialize Flask-Mail
mail = Mail(app)

# MongoDB setup
db = get_db()
app.config['db'] = db  # Store the db instance in app config for global use

# Register routes (from core/routes.py)
app.register_blueprint(core_bp)

if __name__ == '__main__':
    # Debug mode based on environment variables
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1']
    
    # Use the PORT environment variable if available, default to 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
