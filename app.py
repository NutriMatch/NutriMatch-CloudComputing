from flask import Flask, jsonify, request
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, db, auth
from config import secret_key
from config import FIREBASE_AUTH_API
from datetime import datetime
from utils import is_valid_email, create_access_token_with_claims, calculate_age, calculate_calories_needed
import requests
import jwt

# Initialize Firebase
cred = credentials.Certificate('serviceAccountKey1.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://capstone-project-nutrimatch-default-rtdb.asia-southeast1.firebasedatabase.app/'
})

# Initialize Flask
app = Flask(__name__)
CORS(app)

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
    gender = request.form['gender']
    activity_level = request.form['activity_level']

    # 400: Email invalid
    if not is_valid_email(email):
        response = {
            'response': {
                'value': {
                    'status': False,
                    'message': 'Email invalid!',
                    'data': None
                }
            }
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
            'response': {
                'value': {
                    'status': False,
                    'message': 'Email already registered!',
                    'data': None
                }
            }
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
            'response': {
                'value': {
                    'status': False,
                    'message': 'Email and password are required fields.',
                    'data': None
                }
            }
        }
        return jsonify(response), 400

    # 400: Invalid email
    if not is_valid_email(email):
        response = {
            'response': {
                'value': {
                    'status': False,
                    'message': 'Email Invalid!',
                    'data': None
                }
            }
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
            'response':{
                'value': {
                    'status': False,
                    'message': 'Email or password not found!',
                    'data': None
                }
            }
        }
        return jsonify(response), 401


# ------------ USER PROFILE --------------
# ACCOUNT SETTINGS
@app.route('/profile/account_settings', methods=['PUT'])
def update_account_settings():
    # Get the user's access token from the request headers
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        response = {
            'response': {
                'value': {
                    'status': False,
                    'message': 'Invalid access token!',
                    'data': None
                }
            }
        }
        return jsonify(response), 401

    access_token = auth_header.split(' ')[1]
    try:
        # Verify the access token
        payload = jwt.decode(access_token, secret_key, algorithms=['HS256'])
        user_email = payload['sub']

        # Get user data from Realtime Database
        users_ref = db.reference('users')
        user_data = users_ref.order_by_child('email').equal_to(user_email).get()

        # Get body measurement data
        body_measurement_ref = db.reference('body_measurements')
        query = body_measurement_ref.order_by_child('user_id').equal_to(list(user_data.keys())[0]).get()
        measurement_id = list(query.keys())[0]

        # Request
        height = request.form.get('height')
        weight = request.form.get('weight')
        gender = request.form.get('gender')
        activity_level = request.form.get('activity_level')

        # 400: Form are required
        if not height or not weight or not gender or not activity_level:
            response = {
                'status': False,
                'message': 'Form are required!',
                'data': None
            }
            return jsonify(response), 400

        height = int(height)
        weight = int(weight)

        body_measurement_ref.child(measurement_id).update({
            'height': height,
            'weight': weight,
            'gender': gender,
            'activity_level': activity_level
        })
        response = {
            'status': True,
            'message': 'Settings body\'s measurements success!',
            'data': None
        }
        return jsonify(response), 200

    except jwt.ExpiredSignatureError:
        response = {
            'status': False,
            'message': 'Expired access token!',
            'data': None
        }
        return jsonify(response), 401

    except jwt.InvalidTokenError:
        response = {
            'status': False,
            'message': 'Invalid access token!',
            'data': None
        }
        return jsonify(response), 401

    except Exception as e:
        response = {
            'status': False,
            'message': 'An error occurred while updating account settings.',
            'data': None
        }
        return jsonify(response), 500

# PROFILE
@app.route('/profile', methods=['GET'])
def get_profile():
    auth_header = request.headers.get('Authorization')
    # 401: Invalid token
    if not auth_header or not auth_header.startswith('Bearer '):
        response = {
            'response': {
                'value': {
                    'status': False,
                    'message': 'Invalid token, please re-login',
                    'data': None
                }
            }
        }
        return jsonify(response), 401

    access_token = auth_header.split(' ')[1]

    try:
        # Verify the access token
        payload = jwt.decode(access_token, secret_key, algorithms=['HS256'])
        user_email = payload['sub']

        # Get user data from Realtime Database
        users_ref = db.reference('users')
        user_data = users_ref.order_by_child('email').equal_to(user_email).get()

        user_id = list(user_data.keys())[0]

        # Get body measurement data
        body_measurement_ref = db.reference('body_measurements')
        query = body_measurement_ref.order_by_child('user_id').equal_to(user_id).get()
        measurement_id = list(query.keys())[0]

        # 200: Success
        user_response = {
            'id': user_id,
            'fullname': user_data[user_id]['fullname'],
            'email': user_email,
            'birthday': user_data[user_id]['birthday'],
            'body_measurement': {
                'height': query[measurement_id]['height'],
                'weight': query[measurement_id]['weight'],
                'activity_level': query[measurement_id]['activity_level'],
                'gender': query[measurement_id]['gender']
            }
        }
        response = {
            'status': True,
            'message': 'Success get profile data',
            'data': user_response
        }
        return jsonify(response), 200

    except Exception as e:
        response = {
            'status': False,
            'message': 'An error occurred while retrieving the user profile.',
            'data': None
        }
        return jsonify(response), 500

