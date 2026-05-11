let currentUser = null;
let allFurniture = [];
let cart = [];
let uploadedRoomImage = null;

function showToast(msg, type = 'success') {
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.innerHTML = `<i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'}"></i> ${msg}`;
    document.body.appendChild(t);
    setTimeout(() => { t.style.opacity = '0'; t.style.transform = 'translateY(-20px)'; t.style.transition = 'all 0.3s'; setTimeout(() => t.remove(), 300) }, 3000);
}

function showSection(name) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.getElementById('section-' + name).classList.add('active');
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    const btn = document.querySelector(`[data-section="${name}"]`);
    if (btn) btn.classList.add('active');
    if (name === 'orders') loadMyOrders();
    if (name === 'notifs') loadNotifications();
    if (name === 'shop') loadFurniture();
}

function toggleCart() {
    document.getElementById('cartPanel').classList.toggle('open');
    document.getElementById('cartOverlay').classList.toggle('open');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('active');
}

function previewRoom(input) {
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = e => {
            document.getElementById('roomPreview').innerHTML = `<img src="${e.target.result}" style="max-width:100%;max-height:200px;border-radius:12px;object-fit:cover;">`;
        };
        reader.readAsDataURL(input.files[0]);
    }
}

// ============== DO'KON ==============
async function loadFurniture() {
    try {
        const res = await fetch('/get_furniture');
        allFurniture = await res.json();
        document.getElementById('allCount').textContent = allFurniture.length + ' ta';
        displayFurniture(allFurniture, document.getElementById('furnitureGrid'));
    } catch (e) { console.error(e) }
}

