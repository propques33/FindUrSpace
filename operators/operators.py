from flask import Blueprint, request, session, redirect, url_for, render_template, current_app
from bson import ObjectId  # Correct import

# Define blueprint for operators
operators_bp = Blueprint('operators', __name__, url_prefix='/operators', template_folder='templates')

@operators_bp.route('/login', methods=['GET', 'POST'])
def operators_login():
    if 'operator' in session:
        return redirect(url_for('operators.inventory'))  # Redirect if already logged in
    
    if request.method == 'POST':
        mobile = request.form.get('mobile')  # Get mobile number from form
        db = current_app.config['db']
        
        # Authentication logic based on mobile in fillurdetails collection
        operator = db.fillurdetails.find_one({'owner.phone': mobile})
        
        if operator:
            # Convert ObjectId to string before storing in session
            session['operator'] = str(operator['_id'])
            return redirect(url_for('operators.inventory'))
        else:
            return render_template('operators_login.html', error="Invalid mobile number")
    
    return render_template('operators_login.html')


@operators_bp.route('/logout')
def operators_logout():
    session.pop('operator', None)
    return redirect(url_for('operators.operators_login'))


@operators_bp.route('/inventory', methods=['GET'])
def inventory():
    if 'operator' not in session:
        return redirect(url_for('operators.operators_login'))
    
    db = current_app.config['db']
    
    # Convert the stored string back to ObjectId for querying
    operator_id = ObjectId(session['operator'])  # Convert back to ObjectId

    # Fetch operator's data based on _id
    operator = db.fillurdetails.find_one({'_id': operator_id})

    # Fetch inventory for the logged-in operator based on mobile number
    inventory = db.fillurdetails.find({
        'owner.phone': operator['owner']['phone']
    })
    
    # Pass operator's name and inventory to the template
    return render_template('operators_inventory.html', inventory=inventory, owner_name=operator['owner']['name'])
