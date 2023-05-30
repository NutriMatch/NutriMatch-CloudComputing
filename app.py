from flask import Flask, jsonify, request
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, db, auth
from config import secret_key
from config import FIREBASE_AUTH_API
import requests
import re
import jwt

# Initialize Firebase
cred = credentials.Certificate('serviceAccountKey1.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://capstone-project-nutrimatch-default-rtdb.asia-southeast1.firebasedatabase.app/'
})

# Initialize Flask
app = Flask(__name__)
CORS(app)

def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

def create_access_token_with_claims(identity, secret_key):
    additional_claims = {
        'custom_key': 'hctamirtun'
    }
    payload = {
        'sub': identity,
        **additional_claims
    }
    access_token = jwt.encode(payload, secret_key, algorithm='HS256')
    return access_token

# ------------ AUTH --------------
# REGISTER
@app.route('/auth/register', methods=['POST'])
def register():
    fullname = request.form['fullname']
    birthday = request.form['birthday']
    email = request.form['email']
    password = request.form['password']
    height = int(request.form['height'])
    weight = int(request.form['weight'])
    gender = int(request.form['gender'])
    activity_level = int(request.form['activity_level'])

    # 400: Email invalid
    if not is_valid_email(email):
        response = {
            'status': False,
            'message': 'Email invalid!',
            'data': None
        }
        return jsonify(response), 400

    # 200: Registration
    try:
        # Create authentication 
        user = auth.create_user(email=email, password=password)
        
        # Add user's data to Realtime Database
        users_ref = db.reference('users')
        new_user_ref = users_ref.push()
        new_user_ref.set({
            'fullname': fullname,
            'birthday': birthday,
            'email': email
        })

        # Generate access token
        access_token = create_access_token_with_claims(email, secret_key)

        # Store body measurement data
        body_measurement_ref = db.reference('body_measurements')
        new_measurement_ref = body_measurement_ref.push()
        new_measurement_ref.set({
            'user_id': new_user_ref.key,
            'height': height,
            'weight': weight,
            'gender': gender,
            'activity_level': activity_level
        })

        response = {
            'status': True,
            'message': 'Register success!',
            'data': {
                'token': access_token
            }
        }

        return jsonify(response), 200
    
    # 401: Email already registered
    except auth.EmailAlreadyExistsError:
        response = {
            'status': False,
            'message': 'Email already registered!',
            'data': None
        }
        return jsonify(response), 401


# LOGIN
@app.route('/auth/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']

    # 400: All fields required
    if not email or not password:
        response = {
            'status': False,
            'message': 'Email and password are required fields.',
            'data': None
        }
        return jsonify(response), 400

    # 400: Invalid email
    if not is_valid_email(email):
        response = {
            'status': False,
            'message': 'Email Invalid!',
            'data': None
        }
        return jsonify(response), 400

    # 200: Success
    # Authenticate with Firebase
    payload = {
        'email': email,
        'password': password,
        'returnSecureToken': True
    }

    response = requests.post(FIREBASE_AUTH_API, json=payload)
    data = response.json()

    if response.status_code == 200:
        # Login successful
        user = auth.get_user_by_email(email)
        user_id = user.uid

        access_token = create_access_token_with_claims(email, secret_key)

        # Get user data from Realtime Database
        users_ref = db.reference('users')
        user_data = users_ref.order_by_child('email').equal_to(email).get()

        # Get body measurement data
        body_measurement_ref = db.reference('body_measurements')
        query = body_measurement_ref.order_by_child('user_id').equal_to(list(user_data.keys())[0]).get()

        # User response data
        user_response = {
            'id': user_id,
            'fullname': user_data[list(user_data.keys())[0]]['fullname'],
            'email': email,
            'birthday': user_data[list(user_data.keys())[0]]['birthday'],
            'body_measurement': {
                'height': query[list(query.keys())[0]]['height'],
                'weight': query[list(query.keys())[0]]['weight'],
                'activity_level': query[list(query.keys())[0]]['activity_level'],
                'gender': query[list(query.keys())[0]]['gender']
            }
        }

        response = {
            'status': True,
            'message': 'Login success!',
            'data': {
                'token': access_token,
                'body_measurement_setting': True,
                'user': user_response
            }
        }
        return jsonify(response), 200

    else:
        response = {
            'status': False,
            'message': 'Email or password not found!',
            'data': None
        }
        return jsonify(response), 401


def get_user_id_from_token(token, secret_key):
    try:
        # Decode the token to access the payload
        payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        user_id = payload['sub']  # Assuming the user ID is stored in the 'sub' claim
        return user_id
    
    except jwt.InvalidTokenError:
        # Handle invalid token
        return None
    
# ------------ USER PROFILE --------------
# ACCOUNT SETTING
@app.route('/profile/account_settings', methods=['PUT'])
def update_body_measurement():
    # Get the token from the request headers
    headers = {
    "Content-Type": "application/x-www-form-urlencoded"
}
    
    auth_header = request.headers.get('Authorization')
    if auth_header is None or not auth_header.startswith('Bearer '):
        response = {
            'status': False,
            'message': 'Invalid token',
            'data': None
        }
        return jsonify(response), 401
    
    token = auth_header.split(' ')[1]

    try:
        # Decode the token to access the payload
        # payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        # user_id = payload['sub']  # Assuming the user ID is stored in the 'sub' claim
        
        # Retrieve the body measurement data from the request
        
        height = int(request.form.get('height'))
        weight = int(request.form.get('weight'))
        gender = int(request.form.get('gender'))
        activity_level = int(request.form.get('activity_level'))

        user_id = get_user_id_from_token(token, secret_key)
        if user_id is None:
            response = {
                'status': False,
                'message': 'Invalid token',
                'data': None
                }
            return jsonify(response), 401
        
        # 400: Form are required!
        if not height or not weight or not gender or not activity_level:
            response = {
                'status': False,
                'message': 'Form are required!',
                'data': None
            }
            return jsonify(response), 400
        
        # Update body measurement data in Firebase Realtime Database
        body_measurement_ref = db.reference('body_measurements')
        query = body_measurement_ref.order_by_child('user_id').equal_to(user_id).get()

        for measurement_id in query:
            measurement_ref = body_measurement_ref.child(measurement_id)
            measurement_ref.update({
                'height': height,
                'weight': weight,
                'gender': gender,
                'activity_level': activity_level
        })

        # 200: Success
        response = {
            'status': True,
            'message': 'Body measurements updated successfully.',
            'data': None
        }
        return jsonify(response), 200

    except jwt.InvalidTokenError:
        # Handle invalid token
        response = {
            'status': False,
            'message': 'Invalid token',
            'data': None
        }
        return jsonify(response), 401

    except Exception as e:
        response = {
            'status': False,
            'message': 'Failed to update body measurements.',
            'data': None
        }
        return jsonify(response), 500





# Initialize Flask
app.debug = True
print('Debugging message')
CORS(app)

if __name__ == '__main__':
    app.run()
