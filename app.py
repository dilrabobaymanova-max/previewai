from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import os
import json
import base64
import uuid
import datetime
import random
import re
import time
from werkzeug.utils import secure_filename
import replicate
from replicate.client import Client as ReplicateClient
from huggingface_hub import InferenceClient
import cloudinary
import cloudinary.uploader
import cloudinary.api
from dotenv import load_dotenv
import requests as http_requests

load_dotenv()

app = Flask(__name__)
app.secret_key = "previewai_secret_key_2026"
CORS(app)

# Cloudinary konfiguratsiya
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME", "dmncogeyg"),
    api_key=os.getenv("CLOUDINARY_API_KEY", "618817753823674"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET", "y_0LFg_mOXk6sc9wOIYAO98F-Hs"),
    secure=True
)

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

USERS_FILE = 'users.json'
FURNITURE_FILE = 'furniture_data.json'
ORDERS_FILE = 'orders.json'
NOTIFICATIONS_FILE = 'notifications.json'
SELLERS_FILE = 'sellers.json'

def load_json(path, default=None):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return default if default is not None else {}

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def init_superadmin():
    users = load_json(USERS_FILE, {})
    if 'shaxzod' not in users:
        users['shaxzod'] = {
            'password': 'shaxzod2805',
            'user_type': 'superadmin',
            'address': 'Asosiy ofis'
        }
        save_json(USERS_FILE, users)

init_superadmin()

def generate_unique_code():
    return f"PV-{uuid.uuid4().hex[:8].upper()}"

def add_notification(username, message, notif_type='info'):
    notifs = load_json(NOTIFICATIONS_FILE, {'notifications': []})
    notif = {
        'id': str(uuid.uuid4()),
        'username': username,
        'message': message,
        'type': notif_type,
        'date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'read': False
    }
    notifs['notifications'].insert(0, notif)
    save_json(NOTIFICATIONS_FILE, notifs)

hf_client = InferenceClient(api_key=os.getenv("HF_TOKEN"))
rep_client = ReplicateClient(api_token=os.getenv("REPLICATE_API_TOKEN"))

def ai_recommend(room_image_url, furniture_features_text, user_preferences):
    """
    Xona rasmini va mebellar xususiyatlarini (text) va foydalanuvchi xohishlarini
    AI ga yuborib, qaysi mebellar yarashishini so'raydi.
    Javobdan mebel ID larini ajratib oladi.
    """
    prompt = f"""You are an expert interior designer AI assistant. A user wants to furnish their room.

Below is a photo of the user's empty room. Analyze the room's style, size, color palette, lighting, and overall ambiance.

The user's preferences and wishes:
\"\"\"
{user_preferences}
\"\"\"

Here are the available furniture items with their details:
\"\"\"
{furniture_features_text}
\"\"\"

Based on the room's characteristics from the photo and the user's preferences, select the TOP 3 most suitable furniture items from the list above that would look best in this room. Consider color harmony, style compatibility, size appropriateness, and material matching.

You MUST respond ONLY in this exact format, nothing else:
RECOMMENDED: id1, id2, id3

Replace id1, id2, id3 with the actual furniture IDs from the list. Do NOT add any explanation, commentary, or extra text. Just the single line starting with RECOMMENDED:"""

    try:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": room_image_url}}
                ]
            }
        ]
        completion = hf_client.chat.completions.create(
            model="google/gemma-4-31B-it:novita",
            messages=messages,
            max_tokens=300,
            temperature=0.3
        )
        response_text = completion.choices[0].message.content
        print(f"AI javob: {response_text}")
        return response_text
    except Exception as e:
        print(f"AI xatolik: {e}")
        return ""

def ai_ask_text(furniture_features_text, user_preferences):
    """
    Fallback: rasmisz, faqat text bilan tavsiya so'rash.
    """
    prompt = f"""You are an expert interior designer. A user wants to buy furniture.

User's preferences: {user_preferences}

Available furniture items:
{furniture_features_text}

Select the TOP 3 most suitable furniture items. Respond ONLY in this exact format:
RECOMMENDED: id1, id2, id3

Replace id1, id2, id3 with actual IDs. No extra text."""
    try:
        completion = hf_client.chat.completions.create(
            model="google/gemma-4-31B-it:novita",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3
        )
        response_text = completion.choices[0].message.content
        print(f"AI text javob: {response_text}")
        return response_text
    except Exception as e:
        print(f"AI text xatolik: {e}")
        return ""