function displayFurniture(items, container) {
    if (!items || !items.length) {
        container.innerHTML = '<div class="empty-state"><i class="fas fa-couch"></i><h3>Mebellar yo\'q</h3></div>';
        return;
    }
    container.innerHTML = items.map(item => {
        const inCart = cart.some(ci => ci.id === item.id);
        const nameEsc = item.name.replace(/'/g, "\\'");
        const shopEsc = (item.shop_name || '').replace(/'/g, "\\'");
        return `<div class="furniture-card">
            <div class="furniture-card-img">
                <img src="${item.image_path}" alt="${item.name}" onerror="this.src='/static/no-image.png'">
                ${item.shop_name ? `<div class="shop-badge"><i class="fas fa-store"></i> ${item.shop_name}</div>` : ''}
            </div>
            <div class="furniture-info">
                <h3>${item.name}</h3>
                ${item.category ? `<div class="furniture-detail"><i class="fas fa-tag"></i> ${item.category}</div>` : ''}
                ${item.color ? `<div class="furniture-detail"><i class="fas fa-palette"></i> ${item.color}${item.material ? ' | ' + item.material : ''}</div>` : ''}
                <div class="furniture-price">${Number(item.price).toLocaleString()} so'm</div>
                <button class="btn-cart ${inCart ? 'in-cart' : ''}"
                    onclick="toggleCartItem('${item.id}','${nameEsc}',${item.price},'${item.image_path}','${shopEsc}')">
                    <i class="fas ${inCart ? 'fa-check' : 'fa-cart-plus'}"></i> ${inCart ? 'Savatda' : 'Savatga qo\'shish'}
                </button>
            </div>
        </div>`;
    }).join('');
}

function toggleCartItem(id, name, price, img, shop) {
    const idx = cart.findIndex(i => i.id === id);
    if (idx === -1) {
        cart.push({ id, name, price, image_path: img, shop_name: shop });
        showToast(`${name} savatga qo'shildi`);
    } else {
        cart.splice(idx, 1);
        showToast(`${name} savatdan olib tashlandi`, 'error');
    }
    updateCartUI();
    // Refresh current view
    const shopSection = document.getElementById('section-shop');
    if (shopSection.classList.contains('active')) displayFurniture(allFurniture, document.getElementById('furnitureGrid'));
    const aiResults = document.getElementById('aiResults');
    if (window.lastAIResults && aiResults.children.length > 0) displayFurniture(window.lastAIResults, aiResults);
}

function updateCartUI() {
    const total = cart.reduce((s, i) => s + i.price, 0);
    document.getElementById('cartCount').textContent = cart.length;
    document.getElementById('cartBadge').textContent = cart.length;
    document.getElementById('cartTotal').textContent = Number(total).toLocaleString() + " so'm";
    const ci = document.getElementById('cartItems');
    if (!cart.length) {
        ci.innerHTML = '<div class="cart-empty"><i class="fas fa-cart-plus"></i><h3>Savat bo\'sh</h3></div>';
    } else {
        ci.innerHTML = cart.map(item => {
            const nameEsc = item.name.replace(/'/g, "\\'");
            const shopEsc = (item.shop_name || '').replace(/'/g, "\\'");
            return `<div class="cart-item">
                <div class="cart-item-info">
                    <div class="cart-item-name">${item.name}</div>
                    <div class="cart-item-price">${Number(item.price).toLocaleString()} so'm</div>
                    <div class="cart-item-shop"><i class="fas fa-store"></i> ${item.shop_name || ''}</div>
                </div>
                <button class="cart-item-remove" onclick="toggleCartItem('${item.id}','${nameEsc}',${item.price},'${item.image_path}','${shopEsc}')"><i class="fas fa-trash"></i></button>
            </div>`;
        }).join('');
    }
}

// ============== AI TAVSIYA ==============
async function getAIRecommendations() {
    const fileInput = document.getElementById('roomImage');
    const preferences = document.getElementById('aiPreferences').value.trim();
    if (!fileInput.files.length) { showToast('Xona rasmini yuklang', 'error'); return }
    if (!preferences) { showToast('Xohishlaringizni yozing', 'error'); return }

    const btn = document.querySelector('#section-ai .btn-submit');
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Yuklanmoqda...';
    btn.disabled = true;

    try {
        const formData = new FormData();
        formData.append('image', fileInput.files[0]);
        const uploadRes = await fetch('/upload_room_image', { method: 'POST', body: formData });
        const uploadData = await uploadRes.json();
        if (!uploadData.success) { showToast('Rasm yuklanmadi', 'error'); return }
        uploadedRoomImage = uploadData.image_path;

        const recRes = await fetch('/recommend_furniture', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ preferences, room_image_path: uploadedRoomImage }) });
        const recData = await recRes.json();
        if (recData.success && recData.recommendations) {
            window.lastAIResults = recData.recommendations;
            displayFurniture(recData.recommendations, document.getElementById('aiResults'));
            showToast(`${recData.recommendations.length} ta mebel tavsiya qilindi!`);
        } else {
            showToast(recData.message || 'Tavsiya olinmadi', 'error');
        }
    } catch (e) {
        showToast('Serverda xatolik', 'error');
    } finally {
        btn.innerHTML = '<i class="fas fa-magic"></i> Tavsiya olish';
        btn.disabled = false;
    }
}

// ============== AI PREVIEW ==============
async function generatePreview() {
    if (!uploadedRoomImage) { showToast("Avval AI Tavsiya bo'limida xona rasmini yuklang", 'error'); return }
    if (!cart.length) { showToast("Savat bo'sh", 'error'); return }

    document.getElementById('previewModal').classList.add('active');
    document.getElementById('previewImage').style.display = 'none';
    document.getElementById('previewLoading').style.display = 'block';

    try {
        const res = await fetch('/generate_preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ room_image_path: uploadedRoomImage, furniture_ids: cart.map(i => i.id) })
        });
        const data = await res.json();
        document.getElementById('previewLoading').style.display = 'none';
        if (data.success) {
            document.getElementById('previewImage').src = data.preview_url;
            document.getElementById('previewImage').style.display = 'block';
        } else {
            showToast(data.message || "AI generatsiyada xatolik", 'error');
            closeModal('previewModal');
        }
    } catch (e) {
        document.getElementById('previewLoading').style.display = 'none';
        showToast('Serverda xatolik', 'error');
        closeModal('previewModal');
    }
}

// ============== BUYURTMA ==============
function showBuyModal() {
    if (!cart.length) { showToast("Savat bo'sh", 'error'); return }
    // Oldindan ism/telefon ni to'ldirish
    document.getElementById('buyModal').classList.add('active');
}

