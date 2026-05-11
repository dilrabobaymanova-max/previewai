from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import os
import json
import base64
import uuid
import datetime
import random
from werkzeug.utils import secure_filename
import replicate
from openai import OpenAI

app = Flask(__name__)
app.secret_key = "previewai_secret_key_2026"
CORS(app)

UPLOAD_FOLDER = 'static/uploads'
FURNITURE_FOLDER = 'static/furniture'
RECEIPTS_FOLDER = 'static/receipts'
VIDEOS_FOLDER = 'videos'
for folder in [UPLOAD_FOLDER, FURNITURE_FOLDER, RECEIPTS_FOLDER, VIDEOS_FOLDER]:
    os.makedirs(folder, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
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

def ai_ask(text):
    try:
        client = OpenAI(
            base_url="https://router.huggingface.co/v1",
            api_key=os.getenv("HF_TOKEN"),
        )
        completion = client.chat.completions.create(
            model='mistralai/Mistral-7B-Instruct-v0.2',
            messages=[{"role": "user", "content": text}],
            temperature=0.7,
            max_tokens=500
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"AI xatolik: {e}")
        return ""

# ------------------- ASOSIY ROUTELAR -------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/videos/<path:filename>')
def serve_video(filename):
    from flask import send_from_directory
    return send_from_directory(VIDEOS_FOLDER, filename)

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
        filename = str(uuid.uuid4()) + '_' + secure_filename(image.filename)
        image_path = os.path.join(FURNITURE_FOLDER, filename)
        image.save(image_path)
        furniture_id = str(uuid.uuid4())
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
            'image_path': f'/static/furniture/{filename}',
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
        img_path = furniture[fid]['image_path'].replace('/static/', 'static/')
        if os.path.exists(img_path):
            os.remove(img_path)
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
        furniture_data = load_json(FURNITURE_FILE, {})
        available = {k: v for k, v in furniture_data.items() if v.get('status') == 'available'}
        if not available:
            return jsonify({'success': False, 'message': 'Hozircha mebel mavjud emas.'})
        furniture_list = "\n".join(
            f"ID:{k} | Nomi:{v['name']} | Kat:{v.get('category','')} | Rang:{v.get('color','')} | Material:{v.get('material','')} | Narx:{v.get('price','')}"
            for k, v in available.items()
        )
        prompt = f"""Foydalanuvchi xohishlari: {preferences}
Mavjud mebellar:
{furniture_list}
Faqat ro'yxatdagi ID-lardan eng mos 3 tasini quyidagi formatda qaytar:
ID1|Nomi1, ID2|Nomi2, ID3|Nomi3
Hech qanday izoh yozmang."""
        ai_response = ai_ask(prompt)
        recommendations = []
        sellers = {s['login']: s for s in load_json(SELLERS_FILE, [])}
        if ai_response:
            for part in ai_response.split(','):
                part = part.strip()
                if '|' in part:
                    fid = part.split('|', 1)[0].strip()
                    if fid in available:
                        f_copy = available[fid].copy()
                        seller_info = sellers.get(f_copy.get('seller'), {})
                        f_copy['shop_name'] = seller_info.get('shop_name', "Noma'lum")
                        recommendations.append(f_copy)
        if not recommendations:
            for k, v in list(available.items())[:3]:
                v_copy = v.copy()
                seller_info = sellers.get(v_copy.get('seller'), {})
                v_copy['shop_name'] = seller_info.get('shop_name', "Noma'lum")
                recommendations.append(v_copy)
        return jsonify({'success': True, 'recommendations': recommendations})
    except Exception as e:
        print(e)
        return jsonify({'success': False, 'message': str(e)})

@app.route('/generate_preview', methods=['POST'])
def generate_preview():
    try:
        data = request.json
        room_image_path = data.get('room_image_path')
        furniture_ids = data.get('furniture_ids', [])
        if not room_image_path or not furniture_ids:
            return jsonify({'success': False, 'message': "Ma'lumot yetishmayapti"})
        room_full = room_image_path.lstrip('/')
        if not os.path.exists(room_full):
            return jsonify({'success': False, 'message': 'Xona rasmi topilmadi'})
        room_b64 = "data:image/jpeg;base64," + base64.b64encode(open(room_full, "rb").read()).decode()
        furniture_data = load_json(FURNITURE_FILE, {})
        furniture_images = []
        for fid in furniture_ids:
            if fid in furniture_data:
                path = furniture_data[fid]['image_path'].lstrip('/')
                if os.path.exists(path):
                    img_b64 = "data:image/jpeg;base64," + base64.b64encode(open(path, "rb").read()).decode()
                    furniture_images.append(img_b64)
        if not furniture_images:
            return jsonify({'success': False, 'message': 'Mebel rasmi topilmadi'})
        prompt = "Place the exact furniture pieces from the reference images into this room photo realistically. Keep original room layout, lighting, and architectural elements. Arrange furniture harmoniously. Photorealistic quality."
        output = replicate.run(
            "black-forest-labs/flux-1.1-pro-ultra",
            input={
                "prompt": prompt,
                "image": room_b64,
                "input_images": furniture_images,
                "seed": random.randint(1, 1000000),
                "output_format": "jpg",
                "aspect_ratio": "16:9"
            }
        )
        preview_path = os.path.join(UPLOAD_FOLDER, f"preview_{uuid.uuid4()}.jpg")
        with open(preview_path, "wb") as f:
            f.write(output.read())
        return jsonify({'success': True, 'preview_url': f'/{preview_path}'})
    except Exception as e:
        print(e)
        return jsonify({'success': False, 'message': str(e)})

@app.route('/upload_room_image', methods=['POST'])
def upload_room_image():
    try:
        image = request.files['image']
        filename = str(uuid.uuid4()) + '_' + secure_filename(image.filename)
        image_path = os.path.join(UPLOAD_FOLDER, filename)
        image.save(image_path)
        return jsonify({'success': True, 'image_path': f'/{image_path}'})
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
        ext = file.filename.rsplit('.', 1)[-1] if '.' in file.filename else 'jpg'
        filename = f"receipt_{uuid.uuid4().hex}.{ext}"
        file.save(os.path.join(RECEIPTS_FOLDER, filename))
        orders[order_id]['receipt_path'] = f'/static/receipts/{filename}'
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
    app.run(debug=True, port=5000)