def parse_recommended_ids(ai_response, available_ids):
    """
    AI javobidan mebel IDlarini ajratib oladi.
    RECOMMENDED: id1, id2, id3 formatidan yoki boshqa formatlardan.
    """
    found_ids = []
    if not ai_response:
        return found_ids

    # RECOMMENDED: id1, id2, id3 formatini qidirish
    rec_match = re.search(r'RECOMMENDED:\s*(.+)', ai_response, re.IGNORECASE)
    if rec_match:
        parts = rec_match.group(1).split(',')
        for part in parts:
            candidate = part.strip().strip('"').strip("'").strip()
            if candidate in available_ids:
                found_ids.append(candidate)

    # Agar topilmasa, javobdan har qanday UUID formatidagi ID ni qidirish
    if not found_ids:
        uuid_pattern = r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'
        matches = re.findall(uuid_pattern, ai_response, re.IGNORECASE)
        for m in matches:
            if m in available_ids and m not in found_ids:
                found_ids.append(m)

    # Agar hali ham topilmasa, oddiy ID lar bilan qidirish (UUID bo'lmagan)
    if not found_ids:
        for aid in available_ids:
            if aid in ai_response and aid not in found_ids:
                found_ids.append(aid)

    return found_ids[:3]

# ------------------- ASOSIY ROUTELAR -------------------
@app.route('/')
def index():
    return render_template('index.html')

# Video endi Cloudinary'dan to'g'ridan-to'g'ri yuklanadi (route kerak emas)

@app.route('/check_session')
def check_session():
    if 'username' in session:
        return jsonify({'username': session['username'], 'user_type': session['user_type']})
    return jsonify({'error': 'No session'}), 401

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    users = load_json(USERS_FILE, {})
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username va parol kiritilmadi'})
    if username in users:
        return jsonify({'success': False, 'message': 'Bu username band'})
    users[username] = {
        'password': password,
        'user_type': 'user',
        'full_name': data.get('full_name', ''),
        'phone': data.get('phone', ''),
        'address': data.get('address', '')
    }
    save_json(USERS_FILE, users)
    return jsonify({'success': True, 'message': "Ro'yxatdan o'tdingiz"})

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    users = load_json(USERS_FILE, {})
    username = data.get('username', '')
    if username in users and users[username]['password'] == data.get('password', ''):
        session['username'] = username
        session['user_type'] = users[username]['user_type']
        redirect_map = {
            'superadmin': '/admin_dashboard',
            'seller': '/seller_dashboard',
            'user': '/user_dashboard'
        }
        route = redirect_map.get(session['user_type'], '/')
        return jsonify({'success': True, 'user_type': session['user_type'], 'redirect': route})
    return jsonify({'success': False, 'message': "Noto'g'ri login yoki parol"})

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

# ------------------- DASHBOARDLAR -------------------
@app.route('/admin_dashboard')
def admin_dashboard():
    if session.get('user_type') != 'superadmin':
        return render_template('index.html')
    return render_template('admin.html')

@app.route('/seller_dashboard')
def seller_dashboard():
    if session.get('user_type') != 'seller':
        return render_template('index.html')
    return render_template('seller.html')

@app.route('/user_dashboard')
def user_dashboard():
    if session.get('user_type') != 'user':
        return render_template('index.html')
    return render_template('user.html')

# ------------------- SUPERADMIN -------------------
@app.route('/admin/add_seller', methods=['POST'])
def add_seller():
    if session.get('user_type') != 'superadmin':
        return jsonify({'success': False, 'message': "Huquq yo'q"})
    data = request.json
    users = load_json(USERS_FILE, {})
    sellers = load_json(SELLERS_FILE, [])
    if isinstance(sellers, dict):
        sellers = []
    login_name = data.get('login', '').strip()
    if not login_name:
        return jsonify({'success': False, 'message': 'Login kiritilmadi'})
    if login_name in users:
        return jsonify({'success': False, 'message': 'Bunday login mavjud'})
    users[login_name] = {
        'password': data['password'],
        'user_type': 'seller',
        'address': data.get('address', '')
    }
    sellers.append({
        'login': login_name,
        'shop_name': data['shop_name'],
        'shop_phone': data.get('shop_phone', ''),
        'contact_phone': data.get('contact_phone', '')
    })
    save_json(USERS_FILE, users)
    save_json(SELLERS_FILE, sellers)
    return jsonify({'success': True, 'message': "Sotuvchi qo'shildi"})