async function submitOrder() {
    const full_name = document.getElementById('buyFullName').value.trim();
    const phone = document.getElementById('buyPhone').value.trim();
    if (!full_name || !phone) { showToast("Barcha maydonlarni to'ldiring", 'error'); return }

    const btn = document.querySelector('#buyModal .btn-submit');
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Yuborilmoqda...';
    btn.disabled = true;

    try {
        const res = await fetch('/customer/place_order', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items: cart.map(i => i.id), full_name, phone })
        });
        const data = await res.json();
        if (data.success) {
            closeModal('buyModal');
            toggleCart();
            let html = data.orders.map(o => `
            <div style="margin:0.8rem 0;padding:1.2rem;background:rgba(255,255,255,0.03);border-radius:12px;border:1px solid var(--card-border)">
                <div style="font-weight:600;margin-bottom:0.5rem">${o.furniture_name}</div>
                <div class="code-display">${o.unique_code}</div>
                <div style="font-size:0.85rem;color:var(--text-secondary)">
                    <i class="fas fa-store" style="color:var(--accent)"></i> <strong>${o.shop_name}</strong> do'koniga tashrif buyuring
                </div>
                <div style="font-size:0.85rem;color:var(--success);margin-top:0.3rem">
                    <i class="fas fa-coins"></i> Cashback: ${Number(o.cashback_amount).toLocaleString()} so'm
                </div>
            </div>`).join('');
            document.getElementById('successContent').innerHTML = `
            <div class="success-content">
                <div class="success-icon"><i class="fas fa-check-circle"></i></div>
                <h2>Buyurtma qabul qilindi!</h2>
                <p class="success-msg">Tez orada sotuvchi siz bilan bog'lanadi. Quyidagi <strong>maxsus kodni</strong> do'konga ko'rsating — ular maxsus chek berishadi.</p>
                ${html}
                <p style="color:var(--text-muted);font-size:0.85rem;margin-top:1rem">Chekni "Buyurtmalarim" bo'limida yuklang va sotib olgan mebelingizning <strong style="color:var(--success)">1% cashback</strong>ini qaytarib oling!</p>
            </div>`;
            document.getElementById('successModal').classList.add('active');
            cart = [];
            updateCartUI();
            displayFurniture(allFurniture, document.getElementById('furnitureGrid'));
        } else {
            showToast(data.message, 'error');
        }
    } catch (e) {
        showToast('Serverda xatolik', 'error');
    } finally {
        btn.innerHTML = '<i class="fas fa-check"></i> Tasdiqlash';
        btn.disabled = false;
    }
}

// ============== BUYURTMALARIM ==============
async function loadMyOrders() {
    try {
        const res = await fetch('/customer/my_orders');
        const data = await res.json();
        const c = document.getElementById('ordersContainer');
        if (!data.orders || !data.orders.length) {
            c.innerHTML = '<div class="empty-state"><i class="fas fa-shopping-bag"></i><h3>Buyurtmalar yo\'q</h3><p>Mebellarni savatga qo\'shib buyurtma bering</p></div>';
            return;
        }
        c.innerHTML = data.orders.map(o => {
            let statusText = 'Kutilmoqda', statusClass = 'pending';
            if (o.status === 'contacted') { statusText = 'Sotuvchi bog\'landi'; statusClass = 'contacted' }
            if (o.status === 'sold') { statusText = 'Sotib olindi'; statusClass = 'sold' }
            let actions = '';
            if (o.status === 'sold' && !o.receipt_path) {
                actions += `<button class="btn-upload" onclick="showUploadReceipt('${o.order_id}')"><i class="fas fa-upload"></i> Chek yuklash</button>`;
            }
            if (o.receipt_path && !o.receipt_approved) {
                actions += `<span style="color:var(--warning);font-size:0.8rem"><i class="fas fa-clock"></i> Chek tekshirilmoqda...</span>`;
            }
            if (o.receipt_path && o.receipt_approved && !o.buyer_contact_info) {
                actions += `<button class="btn-contact" onclick="showContactModal('${o.order_id}',${o.cashback_amount})"><i class="fas fa-coins"></i> Cashback olish</button>`;
            }
            if (o.cashback_paid) {
                actions += `<span style="color:var(--success)"><i class="fas fa-check-circle"></i> Cashback to'landi!</span>`;
            }
            const receiptStatus = o.receipt_path ? (o.receipt_approved ? `<span style="color:var(--success);font-size:0.75rem"><i class="fas fa-check"></i> Chek tasdiqlandi</span>` : `<span style="color:var(--warning);font-size:0.75rem"><i class="fas fa-clock"></i> Chek tekshirilmoqda</span>`) : '';
            return `<div class="order-card">
                <div class="order-header">
                    <div class="order-code">${o.unique_code}</div>
                    <div class="order-status ${statusClass}">${statusText}</div>
                </div>
                <div class="order-details">
                    <span><i class="fas fa-couch"></i> ${o.furniture_name}</span>
                    <span><i class="fas fa-money-bill"></i> ${Number(o.price).toLocaleString()} so'm</span>
                    <span><i class="fas fa-store"></i> ${o.shop_name || ''}</span>
                    <span><i class="fas fa-calendar"></i> ${o.date}</span>
                </div>
                ${receiptStatus ? `<div style="margin-bottom:0.5rem">${receiptStatus}</div>` : ''}
                <div class="order-actions">${actions}</div>
            </div>`;
        }).join('');
    } catch (e) { console.error(e) }
}

