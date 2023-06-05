import re
import jwt
from datetime import datetime
from firebase_admin import db, auth

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
    elif current_time < "15:00:00":
        return "lunch"
    else:
        return "dinner"

def store_food_data(user_id, meal_category, foods):
    user_food_ref = db.reference('user_food')
    new_food_entry = user_food_ref.push()

    new_food_entry.set({
        'user_id': user_id,
        'category': meal_category
    })

    for index, label_info in enumerate(foods):
        food_entry = new_food_entry.child(f'food_{index}')
        food_entry.set(label_info)