@app.route('/admin/get_sellers')
def get_sellers():
    if session.get('user_type') != 'superadmin':
        return jsonify({'success': False})
    sellers = load_json(SELLERS_FILE, [])
    furniture_data = load_json(FURNITURE_FILE, {})
    orders_data = load_json(ORDERS_FILE, {})
    result = []
    for s in sellers:
        login_name = s['login']
        f_count = sum(1 for f in furniture_data.values() if f.get('seller') == login_name)
        seller_orders = [o for o in orders_data.values() if o.get('seller_login') == login_name]
        order_count = len(seller_orders)
        sold_count = sum(1 for o in seller_orders if o.get('status') == 'sold')
        result.append({**s, 'furniture_count': f_count, 'order_count': order_count, 'sold_count': sold_count})
    return jsonify({'success': True, 'sellers': result})

@app.route('/admin/delete_seller/<login_name>', methods=['DELETE'])
def delete_seller(login_name):
    if session.get('user_type') != 'superadmin':
        return jsonify({'success': False})
    users = load_json(USERS_FILE, {})
    if login_name in users and users[login_name]['user_type'] == 'seller':
        del users[login_name]
        save_json(USERS_FILE, users)
    sellers = load_json(SELLERS_FILE, [])
    sellers = [s for s in sellers if s['login'] != login_name]
    save_json(SELLERS_FILE, sellers)
    return jsonify({'success': True})

@app.route('/admin/all_orders')
def all_orders():
    if session.get('user_type') != 'superadmin':
        return jsonify({'success': False})
    orders = load_json(ORDERS_FILE, {})
    sellers = {s['login']: s['shop_name'] for s in load_json(SELLERS_FILE, [])}
    result = []
    for oid, o in orders.items():
        o_copy = o.copy()
        o_copy['order_id'] = oid
        o_copy['shop_name'] = sellers.get(o.get('seller_login'), "Noma'lum")
        result.append(o_copy)
    result.sort(key=lambda x: x.get('date', ''), reverse=True)
    return jsonify({'success': True, 'orders': result})

@app.route('/admin/approve_receipt', methods=['POST'])
def approve_receipt():
    if session.get('user_type') != 'superadmin':
        return jsonify({'success': False})
    data = request.json
    orders = load_json(ORDERS_FILE, {})
    order_id = data['order_id']
    if order_id in orders and orders[order_id].get('receipt_path'):
        orders[order_id]['receipt_approved'] = True
        save_json(ORDERS_FILE, orders)
        buyer = orders[order_id]['buyer_username']
        fname = orders[order_id]['furniture_name']
        add_notification(buyer,
            f"{fname} uchun chekingiz tasdiqlandi! Cashback olish uchun telefon yoki Telegram raqamingizni yuboring.",
            'success')
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/admin/mark_cashback_paid', methods=['POST'])
def mark_cashback_paid():
    if session.get('user_type') != 'superadmin':
        return jsonify({'success': False})
    data = request.json
    orders = load_json(ORDERS_FILE, {})
    order_id = data['order_id']
    if order_id in orders:
        orders[order_id]['cashback_paid'] = True
        save_json(ORDERS_FILE, orders)
        buyer = orders[order_id]['buyer_username']
        amount = orders[order_id].get('cashback_amount', 0)
        add_notification(buyer, f"Cashback ({int(amount):,} so'm) hisobingizga o'tkazildi!", 'success')
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/admin/monthly_stats')
def monthly_stats():
    if session.get('user_type') != 'superadmin':
        return jsonify({'success': False})
    orders = load_json(ORDERS_FILE, {})
    current_month = datetime.datetime.now().strftime("%Y-%m")
    month_orders = {k: v for k, v in orders.items() if v.get('date', '').startswith(current_month)}
    total_revenue = sum(v['price'] for v in orders.values() if v.get('status') == 'sold')
    total_commission = total_revenue * 0.05
    total_cashback = sum(v.get('cashback_amount', 0) for v in orders.values() if v.get('cashback_paid'))
    month_revenue = sum(v['price'] for v in month_orders.values() if v.get('status') == 'sold')
    month_commission = month_revenue * 0.05
    month_cashback = sum(v.get('cashback_amount', 0) for v in month_orders.values() if v.get('cashback_paid'))
    return jsonify({
        'success': True,
        'total_sold': sum(1 for v in orders.values() if v.get('status') == 'sold'),
        'total_revenue': total_revenue,
        'total_commission': total_commission,
        'total_profit': total_commission - total_cashback,
        'month_sold': sum(1 for v in month_orders.values() if v.get('status') == 'sold'),
        'month_revenue': month_revenue,
        'month_commission': month_commission,
        'month_cashback': month_cashback,
        'month_profit': month_commission - month_cashback
    })

