from flask import Flask
import os
import secrets
from dotenv import load_dotenv
from core.database import get_db
from core.routes import core_bp  # Importing routes from core/routes.py

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# MongoDB setup with debugging
try:
    db = get_db()
    db.command("ping")  # Perform a quick test to check the connection
    print("Database connected successfully!")
except Exception as e:
    print(f"Database connection failed: {e}")

# Store db instance in app config if needed
app.config['db'] = db

# Register routes (from core/routes.py)
app.register_blueprint(core_bp)

if __name__ == '__main__':
    # Debug mode to help troubleshoot issues
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1']
    
    # Use the PORT environment variable if available, default to 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
