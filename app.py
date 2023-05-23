from flask import Flask, jsonify, request
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from firebase_admin import auth
from config import secret_key
import re
import jwt

# Initialize Firebase
cred = credentials.Certificate('serviceAccountKey1.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://capstone-project-nutrimatch-default-rtdb.asia-southeast1.firebasedatabase.app/'
})

# Initialize Flask
app = Flask(__name__)


def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

def create_access_token_with_claims(identity, secret_key):
    additional_claims = {
        'custom_key': 'hctamirtun'  # Tambahkan klaim kustom sesuai kebutuhan Anda
    }
    payload = {
        'sub': identity,
        **additional_claims
    }
    access_token = jwt.encode(payload, secret_key, algorithm='HS256')
    return access_token


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

        # Generate access token
        access_token = create_access_token_with_claims(email, secret_key)

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


if __name__ == '__main__':
    app.run()