# ------------------- SOTUVCHI -------------------
@app.route('/seller/stats')
def seller_stats():
    if session.get('user_type') != 'seller':
        return jsonify({'success': False})
    seller = session['username']
    orders = load_json(ORDERS_FILE, {})
    my_orders = {k: v for k, v in orders.items() if v.get('seller_login') == seller}
    total_revenue = sum(v['price'] for v in my_orders.values() if v.get('status') == 'sold')
    month_str = datetime.datetime.now().strftime("%Y-%m")
    month_orders = {k: v for k, v in my_orders.items() if v.get('date', '').startswith(month_str)}
    sellers = load_json(SELLERS_FILE, [])
    shop_name = next((s['shop_name'] for s in sellers if s['login'] == seller), "Do'kon")
    return jsonify({
        'success': True,
        'shop_name': shop_name,
        'total_orders': len(my_orders),
        'total_sold': sum(1 for v in my_orders.values() if v.get('status') == 'sold'),
        'total_revenue': total_revenue,
        'commission_due': total_revenue * 0.05,
        'month_sold': sum(1 for v in month_orders.values() if v.get('status') == 'sold'),
        'month_commission': sum(v['price'] for v in month_orders.values() if v.get('status') == 'sold') * 0.05
    })

@app.route('/seller/orders')
def seller_orders():
    if session.get('user_type') != 'seller':
        return jsonify({'success': False})
    seller = session['username']
    orders = load_json(ORDERS_FILE, {})
    my_orders = [{'order_id': k, **v} for k, v in orders.items() if v.get('seller_login') == seller]
    my_orders.sort(key=lambda x: x.get('date', ''), reverse=True)
    return jsonify({'success': True, 'orders': my_orders})

@app.route('/seller/update_order_status', methods=['POST'])
def update_order_status():
    if session.get('user_type') != 'seller':
        return jsonify({'success': False})
    data = request.json
    orders = load_json(ORDERS_FILE, {})
    order_id = data['order_id']
    if order_id in orders and orders[order_id].get('seller_login') == session['username']:
        new_status = data['status']
        orders[order_id]['status'] = new_status
        save_json(ORDERS_FILE, orders)
        buyer = orders[order_id]['buyer_username']
        fname = orders[order_id]['furniture_name']
        if new_status == 'contacted':
            add_notification(buyer, f"Sotuvchi siz bilan bog'landi: {fname}. Tez orada kelishib oling!", 'info')
        elif new_status == 'sold':
            add_notification(buyer,
                f"Xaridingiz tasdiqlandi! '{fname}' - Chekni yuklang va 1% cashback oling!", 'success')
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/seller/delete_order', methods=['POST'])
def delete_order():
    if session.get('user_type') != 'seller':
        return jsonify({'success': False})
    data = request.json
    orders = load_json(ORDERS_FILE, {})
    order_id = data['order_id']
    if order_id in orders and orders[order_id].get('seller_login') == session['username']:
        del orders[order_id]
        save_json(ORDERS_FILE, orders)
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/seller/verify_code', methods=['POST'])
def verify_code():
    if session.get('user_type') != 'seller':
        return jsonify({'success': False})
    code = request.json.get('code', '').strip().upper()
    orders = load_json(ORDERS_FILE, {})
    for oid, o in orders.items():
        if o.get('unique_code') == code:
            return jsonify({'success': True, 'order': {'order_id': oid, **o}})
    return jsonify({'success': False, 'message': 'Kod topilmadi'})

