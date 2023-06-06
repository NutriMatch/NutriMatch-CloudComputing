from flask import Flask, jsonify, request
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, db, auth
from config import secret_key
from config import FIREBASE_AUTH_API
from datetime import datetime
from utils import *
import numpy as np
from tensorflow.keras.utils import load_img, img_to_array
from tensorflow.keras.models import load_model
from PIL import Image
import io
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
            'status': False,
            'message': 'Email invalid!',
            'data': None
        }
        return jsonify(response), 400

    # 201: Registration
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

        return jsonify(response), 201
    
    # 401: Email already registered
    except auth.EmailAlreadyExistsError:
        response = {
            'status': False,
            'message': 'Email already registered!',
            'data': None
        }
        return jsonify(response), 401

# CHECK EMAIL
@app.route('/auth/check_email', methods=['POST'])
def check_email():
    email = request.form['email']

    # 400: Email Invalid
    if not is_valid_email(email):
        response = {
            'status': False,
            'message': 'Email invalid!',
            'data': None
        }
        return jsonify(response), 400

    # 409 : Email already registered
    try:
        user = auth.get_user_by_email(email)
        response = {
            'status': False,
            'message': 'Email already registered!',
            'data': None
        }
        return jsonify(response), 409

    # 200: Email can be registered!
    except auth.UserNotFoundError:
        response = {
            'status': True,
            'message': 'Email can be registered!',
            'data': None
        }
        return jsonify(response), 201

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
        user = auth.get_user_by_email(email)
        user_id = user.uid
        access_token = create_access_token_with_claims(email, secret_key)

        # Get user data from Realtime Database
        users_ref = db.reference('users')
        user_data = users_ref.order_by_child('email').equal_to(email).get()

        # Get body measurement data
        body_measurement_ref = db.reference('body_measurements')
        query = body_measurement_ref.order_by_child('user_id').equal_to(list(user_data.keys())[0]).get()

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


# ------------ USER PROFILE --------------
# ACCOUNT SETTINGS
@app.route('/profile/account_settings', methods=['PUT'])
def update_account_settings():
    # Get the user's access token from the request headers
    auth_header = request.headers.get('Authorization')
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
            'status': False,
            'message': 'Invalid token, please re-login',
            'data': None
        }
        return jsonify(response), 401

    access_token = auth_header.split(' ')[1]

    # Verify the access token
    try:
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

    except jwt.exceptions.InvalidTokenError:
        response = {
            'status': False,
            'message': 'Invalid token, please re-login',
            'data': None
        }
        return jsonify(response), 401

