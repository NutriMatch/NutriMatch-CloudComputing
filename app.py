from flask import Flask, jsonify, request
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, db, auth, storage
from config import secret_key
from config import FIREBASE_AUTH_API
from utils import *
import numpy as np
from tensorflow.keras.utils import load_img, img_to_array
from tensorflow.keras.models import load_model
from PIL import Image
import datetime
import io
import requests
import jwt

# Initialize Firebase
cred = credentials.Certificate('serviceAccountKey1.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://capstone-project-nutrimatch-default-rtdb.asia-southeast1.firebasedatabase.app/',
    'storageBucket': 'capstone-project-nutrimatch.appspot.com'
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
            weight = round(food_weight / len(class_labels), 2)

            protein = round(nutrition['prot'] * weight, 2)
            fat = round(nutrition['fat'] * weight, 2)
            carb = round(nutrition['carbs'] * weight, 2)

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

# SUMBIT MANUAL
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

        # Request
        food_image = request.files['food_image']
        name = request.form['name']
        weight = request.form['weight']
        calories = request.form['calories']

        # 400: Bad Request
        if not name or not weight or not calories:
            response = {
                'status': False,
                'message': 'Failed to submit!',
                'data': None
            }
            return jsonify(response), 400

        try:
            weight = float(weight)
            calories = float(calories)
        except ValueError:
            response = {
                'status': False,
                'message': 'Invalid value!',
                'data': None
            }
            return jsonify(response), 400

        # Calculate nutrient values based on calorie
        proteins = round(calories * 0.2 / 4, 2)
        carbs = round(calories * 0.5 / 4, 2)
        fats = round(calories * 0.3 / 9, 2)

        meal_category = categorize_meal()

        foods = []
        food_info = {
            'name': name,
            'weight': weight,
            'protein': proteins,
            'fat': fats,
            'carb': carbs
        }
        foods.append(food_info)

        meal_category = categorize_meal()

        food_title = name

        # Upload and retrieve image URL
        image_url = upload_food_image(food_image)

        # Store data to Realtime Database
        store_food_data(user_id, image_url, meal_category, calories, proteins, fats, carbs, foods, food_title)

        # 200: Success
        response = {
            'status': True,
            'message': 'Food Successfully Submit!',
            'data': None
        }
        return jsonify(response), 200

    # 401: Unauthorized
    except KeyError:
        response = {
            'status': False,
            'message': 'Failed to submit!',
            'data': None
        }
        return jsonify(response), 401

# SUBMIT FOOD 
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
    
        # Request
        food_image = request.files['food_image']
        names = []
        weights = []
        proteins = []
        fats = []
        carbs = []

        for i in range(len(request.form)):
            name_key = f'food[{i}][name]'
            weight_key = f'food[{i}][weight]'
            protein_key = f'food[{i}][protein]'
            fat_key = f'food[{i}][fat]'
            carb_key = f'food[{i}][carb]'
            
            if all(key in request.form for key in [name_key, weight_key, protein_key, fat_key, carb_key]):
                names.append(request.form[name_key])
                weights.append(float(request.form[weight_key]))
                proteins.append(float(request.form[protein_key]))
                fats.append(float(request.form[fat_key]))            
                carbs.append(float(request.form[carb_key]))
                
        foods = []
        total_calories = 0
        total_protein = 0
        total_fat = 0
        total_carb = 0

        for name, weight, protein, fat, carb in zip(names, weights, proteins, fats, carbs):
            label_info = {
                'name': name,
                'weight': weight,
                'protein': protein,
                'fat': fat,
                'carb': carb,
            }
            foods.append(label_info)

            # Calculate calories for the current food item
            calories = (protein * 4) + (carb * 4) + (fat * 9)
            total_calories += calories
            total_protein += protein
            total_fat += fat
            total_carb += carb

        # 400: Bad Request
        if not names or not weights or not proteins or not fats or not carbs:
            response = {
                'status': False,
                'message': 'All fields are required!',
                'data': None
            }
            return jsonify(response), 400

        meal_category = categorize_meal()
        
        food_title = ', '.join(names)

        # Upload and retrieve image URL            
        image_url = upload_food_image(food_image)

        # Store data to Realtime Database
        store_food_data(user_id, image_url, meal_category, total_calories, total_protein, total_fat, total_carb, foods, food_title)

        # Return a success response
        response = {
            'status': True,
            'message': 'Food submitted successfully!',
            'data': None
        }
        return jsonify(response)

    # 400: Bad Request
    except KeyError:
        response = {
            'status': False,
            'message': 'Failed to submit!',
            'data': None
        }
        return jsonify(response), 400

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

        # Data needed for calculation
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

        # Get today's date
        today = datetime.date.today().isoformat()

        # Get user food entries for today
        user_food_ref = db.reference('user_food')
        user_food_data = user_food_ref.order_by_child('user_id').equal_to(user_id).get()

        # Filter the entries for today
        today_entries = [
            entry for entry in user_food_data.values()
            if entry.get('user_id') == user_id and get_date_from_timestamp(entry.get('timestamp')) == today
        ]

        # Calculate the sum of calories, proteins, fats, and carbs for today's entries
        today_calories = round(sum(entry.get('calories', 0) for entry in today_entries), 2)
        today_proteins = round(sum(entry.get('proteins', 0) for entry in today_entries), 2)
        today_fats = round(sum(entry.get('fats', 0) for entry in today_entries), 2)
        today_carbs = round(sum(entry.get('carbs', 0) for entry in today_entries), 2)

        # Calculation
        # (protein: 10-35% calorie, fat: 20-35%, carbs: 45-65%)
        protein = round(calories_needed * 0.2 / 4, 2)
        carbohydrate = round(calories_needed * 0.5 / 4, 2)
        fat = round(calories_needed * 0.3 / 9, 2)

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
            'calories': {
                'target': calories_needed,
                'current': today_calories
            },
            'protein': {
                'target': protein,
                'current': today_proteins
            },
            'fat': {
                'target': fat,
                'current': today_fats
            },
            'carbs': {
                'target': carbohydrate,
                'current': today_carbs
            }
        }

        history_food = {
            'breakfast': [],
            'lunch': [],
            'dinner': []
        }

        for entry in today_entries:
            category = entry.get('category')
            food_info = {
                'image_url': entry.get('image_url'),
                'title': entry.get('title'),
                'nutrition_info': {
                    'calories': entry.get('calories', 0),
                    'protein': entry.get('proteins', 0),
                    'fat': entry.get('fats', 0),
                    'carbs': entry.get('carbs', 0)
                }
            }

            if category == 'breakfast':
                history_food['breakfast'].append(food_info)
            elif category == 'lunch':
                history_food['lunch'].append(food_info)
            elif category == 'dinner':
                history_food['dinner'].append(food_info)
        
        # 200: Success
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

    # 401: Unauthorized
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