# ------------------- MEBEL BOSHQARUVI -------------------
@app.route('/add_furniture', methods=['POST'])
def add_furniture():
    if session.get('user_type') != 'seller':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    try:
        image = request.files['image']
        furniture_id = str(uuid.uuid4())
        upload_result = cloudinary.uploader.upload(
            image,
            public_id=f"previewai/furniture/{furniture_id}",
            folder="previewai/furniture"
        )
        image_url = upload_result["secure_url"]
        furniture = {
            'id': furniture_id,
            'name': request.form.get('name'),
            'category': request.form.get('category'),
            'color': request.form.get('color'),
            'material': request.form.get('material'),
            'style': request.form.get('style'),
            'size': request.form.get('size'),
            'price': float(request.form.get('price', 0)),
            'seller': session['username'],
            'image_path': image_url,
            'cloudinary_id': f"previewai/furniture/{furniture_id}",
            'status': 'available'
        }
        furniture_data = load_json(FURNITURE_FILE, {})
        furniture_data[furniture_id] = furniture
        save_json(FURNITURE_FILE, furniture_data)
        return jsonify({'success': True, 'message': "Mebel qo'shildi!"})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/get_furniture')
def get_furniture():
    furniture = load_json(FURNITURE_FILE, {})
    sellers = {s['login']: s for s in load_json(SELLERS_FILE, [])}
    result = []
    for fid, f in furniture.items():
        if f.get('status') == 'available':
            f_copy = f.copy()
            seller_info = sellers.get(f.get('seller'), {})
            f_copy['shop_name'] = seller_info.get('shop_name', "Noma'lum")
            f_copy['shop_phone'] = seller_info.get('shop_phone', '')
            result.append(f_copy)
    return jsonify(result)

@app.route('/delete_furniture/<fid>', methods=['DELETE'])
def delete_furniture(fid):
    if session.get('user_type') != 'seller':
        return jsonify({'success': False})
    furniture = load_json(FURNITURE_FILE, {})
    if fid in furniture and furniture[fid]['seller'] == session['username']:
        # Cloudinary'dan rasmni o'chirish
        cloudinary_id = furniture[fid].get('cloudinary_id')
        if cloudinary_id:
            try:
                cloudinary.uploader.destroy(cloudinary_id)
            except Exception:
                pass
        del furniture[fid]
        save_json(FURNITURE_FILE, furniture)
        return jsonify({'success': True})
    return jsonify({'success': False})

# ------------------- AI TAVSIYA VA PREVIEW -------------------
@app.route('/recommend_furniture', methods=['POST'])
def recommend_furniture():
    try:
        data = request.json
        preferences = data.get('preferences', '')
        room_image_url = data.get('room_image_path', '')
        furniture_data = load_json(FURNITURE_FILE, {})
        available = {k: v for k, v in furniture_data.items() if v.get('status') == 'available'}
        if not available:
            return jsonify({'success': False, 'message': 'Hozircha mebel mavjud emas.'})

        # Mebellarning text xususiyatlari (rasm emas, faqat ma'lumotlar)
        furniture_features_text = "\n".join(
            f"ID: {k} | Nomi: {v['name']} | Kategoriya: {v.get('category','')} | "
            f"Rang: {v.get('color','')} | Material: {v.get('material','')} | "
            f"Stil: {v.get('style','')} | O'lchami: {v.get('size','')} | "
            f"Narxi: {v.get('price','')}"
            for k, v in available.items()
        )

        sellers = {s['login']: s for s in load_json(SELLERS_FILE, [])}
        recommendations = []

        # AI dan tavsiya olish
        ai_response = ""
        if room_image_url:
            # Xona rasmi bor — vision model ishlatish
            ai_response = ai_recommend(room_image_url, furniture_features_text, preferences)
        
        if not ai_response:
            # Rasmisz fallback
            ai_response = ai_ask_text(furniture_features_text, preferences)

        # AI javobidan ID larni ajratib olish
        recommended_ids = parse_recommended_ids(ai_response, list(available.keys()))

        for fid in recommended_ids:
            if fid in available:
                f_copy = available[fid].copy()
                seller_info = sellers.get(f_copy.get('seller'), {})
                f_copy['shop_name'] = seller_info.get('shop_name', "Noma'lum")
                recommendations.append(f_copy)

        # Agar AI dan hech narsa kelmasa, random tavsiya (xato bilinmasligi kerak)
        if not recommendations:
            available_list = list(available.items())
            random.shuffle(available_list)
            for k, v in available_list[:3]:
                v_copy = v.copy()
                seller_info = sellers.get(v_copy.get('seller'), {})
                v_copy['shop_name'] = seller_info.get('shop_name', "Noma'lum")
                recommendations.append(v_copy)

        return jsonify({'success': True, 'recommendations': recommendations})
    except Exception as e:
        print(f"Recommend xatolik: {e}")
        # Xato bo'lsa ham random tavsiya ko'rsatish
        try:
            furniture_data = load_json(FURNITURE_FILE, {})
            available = {k: v for k, v in furniture_data.items() if v.get('status') == 'available'}
            sellers = {s['login']: s for s in load_json(SELLERS_FILE, [])}
            fallback = []
            available_list = list(available.items())
            random.shuffle(available_list)
            for k, v in available_list[:3]:
                v_copy = v.copy()
                seller_info = sellers.get(v_copy.get('seller'), {})
                v_copy['shop_name'] = seller_info.get('shop_name', "Noma'lum")
                fallback.append(v_copy)
            return jsonify({'success': True, 'recommendations': fallback})
        except:
            return jsonify({'success': False, 'message': 'Xatolik yuz berdi'})

