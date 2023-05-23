from flask import Flask, jsonify, request
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from firebase_admin import auth
import re

# Initialize Firebase
cred = credentials.Certificate('serviceAccountKey1.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://capstone-project-nutrimatch-default-rtdb.asia-southeast1.firebasedatabase.app/'
})

# Initialize Flask
app = Flask(__name__)
# CORS(app)

def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

# REGISTER
@app.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    fullname = data.get('fullname')
    birthday = data.get('birthday')
    email = data.get('email')
    password = data.get('password')

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
        auth.create_user(email=email, password=password)
        
        # Add user's data to Realtime Database
        users_ref = db.reference('users')
        new_user_ref = users_ref.push()
        new_user_ref.set({
            'fullname': fullname,
            'birthday': birthday,
            'email': email
        })

        response = {
            'status': True,
            'message': 'Register success!',
            'data': {
                'token': None
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

@app.route('/auth/', methods=['POST'])
def account_settings():
    data = request.get_json()
    height = data.get('height')
    weight = data.get('weight')
    gender = data.get('gender')
    activity_level = data.get('activity_level')


if __name__ == '__main__':
    app.run()
