import re
import jwt
import requests
from datetime import datetime
from config import FIREBASE_AUTH_API
from firebase_admin import db, auth, storage, initialize_app

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

def calculate_age(birthday):
    birth_date = datetime.strptime(birthday, '%Y-%m-%d').date()
    today = datetime.today().date()
    age = today.year - birth_date.year
    if today.month < birth_date.month or (today.month == birth_date.month and today.day < birth_date.day):
        age -= 1
    return age

def calculate_calories_needed(weight, height, age, gender, activity_level):
    # Constants for calculating calories
    Male_BMR_Constant = 66
    Female_BMR_Constant = 655
    Male_Weight_Factor = 13.75
    Female_Weight_Factor = 9.56
    Male_Height_Factor = 5
    Female_Height_Factor = 1.8
    Male_Age_Factor = 6.75
    Female_Age_Factor = 4.7

    if gender == 'M':
        bmr = (
            Male_BMR_Constant
            + (Male_Weight_Factor * weight)
            + (Male_Height_Factor * height)
            - (Male_Age_Factor * age)
        )
    elif gender == 'F':
        bmr = (
            Female_BMR_Constant
            + (Female_Weight_Factor * weight)
            + (Female_Height_Factor * height)
            - (Female_Age_Factor * age)
        )
    else:
        return None
    
    if activity_level == 'L':
        calories_needed = bmr * 1.2 
    elif activity_level == 'M':
        calories_needed = bmr * 1.55 
    elif activity_level == 'H':
        calories_needed = bmr * 1.9 
    else:
        return None

    return calories_needed

def get_nutrition_info(label):
    ref = db.reference('food_nutrients/' + label)
    foods = ref.get()
    return foods

def get_class_labels(class_indices):
    class_labels = ["ayam", "nasi", "telur", "brokoli", "ikan", "jeruk", "mie", "roti", "tahu", "tempe"]
    return [class_labels[idx] for idx in class_indices]

def categorize_meal():
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    
    # Categorize the meal based on the time of day
    if current_time < "10:00:00":
        return "breakfast"
    elif current_time < "18:00:00":
        return "lunch"
    else:
        return "dinner"

def store_food_data(user_id, image_url, meal_category, calories, proteins, fats, carbs, foods, food_title):
    user_food_ref = db.reference('user_food')
    new_food_entry = user_food_ref.push()

    timestamp = datetime.now().isoformat()

    new_food_entry.set({
        'user_id': user_id,
        'title': food_title,
        'image_url': image_url,
        'category': meal_category,
        'calories': calories,
        'proteins': proteins,
        'fats': fats,
        'carbs': carbs,
        'timestamp': timestamp
    })

    for index, label_info in enumerate(foods):
        food_entry = new_food_entry.child(f'food_{index}')
        food_entry.set(label_info)

def upload_food_image(file):
    bucket = storage.bucket()

    file_name = file.filename
    blob = bucket.blob(file_name)
    blob.upload_from_file(file)
    
    # Return the public URL of the uploaded image
    image_url = blob.public_url
    
    return image_url

def get_date_from_timestamp(timestamp):

    if timestamp is None:
        return None
    try:
        date = datetime.fromisoformat(timestamp)
        return date.date().isoformat()
    except (ValueError, TypeError):
        return None

def verify_old_password(email, password):
    request_data = {
        'email': email,
        'password': password,
        'returnSecureToken': False
    }

    response = requests.post(FIREBASE_AUTH_API, json=request_data)
    response_data = response.json()

    if 'idToken' in response_data:
        return True
    else:
        return False