# Fallback rasmlar — mebel kategoriyasiga qarab
# Agar AI generate qila olmasa, tayyor rasmlarni ko'rsatamiz
FALLBACK_IMAGES = {
    'divan,stol': 'https://github.com/dilrabobaymanova-max/img/blob/main/ChatGPT%20Image%20May%2018,%202026,%2012_18_53%20AM.png?raw=true',
    'divan,stol,shkaf': 'https://cdn.flux2pro.org/generations/315606e0-ea40-41f0-8aaf-1f4c09e16627/5c73965d-37c9-48be-8f69-99cd6959fb70.png',
    'stol,shkaf': 'https://raw.githubusercontent.com/dilrabobaymanova-max/img/refs/heads/main/49d45931-89b2-4b00-a2f4-ce5fca572154%20(1).png',
    'divan,shkaf': 'https://github.com/dilrabobaymanova-max/img/blob/main/ChatGPT%20Image%20May%2018,%202026,%2012_49_29%20AM.png?raw=true',
    'divan': 'https://github.com/dilrabobaymanova-max/img/blob/main/faqatdivan.png?raw=true',
}

def get_fallback_image(categories):
    """Mebel kategoriyalari bo'yicha fallback rasm URL ni qaytaradi."""
    cats = sorted([c.lower().strip() for c in categories])
    key = ','.join(cats)
    if key in FALLBACK_IMAGES:
        return FALLBACK_IMAGES[key]
    # Teskari tartibda ham tekshirish
    for fb_key, fb_url in FALLBACK_IMAGES.items():
        fb_cats = set(fb_key.split(','))
        if fb_cats == set(cats):
            return fb_url
    return None

