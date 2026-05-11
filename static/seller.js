let shopName = '';

function showToast(msg,type='success'){const t=document.createElement('div');t.className=`toast ${type}`;t.innerHTML=`<i class="fas ${type==='success'?'fa-check-circle':'fa-exclamation-circle'}"></i> ${msg}`;document.body.appendChild(t);setTimeout(()=>{t.style.opacity='0';t.style.transition='all 0.3s';setTimeout(()=>t.remove(),300)},3000)}

function showSection(name,el){
    document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
    document.getElementById('section-'+name).classList.add('active');
    document.querySelectorAll('.nav-item:not(.logout)').forEach(n=>n.classList.remove('active'));
    if(el)el.classList.add('active');
    if(name==='dashboard')loadStats();
    if(name==='furniture')loadMyFurniture();
    if(name==='orders')loadOrders();
    if(name==='verify'){}
    if(name==='notifs')loadNotifications();
}

async function loadStats(){
    try{
        const r=await fetch('/seller/stats');const d=await r.json();
        if(d.success){
            document.getElementById('statOrders').textContent=d.total_orders;
            document.getElementById('statSold').textContent=d.total_sold;
            document.getElementById('statRevenue').textContent=Number(d.total_revenue).toLocaleString()+' so\'m';
            document.getElementById('statCommission').textContent=Number(d.commission_due).toLocaleString()+' so\'m';
            document.getElementById('statMonthSold').textContent=d.month_sold;
            document.getElementById('statMonthCommission').textContent=Number(d.month_commission).toLocaleString()+' so\'m';
            if(d.shop_name){shopName=d.shop_name;document.getElementById('shopNameDisplay').textContent=d.shop_name}
        }
    }catch(e){console.error(e)}
}

async function loadMyFurniture(){
    try{
        const r=await fetch('/get_furniture');const data=await r.json();
        const res=await fetch('/check_session');const sess=await res.json();
        const my=data.filter(f=>f.seller===sess.username);
        const c=document.getElementById('furnitureGrid');
        if(!my.length){c.innerHTML='<div class="empty-state" style="grid-column:1/-1"><i class="fas fa-couch"></i><h3>Mebellar yo\'q</h3></div>';return}
        c.innerHTML=my.map(item=>`<div class="furniture-card">
            <img src="${item.image_path}" alt="${item.name}">
            <div class="furniture-info">
                <h3>${item.name}</h3>
                <div class="furniture-detail"><i class="fas fa-tag"></i> ${item.category||''}</div>
                <div class="furniture-detail"><i class="fas fa-palette"></i> ${item.color||''} | ${item.material||''}</div>
                <div class="furniture-price">${Number(item.price).toLocaleString()} so'm</div>
                <button class="delete-btn" onclick="deleteFurniture('${item.id}')"><i class="fas fa-trash"></i> O'chirish</button>
            </div>
        </div>`).join('');
    }catch(e){console.error(e)}
}

async function deleteFurniture(id){
    if(!confirm('O\'chirmoqchimisiz?'))return;
    await fetch('/delete_furniture/'+id,{method:'DELETE'});
    showToast('O\'chirildi');loadMyFurniture();
}

async function addFurniture(){
    const form=document.getElementById('furnitureForm');
    const fd=new FormData(form);
    try{
        const r=await fetch('/add_furniture',{method:'POST',body:fd});
        const d=await r.json();
        if(d.success){showToast(d.message);form.reset()}
        else showToast(d.message,'error');
    }catch(e){showToast('Xatolik','error')}
}