function showUploadReceipt(orderId) {
    document.getElementById('receiptOrderId').value = orderId;
    document.getElementById('receiptFile').value = '';
    document.getElementById('receiptModal').classList.add('active');
}

async function submitReceipt() {
    const orderId = document.getElementById('receiptOrderId').value;
    const file = document.getElementById('receiptFile').files[0];
    if (!file) { showToast('Chek rasmini tanlang', 'error'); return }

    const btn = document.querySelector('#receiptModal .btn-submit');
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Yuklanmoqda...';
    btn.disabled = true;

    const fd = new FormData();
    fd.append('order_id', orderId);
    fd.append('receipt', file);
    try {
        const res = await fetch('/customer/upload_receipt', { method: 'POST', body: fd });
        const data = await res.json();
        if (data.success) {
            showToast(data.message);
            closeModal('receiptModal');
            loadMyOrders();
        } else {
            showToast(data.message || 'Xatolik', 'error');
        }
    } catch (e) {
        showToast('Serverda xatolik', 'error');
    } finally {
        btn.innerHTML = '<i class="fas fa-upload"></i> Yuklash';
        btn.disabled = false;
    }
}

function showContactModal(orderId, cashback) {
    document.getElementById('contactOrderId').value = orderId;
    document.getElementById('cashbackAmount').textContent = Number(cashback).toLocaleString();
    document.getElementById('contactInfo').value = '';
    document.getElementById('contactModal').classList.add('active');
}

async function submitContact() {
    const orderId = document.getElementById('contactOrderId').value;
    const contact = document.getElementById('contactInfo').value.trim();
    if (!contact) { showToast("Aloqa ma'lumotini kiriting", 'error'); return }
    const res = await fetch('/customer/submit_contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order_id: orderId, contact_info: contact })
    });
    const data = await res.json();
    if (data.success) {
        showToast('Yuborildi! Tez orada bog\'lanamiz.');
        closeModal('contactModal');
        loadMyOrders();
    } else {
        showToast('Xatolik', 'error');
    }
}

// ============== BILDIRISHNOMALAR ==============
async function loadNotifications() {
    try {
        const res = await fetch('/notifications');
        const data = await res.json();
        const c = document.getElementById('notifsContainer');
        const badge = document.getElementById('notifBadge');
        if (!data.notifications || !data.notifications.length) {
            c.innerHTML = '<div class="empty-state"><i class="fas fa-bell"></i><h3>Bildirishnomalar yo\'q</h3></div>';
            if (badge) badge.style.display = 'none';
            return;
        }
        const unread = data.notifications.filter(n => !n.read).length;
        if (badge) { badge.textContent = unread; badge.style.display = unread > 0 ? 'flex' : 'none' }
        c.innerHTML = data.notifications.map(n => `
        <div class="notif-item ${n.read ? '' : 'unread'}" onclick="markRead('${n.id}',this)">
            <div class="notif-icon"><i class="fas fa-bell"></i></div>
            <div>
                <div class="notif-text">${n.message}</div>
                <div class="notif-date">${n.date}</div>
            </div>
        </div>`).join('');
    } catch (e) { console.error(e) }
}

async function markRead(id, el) {
    await fetch('/notifications/mark_read', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) });
    if (el) el.classList.remove('unread');
}

async function logout() {
    await fetch('/logout', { method: 'POST' });
    window.location.href = '/';
}

// ============== INIT ==============
async function init() {
    try {
        const res = await fetch('/check_session');
        if (res.ok) {
            const data = await res.json();
            if (data.user_type === 'user') {
                currentUser = data.username;
                document.getElementById('usernameDisplay').textContent = currentUser;
                document.getElementById('userAvatar').textContent = currentUser.charAt(0).toUpperCase();
                loadFurniture();
                updateCartUI();
                loadNotifications();
                // Bildirishnomalarni avtomatik yangilash
                setInterval(loadNotifications, 30000);
            } else {
                window.location.href = '/';
            }
        } else {
            window.location.href = '/';
        }
    } catch (e) { window.location.href = '/' }
}

init();