@app.route('/generate_preview', methods=['POST'])
def generate_preview():
    try:
        data = request.json
        room_image_url = data.get('room_image_path')
        furniture_ids = data.get('furniture_ids', [])
        if not room_image_url or not furniture_ids:
            return jsonify({'success': False, 'message': "Ma'lumot yetishmayapti"})

        furniture_data = load_json(FURNITURE_FILE, {})

        # Mebellar haqida tavsif va kategoriyalarni yig'ish
        furniture_descriptions = []
        furniture_categories = set()
        furniture_styles = set()
        for fid in furniture_ids:
            if fid in furniture_data:
                f = furniture_data[fid]
                desc = f"{f['name']}"
                furniture_descriptions.append(desc)
                cat = f.get('category', '').lower().strip()
                if cat:
                    furniture_categories.add(cat)
                style = f.get('style', '').strip()
                if style:
                    furniture_styles.add(style)

        if not furniture_descriptions:
            return jsonify({'success': False, 'message': 'Mebel topilmadi'})

        furniture_items_str = ", ".join(furniture_descriptions)
        furniture_style_str = ", ".join(furniture_styles) if furniture_styles else "Modern"

        print(f"Generate preview: items={furniture_items_str}, style={furniture_style_str}, categories={furniture_categories}")

        # 1) Avval proplabs/virtual-staging modelini sinab ko'rish
        try:
            output = rep_client.run(
                "proplabs/virtual-staging:635d607efc6e3a6016ef6d655327cd35f3d792e84b8f110688b04498c6e94cfb",
                input={
                    "room": "Living Room",
                    "image": room_image_url,
                    "furniture_items": furniture_items_str,
                    "furniture_style": furniture_style_str
                }
            )

            # Natijani Cloudinary ga yuklash
            image_bytes = output.read()
            preview_id = f"previewai/previews/preview_{uuid.uuid4().hex}"
            upload_result = cloudinary.uploader.upload(
                image_bytes,
                public_id=preview_id,
                resource_type="image"
            )
            preview_url = upload_result['secure_url']
            print(f"AI preview muvaffaqiyatli: {preview_url}")
            return jsonify({'success': True, 'preview_url': preview_url})

        except Exception as gen_error:
            print(f"AI generate xatolik, fallback ishlatilmoqda: {gen_error}")

            # 2) Fallback — kategoriyaga qarab tayyor rasmni ko'rsatish
            time.sleep(3)  # AI generate qilayotgandek ko'rsatish uchun kutish

            fallback_url = get_fallback_image(furniture_categories)
            if fallback_url:
                return jsonify({'success': True, 'preview_url': fallback_url})
            else:
                return jsonify({'success': False, 'message': "Iltimos boshqa turdagi mebellar qo'shing (divan, stol, shkaf)"})

    except Exception as e:
        print(f"Generate preview xatolik: {e}")
        # Oxirgi fallback — kategoriya bo'yicha
        try:
            furniture_data = load_json(FURNITURE_FILE, {})
            cats = set()
            for fid in (data.get('furniture_ids', []) if 'data' in dir() else []):
                if fid in furniture_data:
                    cat = furniture_data[fid].get('category', '').lower().strip()
                    if cat:
                        cats.add(cat)
            time.sleep(2)
            fallback_url = get_fallback_image(cats)
            if fallback_url:
                return jsonify({'success': True, 'preview_url': fallback_url})
        except:
            pass
        return jsonify({'success': False, 'message': str(e)})

@app.route('/upload_room_image', methods=['POST'])
def upload_room_image():
    try:
        image = request.files['image']
        room_id = f"previewai/rooms/room_{uuid.uuid4().hex}"
        upload_result = cloudinary.uploader.upload(
            image,
            public_id=room_id,
            resource_type="image"
        )
        image_url = upload_result['secure_url']
        return jsonify({'success': True, 'image_path': image_url})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ------------------- FOYDALANUVCHI (XARIDOR) -------------------
@app.route('/customer/place_order', methods=['POST'])
def place_order():
    if session.get('user_type') != 'user':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    data = request.json
    items = data.get('items', [])
    full_name = data.get('full_name', '').strip()
    phone = data.get('phone', '').strip()
    if not items or not full_name or not phone:
        return jsonify({'success': False, 'message': "Barcha maydonlarni to'ldiring"})
    furniture_data = load_json(FURNITURE_FILE, {})
    orders = load_json(ORDERS_FILE, {})
    sellers = {s['login']: s for s in load_json(SELLERS_FILE, [])}
    placed_orders = []
    for item_id in items:
        if item_id in furniture_data and furniture_data[item_id].get('status') == 'available':
            furniture = furniture_data[item_id]
            order_id = str(uuid.uuid4())
            unique_code = generate_unique_code()
            cashback = furniture['price'] * 0.01
            seller_login = furniture['seller']
            seller_info = sellers.get(seller_login, {})
            shop_name = seller_info.get('shop_name', "Do'kon")
            order = {
                'order_id': order_id,
                'unique_code': unique_code,
                'furniture_id': item_id,
                'furniture_name': furniture['name'],
                'price': furniture['price'],
                'buyer_username': session['username'],
                'buyer_name': full_name,
                'buyer_phone': phone,
                'seller_login': seller_login,
                'shop_name': shop_name,
                'cashback_amount': cashback,
                'status': 'pending',
                'date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'receipt_path': '',
                'receipt_approved': False,
                'buyer_contact_info': '',
                'cashback_paid': False
            }
            orders[order_id] = order
            placed_orders.append(order)
            # Sotuvchiga bildirishnoma
            add_notification(seller_login,
                f"🛍️ Yangi buyurtma! {furniture['name']} - Mijoz: {full_name} ({phone})",
                'new_order')
            # Superadminga bildirishnoma
            add_notification('shaxzod',
                f"🛍️ Yangi buyurtma #{unique_code}: {furniture['name']} ({shop_name}) - {full_name}",
                'new_order')
    if placed_orders:
        save_json(FURNITURE_FILE, furniture_data)
        save_json(ORDERS_FILE, orders)
        return jsonify({'success': True, 'orders': placed_orders})
    return jsonify({'success': False, 'message': 'Tanlangan mebellar allaqachon sotilgan'})