async function loadOrders(){
    try{
        const r=await fetch('/seller/orders');const d=await r.json();
        const c=document.getElementById('ordersContainer');
        if(!d.success||!d.orders.length){c.innerHTML='<div class="empty-state"><i class="fas fa-shopping-bag"></i><h3>Buyurtmalar yo\'q</h3></div>';return}
        c.innerHTML=d.orders.map(o=>{
            let statusClass=o.status==='sold'?'sold':o.status==='contacted'?'contacted':'pending';
            let statusText=o.status==='sold'?'✅ Sotib oldi':o.status==='contacted'?'📞 Bog\'lanildi':'🔴 Kutilmoqda';
            let actions='';
            if(o.status==='pending'){
                actions+=`<button class="btn-sm yellow" onclick="updateStatus('${o.order_id}','contacted')"><i class="fas fa-phone"></i> Bog'landim</button>`;
                actions+=`<button class="btn-sm danger" onclick="deleteOrder('${o.order_id}')"><i class="fas fa-times"></i> O'chirish</button>`;
            }
            if(o.status==='contacted'){
                actions+=`<button class="btn-sm green" onclick="updateStatus('${o.order_id}','sold')"><i class="fas fa-check"></i> Sotib oldi</button>`;
                actions+=`<button class="btn-sm danger" onclick="deleteOrder('${o.order_id}')"><i class="fas fa-times"></i> Sotib olmadi</button>`;
            }
            return `<div class="order-card status-${o.status}">
                <div class="order-header">
                    <div class="order-code">${o.unique_code}</div>
                    <span class="status-badge ${statusClass}">${statusText}</span>
                </div>
                <div class="order-details">
                    <span><i class="fas fa-user"></i>${o.buyer_name}</span>
                    <span><i class="fas fa-phone"></i>${o.buyer_phone}</span>
                    <span><i class="fas fa-couch"></i>${o.furniture_name}</span>
                    <span><i class="fas fa-money-bill"></i>${Number(o.price).toLocaleString()} so'm</span>
                    <span><i class="fas fa-calendar"></i>${o.date}</span>
                </div>
                <div class="order-actions">${actions}</div>
            </div>`;
        }).join('');
    }catch(e){console.error(e)}
}

async function updateStatus(id,status){
    await fetch('/seller/update_order_status',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({order_id:id,status})});
    showToast('Status yangilandi');loadOrders();
}

async function deleteOrder(id){
    if(!confirm('O\'chirmoqchimisiz?'))return;
    await fetch('/seller/delete_order',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({order_id:id})});
    showToast('O\'chirildi');loadOrders();
}

async function verifyCode(){
    const code=document.getElementById('verifyInput').value.trim();
    if(!code){showToast('Kodni kiriting','error');return}
    try{
        const r=await fetch('/seller/verify_code',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code})});
        const d=await r.json();
        const c=document.getElementById('verifyResult');
        if(d.success){
            const o=d.order;
            c.innerHTML=`<div class="verify-result" style="border-color:var(--success)">
                <h3 style="color:var(--success);margin-bottom:1rem"><i class="fas fa-check-circle"></i> Kod topildi!</h3>
                <div class="order-details" style="margin-bottom:0">
                    <span><i class="fas fa-user"></i>${o.buyer_name}</span>
                    <span><i class="fas fa-phone"></i>${o.buyer_phone}</span>
                    <span><i class="fas fa-couch"></i>${o.furniture_name}</span>
                    <span><i class="fas fa-money-bill"></i>${Number(o.price).toLocaleString()} so'm</span>
                    <span><i class="fas fa-calendar"></i>${o.date}</span>
                    <span><i class="fas fa-info-circle"></i>Status: ${o.status}</span>
                </div>
            </div>`;
        }else{
            c.innerHTML=`<div class="verify-result" style="border-color:var(--danger)"><h3 style="color:var(--danger)"><i class="fas fa-times-circle"></i> Kod topilmadi</h3></div>`;
        }
    }catch(e){showToast('Xatolik','error')}
}

async function loadNotifications(){
    try{
        const r=await fetch('/notifications');const d=await r.json();
        const c=document.getElementById('notifsContainer');
        if(!d.success||!d.notifications.length){c.innerHTML='<div class="empty-state"><i class="fas fa-bell"></i><h3>Bildirishnomalar yo\'q</h3></div>';return}
        c.innerHTML=d.notifications.map(n=>`<div class="notif-item ${n.read?'':'unread'}" onclick="markRead('${n.id}',this)">
            <div class="notif-icon"><i class="fas fa-bell"></i></div>
            <div><div class="notif-text">${n.message}</div><div class="notif-date">${n.date}</div></div>
        </div>`).join('');
    }catch(e){console.error(e)}
}

async function markRead(id,el){
    await fetch('/notifications/mark_read',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});
    if(el)el.classList.remove('unread');
}

async function logout(){await fetch('/logout',{method:'POST'});window.location.href='/'}

async function init(){
    try{
        const r=await fetch('/check_session');
        if(r.ok){const d=await r.json();if(d.user_type!=='seller')window.location.href='/';else{document.getElementById('sellerName').textContent=d.username;loadStats()}}
        else window.location.href='/';
    }catch(e){window.location.href='/'}
}
init();