# ACCOUNT
@app.route('/profile/account', methods=['PUT'])
def update_account():
    auth_header = request.headers.get('Authorization')
    # 401: Invalid token
    if not auth_header or not auth_header.startswith('Bearer '):
        response = {
            'response': {
                'value': {
                    'status': False,
                    'message': 'Invalid token!, please re-login',
                    'data': None
                }
            }
        }
        return jsonify(response), 401

    access_token = auth_header.split(' ')[1]

    try:
        # Verify the access token
        payload = jwt.decode(access_token, secret_key, algorithms=['HS256'])
        user_email = payload['sub']

        # Get user data from Realtime Database
        users_ref = db.reference('users')
        user_data = users_ref.order_by_child('email').equal_to(user_email).get()
        user_id = list(user_data.keys())[0]

        # 404: User not found
        if not user_data:
            response = {
                'response': {
                    'value': {
                        'status': False,
                        'message': 'User not found!',
                        'data': None
                    }
                }
            }
            return jsonify(response), 404

        # Update user's fullname and birthday
        fullname = request.form.get('fullname')
        birthday = request.form.get('birthday')

        # 400: Fullname and birthday are required
        if not fullname or not birthday:
            response = {
                'status': False,
                'message': 'Fullname and birthday are required fields!',
                'data': None
            }
            return jsonify(response), 400

        # 201: Success
        # Update user data in Realtime Database
        users_ref.child(user_id).update({
            'fullname': fullname,
            'birthday': birthday
        })
        response = {
            'status': True,
            'message': 'Edit success!',
            'data': None
        }
        return jsonify(response), 201
    
    except auth.AuthError as e:
        # 403: Forbidden
        if e.code == 'insufficient-permission':
            response = {
                'status': False,
                'message': 'Forbidden',
                'data': None
            }
            return jsonify(response), 403
        

# ------------ MASTER --------------
# DASHBOARD
@app.route('/master/dashboard', methods=['GET'])
def get_calories_needed():
    auth_header = request.headers.get('Authorization')

    # Check if the access token is provided
    if not auth_header or not auth_header.startswith('Bearer '):
        response = {
            'status': False,
            'message': 'Invalid access token!',
            'data': None
        }
        return jsonify(response), 401

    access_token = auth_header.split(' ')[1]

    try:
        # Verify the access token
        payload = jwt.decode(access_token, secret_key, algorithms=['HS256'])
        user_email = payload['sub']

        # Get user data from Realtime Database
        users_ref = db.reference('users')
        user_data = users_ref.order_by_child('email').equal_to(user_email).get()

        # Get body measurement data
        body_measurement_ref = db.reference('body_measurements')
        query = body_measurement_ref.order_by_child('user_id').equal_to(list(user_data.keys())[0]).get()
        measurement_id = list(query.keys())[0]

        # Extract necessary data for calorie calculation
        weight = query[measurement_id]['weight']
        height = query[measurement_id]['height']
        gender = query[measurement_id]['gender']
        activity_level = query[measurement_id]['activity_level']

        # Modify the code to retrieve user_id
        user_id = list(user_data.keys())[0]
        
        # Calculate calories needed
        age = calculate_age(user_data[list(user_data.keys())[0]]['birthday'])
        calories_needed = calculate_calories_needed(weight, height, age, gender, activity_level)

        # Hitung kebutuhan protein (10-35% total kalori)
        protein = calories_needed * 0.15 / 4

        # Hitung kebutuhan lemak (20-35% total kalori)
        fat = calories_needed * 0.25 / 9

        # Hitung kebutuhan karbohidrat (45-65% total kalori)
        carbohydrate = calories_needed * 0.55 / 4

        # 200: Success
        user_response = {
            'id': user_id,
            'fullname': user_data[user_id]['fullname'],
            'email': user_email,
            'birthday': user_data[user_id]['birthday'],
            'body_measurement': {
                'height': query[measurement_id]['height'],
                'weight': query[measurement_id]['weight'],
                'activity_level': query[measurement_id]['activity_level'],
                'gender': query[measurement_id]['gender']
            }
        }

        graph = {
            'calories':{
                'target': calories_needed,
                'current': None
            },
            'protein': {
                'target': protein,
                'current': None
            },
            'fat': {
                'target': fat,
                'current': None
            },
            'carbs': {
                'target': carbohydrate,
                'current': None
            }
        }

        history_food = {
            'breakfast':[{
                'get_makanan_user': None #get makanan user 
            }],
            'lunch':[{
                'get_makanan_user': None #get makanan user 
            }],
            'dinner':[{
                'get_makanan_user': None #get makanan user 
            }]
        }

        response = {
            'status': True,
            'message': 'Calories needed calculated successfully.',
            'data': {
                'user': user_response,
            },
            'graph': graph,
            'history_food': history_food
        }
        return jsonify(response), 200

    except jwt.exceptions.InvalidTokenError:
        response = {
            'status': False,
            'message': 'Invalid token, please re-login',
            'data': None
        }
        return jsonify(response), 401

    except Exception as e:
        response = {
            'status': False,
            'message': 'Failed to calculate calories needed.',
            'data': str(e)
        }
        return jsonify(response), 500


# Initialize Flask
app.debug = True
print('Debugging message')
CORS(app)

if __name__ == '__main__':
    app.run()