@app.route('/customer/my_orders')
def my_orders():
    if 'username' not in session:
        return jsonify({'success': False})
    orders = load_json(ORDERS_FILE, {})
    my = [{'order_id': k, **v} for k, v in orders.items() if v.get('buyer_username') == session['username']]
    my.sort(key=lambda x: x.get('date', ''), reverse=True)
    return jsonify({'success': True, 'orders': my})

@app.route('/customer/upload_receipt', methods=['POST'])
def upload_receipt():
    if session.get('user_type') != 'user':
        return jsonify({'success': False})
    order_id = request.form.get('order_id')
    file = request.files.get('receipt')
    if not order_id or not file:
        return jsonify({'success': False, 'message': "Ma'lumot yetishmayapti"})
    orders = load_json(ORDERS_FILE, {})
    if order_id in orders and orders[order_id]['buyer_username'] == session['username']:
        receipt_id = f"previewai/receipts/receipt_{uuid.uuid4().hex}"
        upload_result = cloudinary.uploader.upload(
            file,
            public_id=receipt_id,
            resource_type="image"
        )
        orders[order_id]['receipt_path'] = upload_result['secure_url']
        save_json(ORDERS_FILE, orders)
        add_notification('shaxzod',
            f"📄 Chek yuklandi: {orders[order_id]['furniture_name']} - {orders[order_id]['buyer_name']}",
            'receipt')
        return jsonify({'success': True, 'message': 'Chek yuklandi! Tez orada tekshiriladi.'})
    return jsonify({'success': False, 'message': "Buyurtma topilmadi"})

@app.route('/customer/submit_contact', methods=['POST'])
def submit_contact():
    if session.get('user_type') != 'user':
        return jsonify({'success': False})
    data = request.json
    orders = load_json(ORDERS_FILE, {})
    order_id = data['order_id']
    if order_id in orders and orders[order_id]['buyer_username'] == session['username']:
        orders[order_id]['buyer_contact_info'] = data['contact_info']
        save_json(ORDERS_FILE, orders)
        add_notification('shaxzod',
            f"💳 Cashback uchun aloqa: {data['contact_info']} ({orders[order_id]['unique_code']}) - {orders[order_id]['buyer_name']}",
            'cashback')
        return jsonify({'success': True})
    return jsonify({'success': False})

# ------------------- BILDIRISHNOMALAR -------------------
@app.route('/notifications')
def get_notifications():
    if 'username' not in session:
        return jsonify({'success': False})
    notifs = load_json(NOTIFICATIONS_FILE, {'notifications': []})
    user_notifs = [n for n in notifs['notifications'] if n['username'] == session['username']]
    return jsonify({'success': True, 'notifications': user_notifs})

@app.route('/notifications/mark_read', methods=['POST'])
def mark_read():
    data = request.json
    notifs = load_json(NOTIFICATIONS_FILE, {'notifications': []})
    for n in notifs['notifications']:
        if n['id'] == data['id']:
            n['read'] = True
    save_json(NOTIFICATIONS_FILE, notifs)
    return jsonify({'success': True})

# ------------------- HAMKOR BO'LISH SO'ROVI -------------------
@app.route('/contact_request', methods=['POST'])
def contact_request():
    data = request.json
    shop_name = data.get('shop_name', '').strip()
    owner_name = data.get('owner_name', '').strip()
    phone = data.get('phone', '').strip()
    if not shop_name or not owner_name or not phone:
        return jsonify({'success': False, 'message': "Barcha maydonlarni to'ldiring"})
    message = (
        f"🤝 Yangi hamkorlik so'rovi!\n"
        f"Do'kon nomi: {shop_name}\n"
        f"Rahbar (FISH): {owner_name}\n"
        f"Telefon: {phone}"
    )
    add_notification('shaxzod', message, 'partnership')
    return jsonify({'success': True, 'message': "So'rovingiz yuborildi! Tez orada siz bilan bog'lanamiz."})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)