# ACCOUNT
@app.route('/profile/account', methods=['PUT'])
def update_account():
    auth_header = request.headers.get('Authorization')
    # 401: Invalid token
    if not auth_header or not auth_header.startswith('Bearer '):
        response = {
            'status': False,
            'message': 'Invalid token!, please re-login',
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

        # 404: User not found
        if not user_data:
            response = {
                'status': False,
                'message': 'User not found!',
                'data': None
            }
            return jsonify(response), 404

        user_id = list(user_data.keys())[0]

        # Update user's fullname and birthday
        fullname = request.form.get('fullname')
        birthday = request.form.get('birthday')

        if not fullname or not birthday:
            response = {
                'status': False,
                'message': 'Fullname and birthday are required fields!',
                'data': None
            }
            return jsonify(response), 400

        # 403: Forbidden
        if user_email != user_data[user_id]['email']:
            response = {
                'status': False,
                'message': 'Forbidden',
                'data': None
            }
            return jsonify(response), 403

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
    
    # 401: Invalid Token
    except jwt.exceptions.InvalidTokenError:
        response = {
            'status': False,
            'message': 'Invalid token, please re-login',
            'data': None
        }
        return jsonify(response), 401

# PASSWORD
@app.route('/profile/password', methods=['PUT'])
def change_password():
    auth_header = request.headers.get('Authorization')

    # 401: Invalid token
    if not auth_header or not auth_header.startswith('Bearer '):
        response = {
            'status': False,
            'message': 'Invalid token! Please re-login',
            'data': None
        }
        return jsonify(response), 401

    access_token = auth_header.split(' ')[1]

    try:
        # Verify the access token
        payload = jwt.decode(access_token, secret_key, algorithms=['HS256'])
        user_email = payload['sub']

        old_password = request.form['old_password']
        new_password = request.form['new_password']

        if not new_password:
            response = {
                'status': False,
                'message': 'New password is required!',
                'data': None
            }
            return jsonify(response), 400

        user = auth.get_user_by_email(user_email)

        if old_password == new_password:
            response = {
                'status': False,
                'message': 'New password must be different from the old password!',
                'data': None
            }
            return jsonify(response), 400

        # Change password
        auth.update_user(user.uid, password=new_password)

        response = {
            'status': True,
            'message': 'Edit success!',
            'data': None
        }
        return jsonify(response), 200

    except jwt.InvalidTokenError:
        response = {
            'status': False,
            'message': 'Invalid token! Please re-login',
            'data': None
        }
        return jsonify(response), 401

    except firebase_admin.auth.UserNotFoundError:
        response = {
            'status': False,
            'message': 'User not found!',
            'data': None
        }
        return jsonify(response), 404
    
    except Exception as e:
        response = {
            'status': False,
            'message': str(e),
            'data': None
        }
        return jsonify(response), 500


# ------------ MASTER --------------
model = load_model('model.h5')

# SCAN NUTRITION
@app.route('/master/scan_nutrition', methods=['POST'])
def scan_nutrition():
    # Get the user's access token from the request headers
    auth_header = request.headers.get('Authorization')
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
        user_query = users_ref.order_by_child('email').equal_to(user_email).get()

        user_id = None
        for key in user_query:
            user_id = key
            break

        if user_id is None:
            response = {
                'status': False,
                'message': 'User not found in the database',
                'data': None
            }
            return jsonify(response), 404

        food_image = request.files['food_image']
        food_weight = float(request.form['food_weight'])

        # Load Image
        img = load_img(io.BytesIO(food_image.read()), target_size=(150, 150))
        x = img_to_array(img)
        x /= 255
        x = np.expand_dims(x, axis=0)
        images = np.vstack([x])

        # ML detection
        classes = model.predict(images, batch_size=1)

        # Detection Confidence
        threshold = 0.85
        class_indices = np.where(classes[0] > threshold)[0]

        # Get Detected Label
        class_labels = get_class_labels(class_indices)

        # 401: Failed to scan
        if len(class_labels) == 0:
            # 401: Failed to scan
            response = {
                'status': False,
                'message': 'Failed to scan food',
                'data': []
            }
            return jsonify(response), 401

        # Calculate nutrition for each label
        foods = []
        for label in class_labels:
            nutrition = get_nutrition_info(label)
            weight = food_weight / len(class_labels)

            protein = round(nutrition['prot'] * weight, 3)
            fat = round(nutrition['fat'] * weight, 3)
            carb = round(nutrition['carbs'] * weight, 3)

            label_info = {
                'food_title': label,
                'nutrition_info': {
                    'weight': weight,
                    'protein': protein,
                    'fat': fat,
                    'carb': carb
                }
            }
            foods.append(label_info)

        # 200: Success
        response = {
            'status': True,
            'message': 'Food Successfully Scanned!',
            'data': foods
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

@app.route('/master/submit_food', methods=['POST'])
def submit_food():
        # Get the user's access token from the request headers
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        response = {
            'status': False,
            'message': 'Invalid access token!',
            'data': None
        }
        return jsonify(response), 401

    access_token = auth_header.split(' ')[1]
        # Get the user's access token from the request headers
    auth_header = request.headers.get('Authorization')
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
        user_query = users_ref.order_by_child('email').equal_to(user_email).get()

        user_id = None
        for key in user_query:
            user_id = key
            break

        if user_id is None:
            response = {
                'status': False,
                'message': 'User not found in the database',
                'data': None
            }
            return jsonify(response), 404

    except KeyError:
        # 401:Unauthorized
        response = {
            'status': False,
            'message': 'Failed to submit!',
            'data': None
        }
        return jsonify(response), 401
    
    food_image = request.files.get('food_image')
    names = []
    weights = []
    proteins = []
    carbs = []
    fats = []

    
    for i in range(len(request.form)):
        name_key = f'food[{i}][name]'
        weight_key = f'food[{i}][weight]'
        protein_key = f'food[{i}][protein]'
        carb_key = f'food[{i}][carb]'
        fat_key = f'food[{i}][fat]'
        
        if all(key in request.form for key in [name_key, weight_key, protein_key, carb_key, fat_key]):
            names.append(request.form[name_key])
            weights.append(request.form[weight_key])
            proteins.append(request.form[weight_key])
            carbs.append(request.form[weight_key])
            fats.append(request.form[weight_key])            

    foods = []
    for name, weight, protein, carb, fat in zip(names, weights, proteins, carbs, fats):
        label_info = {
            'name': name,
            'weight': weight,
            'protein': protein,
            'carb': carb,
            'fat': fat,
        }
        foods.append(label_info)
    
    meal_category = categorize_meal()
    store_food_data(user_id, meal_category, foods)

    response = {
        'status': True,
        'message': 'Food Successfully Submit!',
        'data': None
    }
    return jsonify(response), 200


@app.route('/master/submit_manual', methods=['POST'])
def submit_manual():
    # Get the user's access token from the request headers
    auth_header = request.headers.get('Authorization')
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
        user_query = users_ref.order_by_child('email').equal_to(user_email).get()

        user_id = None
        for key in user_query:
            user_id = key
            break

        if user_id is None:
            response = {
                'status': False,
                'message': 'User not found in the database',
                'data': None
            }
            return jsonify(response), 404

    except KeyError:
        # 401:Unauthorized
        response = {
            'status': False,
            'message': 'Failed to submit!',
            'data': None
        }
        return jsonify(response), 401
    
    food_image = request.files['food_image']
    name = request.form['name']
    weight = request.form['weight']
    calories = request.form['calories']

     # Check if all required fields are present in the request
    if not name or not weight or not calories:
        response = {
            'status': False,
            'message': 'Failed to submit!',
            'data': None
        }
        return jsonify(response), 400

    # Validate weight is a valid integer
    try:
        weight = int(weight)
    except ValueError:
        response = {
            'status': False,
            'message': 'Invalid weight value!',
            'data': None
        }
        return jsonify(response), 400
    
    # Validate calories is a valid integer
    try:
        calories = int(calories)
    except ValueError:
        response = {
            'status': False,
            'message': 'Invalid calories value!',
            'data': None
        }
        return jsonify(response), 400

    meal_category = categorize_meal()
    
    foods = []
    # Calculate nutrient values based on calorie
    protein = round(calories * 0.2 / 4, 3)
    carbs = round(calories * 0.5 / 4, 3)
    fat = round(calories * 0.3 / 9, 3)

    food_info = {
        'food_title': name,
            'nutrition_info': {
                'weight': weight,
                'protein': protein,
                'fat': fat,
                'carb': carbs
        }
    }
    foods.append(food_info)

    store_food_data(user_id, meal_category, foods)  

    # Return success response
    response = {
        'status': True,
        'message': 'Food Successfully Submit!',
        'data': None
    }
    return jsonify(response), 200

# DASHBOARD
@app.route('/master/dashboard', methods=['GET'])
def get_calories_needed():
    auth_header = request.headers.get('Authorization')

    # 401: Invalid token
    if not auth_header or not auth_header.startswith('Bearer '):
        response = {
            'status': False,
            'message': 'Invalid token!, please re-login',
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

        # Data need for calculation
        weight = query[measurement_id]['weight']
        height = query[measurement_id]['height']
        gender = query[measurement_id]['gender']
        activity_level = query[measurement_id]['activity_level']

        # Retrieve user_id
        user_id = list(user_data.keys())[0]
        
        # Calculate calories needed
        age = calculate_age(user_data[user_id]['birthday'])
        calories_needed = calculate_calories_needed(weight, height, age, gender, activity_level)

        if calories_needed is None:
            response = {
                'status': False,
                'message': 'Failed to calculate calories needed',
                'data': None
            }
            return jsonify(response), 500

        # Protein calculation (10-35% total kalori)
        protein = calories_needed * 0.15 / 4

        # Fat calculation (20-35% total kalori)
        fat = calories_needed * 0.25 / 9

        # Carbs calculation (45-65% total kalori)
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
            'message': 'Success get dashboard',
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


# Initialize Flask
app.debug = True
print('Debugging message')
CORS(app)

if __name__ == '__main__':
    app.run()
