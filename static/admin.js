function showToast(msg,type='success'){
    const t=document.createElement('div');
    t.className=`toast ${type}`;
    t.innerHTML=`<i class="fas ${type==='success'?'fa-check-circle':'fa-exclamation-circle'}"></i> ${msg}`;
    document.body.appendChild(t);
    setTimeout(()=>{t.style.opacity='0';t.style.transition='all 0.3s';setTimeout(()=>t.remove(),300)},3000);
}

function showSection(name,el){
    document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));
    document.getElementById('section-'+name).classList.add('active');
    document.querySelectorAll('.nav-item:not(.logout)').forEach(n=>n.classList.remove('active'));
    if(el)el.classList.add('active');
    const titles={dashboard:'Dashboard',sellers:'Sotuvchilar',addseller:"Sotuvchi qo'shish",orders:'Barcha buyurtmalar',notifs:'Bildirishnomalar',finance:'Moliyaviy hisobot'};
    document.getElementById('pageTitle').textContent=titles[name]||'Dashboard';
    if(name==='dashboard')loadDashboard();
    if(name==='sellers')loadSellers();
    if(name==='orders')loadAllOrders();
    if(name==='notifs')loadNotifications();
    if(name==='finance')loadFinance();
}

async function loadDashboard(){
    try{
        const r=await fetch('/admin/monthly_stats');
        const d=await r.json();
        if(d.success){
            document.getElementById('statSold').textContent=d.total_sold;
            document.getElementById('statRevenue').textContent=Number(d.total_revenue).toLocaleString()+" so'm";
            document.getElementById('statCommission').textContent=Number(d.total_commission).toLocaleString()+" so'm";
            document.getElementById('statProfit').textContent=Number(d.total_profit).toLocaleString()+" so'm";
            document.getElementById('statMonthSold').textContent=d.month_sold;
            document.getElementById('statMonthProfit').textContent=Number(d.month_profit).toLocaleString()+" so'm";
        }
    }catch(e){console.error(e)}
}

async function addSeller(){
    const shop_name=document.getElementById('shopName').value.trim();
    const shop_phone=document.getElementById('shopPhone').value.trim();
    const contact_phone=document.getElementById('contactPhone').value.trim();
    const login=document.getElementById('sellerLogin').value.trim();
    const password=document.getElementById('sellerPassword').value.trim();
    if(!shop_name||!login||!password){showToast("Majburiy maydonlarni to'ldiring",'error');return}
    try{
        const r=await fetch('/admin/add_seller',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({shop_name,shop_phone,contact_phone,login,password})});
        const d=await r.json();
        if(d.success){
            showToast(d.message);
            ['shopName','shopPhone','contactPhone','sellerLogin','sellerPassword'].forEach(id=>document.getElementById(id).value='');
        } else {
            showToast(d.message,'error');
        }
    }catch(e){showToast('Xatolik','error')}
}

async function loadSellers(){
    try{
        const r=await fetch('/admin/get_sellers');
        const d=await r.json();
        const c=document.getElementById('sellersContainer');
        if(!d.success||!d.sellers.length){
            c.innerHTML='<div class="empty-state"><i class="fas fa-store"></i><h3>Sotuvchilar yo\'q</h3></div>';
            return;
        }
        c.innerHTML=d.sellers.map(s=>`
        <div class="seller-card">
            <div class="seller-info">
                <h3><i class="fas fa-store" style="color:var(--primary);margin-right:8px"></i>${s.shop_name}</h3>
                <div class="seller-meta">
                    <span><i class="fas fa-user"></i> ${s.login}</span>
                    <span><i class="fas fa-phone"></i> ${s.shop_phone||'-'}</span>
                    <span><i class="fas fa-mobile-alt"></i> ${s.contact_phone||'-'}</span>
                    <span><i class="fas fa-couch"></i> ${s.furniture_count} mebel</span>
                    <span><i class="fas fa-shopping-bag"></i> ${s.order_count} buyurtma</span>
                    <span><i class="fas fa-check-circle" style="color:var(--success)"></i> ${s.sold_count} sotilgan</span>
                </div>
            </div>
            <button class="btn-sm danger" onclick="deleteSeller('${s.login}')"><i class="fas fa-trash"></i> O'chirish</button>
        </div>`).join('');
    }catch(e){console.error(e)}
}

async function deleteSeller(login){
    if(!confirm("Rostdan o'chirmoqchimisiz?"))return;
    await fetch('/admin/delete_seller/'+login,{method:'DELETE'});
    showToast("O'chirildi");
    loadSellers();
}

async function loadAllOrders(){
    try{
        const r=await fetch('/admin/all_orders');
        const d=await r.json();
        const c=document.getElementById('ordersTableBody');
        if(!d.success||!d.orders.length){
            c.innerHTML='<tr><td colspan="8" style="text-align:center;padding:2rem;color:var(--text-muted)">Buyurtmalar yo\'q</td></tr>';
            return;
        }
        c.innerHTML=d.orders.map(o=>{
            const statusClass=o.status==='sold'?'sold':o.status==='contacted'?'contacted':'pending';
            const statusText=o.status==='sold'?'✅ Sotildi':o.status==='contacted'?'📞 Bog\'lanildi':'🔴 Kutilmoqda';
            let actions='';
            if(o.receipt_path&&!o.receipt_approved){
                actions+=`<button class="btn-sm approve" onclick="approveReceipt('${o.order_id}')"><i class="fas fa-check"></i> Tasdiqlash</button>`;
            }
            if(o.receipt_approved&&o.buyer_contact_info&&!o.cashback_paid){
                actions+=`<button class="btn-sm info" onclick="markCashbackPaid('${o.order_id}')"><i class="fas fa-coins"></i> Cashback to'landi</button>`;
            }
            if(o.cashback_paid){
                actions+=`<span style="color:var(--success);font-size:0.75rem"><i class="fas fa-check-circle"></i> To'landi</span>`;
            }
            const receiptHtml=o.receipt_path?`<img src="${o.receipt_path}" class="receipt-img" onclick="window.open('${o.receipt_path}')" title="Ko'rish">`:'-';
            const contactHtml=o.buyer_contact_info?`<div style="font-size:0.75rem;color:var(--accent);margin-top:4px"><i class="fas fa-paper-plane"></i> ${o.buyer_contact_info}</div>`:'';
            return `<tr>
                <td><strong style="color:var(--accent);font-family:monospace">${o.unique_code}</strong></td>
                <td>${o.furniture_name}</td>
                <td>${o.buyer_name}<br><small style="color:var(--text-muted)">${o.buyer_phone}</small></td>
                <td>${o.shop_name}</td>
                <td>${Number(o.price).toLocaleString()} so'm</td>
                <td><span class="status-badge ${statusClass}">${statusText}</span></td>
                <td>${receiptHtml}</td>
                <td>${actions}${contactHtml}</td>
            </tr>`;
        }).join('');
    }catch(e){console.error(e)}
}

async function approveReceipt(id){
    await fetch('/admin/approve_receipt',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({order_id:id})});
    showToast('Chek tasdiqlandi!');
    loadAllOrders();
}

async function markCashbackPaid(id){
    await fetch('/admin/mark_cashback_paid',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({order_id:id})});
    showToast("Cashback to'landi deb belgilandi!");
    loadAllOrders();
}

async function loadNotifications(){
    try{
        const r=await fetch('/notifications');
        const d=await r.json();
        const c=document.getElementById('notifsContainer');
        const badge=document.getElementById('adminNotifBadge');
        if(!d.success||!d.notifications.length){
            c.innerHTML='<div class="empty-state"><i class="fas fa-bell"></i><h3>Bildirishnomalar yo\'q</h3></div>';
            if(badge){badge.style.display='none'}
            return;
        }
        const unread=d.notifications.filter(n=>!n.read).length;
        if(badge){badge.textContent=unread;badge.style.display=unread>0?'inline-flex':'none'}
        const iconMap = {
            'partnership': {icon:'fa-handshake', color:'#00E676'},
            'new_order':   {icon:'fa-shopping-bag', color:'var(--primary)'},
            'receipt':     {icon:'fa-file-alt', color:'var(--accent)'},
            'cashback':    {icon:'fa-coins', color:'#FFD700'},
            'success':     {icon:'fa-check-circle', color:'#00E676'},
        };
        c.innerHTML=d.notifications.map(n=>{
            const ic = iconMap[n.type] || {icon:'fa-bell', color:'rgba(255,255,255,0.5)'};
            const border = n.type==='partnership' ? 'border-left:3px solid #00E676;' : '';
            return `
        <div class="notif-item ${n.read?'':'unread'}" onclick="markRead('${n.id}',this)" style="${border}">
            <div class="notif-icon" style="background:rgba(${n.type==='partnership'?'0,230,118':'108,99,255'},0.15);">
                <i class="fas ${ic.icon}" style="color:${ic.color};"></i>
            </div>
            <div><div class="notif-text" style="white-space:pre-line;">${n.message}</div><div class="notif-date">${n.date}</div></div>
        </div>`;
        }).join('');
    }catch(e){console.error(e)}
}

async function markRead(id,el){
    await fetch('/notifications/mark_read',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});
    if(el)el.classList.remove('unread');
}

async function loadFinance(){
    try{
        const r=await fetch('/admin/monthly_stats');
        const d=await r.json();
        if(!d.success)return;
        document.getElementById('financeContent').innerHTML=`
        <div class="card"><h2><i class="fas fa-calendar-alt"></i> Bu oy statistikasi</h2>
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-card-header"><span class="stat-card-title">Oylik sotuvlar</span><div class="stat-card-icon blue"><i class="fas fa-shopping-bag"></i></div></div><div class="stat-number">${d.month_sold}</div></div>
            <div class="stat-card"><div class="stat-card-header"><span class="stat-card-title">Oylik tushum</span><div class="stat-card-icon pink"><i class="fas fa-money-bill"></i></div></div><div class="stat-number" style="font-size:1.3rem">${Number(d.month_revenue).toLocaleString()} so'm</div></div>
            <div class="stat-card"><div class="stat-card-header"><span class="stat-card-title">Oylik 5% komissiya</span><div class="stat-card-icon green"><i class="fas fa-percentage"></i></div></div><div class="stat-number" style="font-size:1.3rem">${Number(d.month_commission).toLocaleString()} so'm</div></div>
            <div class="stat-card"><div class="stat-card-header"><span class="stat-card-title">Oylik 1% cashback</span><div class="stat-card-icon orange"><i class="fas fa-coins"></i></div></div><div class="stat-number" style="font-size:1.3rem">${Number(d.month_cashback).toLocaleString()} so'm</div></div>
            <div class="stat-card"><div class="stat-card-header"><span class="stat-card-title">Oylik 4% foyda</span><div class="stat-card-icon cyan"><i class="fas fa-chart-line"></i></div></div><div class="stat-number" style="font-size:1.3rem;color:var(--success)">${Number(d.month_profit).toLocaleString()} so'm</div></div>
        </div></div>
        <div class="card"><h2><i class="fas fa-infinity"></i> Umumiy (barcha vaqt)</h2>
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-card-header"><span class="stat-card-title">Jami sotuvlar</span><div class="stat-card-icon blue"><i class="fas fa-chart-bar"></i></div></div><div class="stat-number">${d.total_sold}</div></div>
            <div class="stat-card"><div class="stat-card-header"><span class="stat-card-title">Jami tushum</span><div class="stat-card-icon pink"><i class="fas fa-money-bill-wave"></i></div></div><div class="stat-number" style="font-size:1.3rem">${Number(d.total_revenue).toLocaleString()} so'm</div></div>
            <div class="stat-card"><div class="stat-card-header"><span class="stat-card-title">Jami 5% komissiya</span><div class="stat-card-icon green"><i class="fas fa-hand-holding-usd"></i></div></div><div class="stat-number" style="font-size:1.3rem">${Number(d.total_commission).toLocaleString()} so'm</div></div>
            <div class="stat-card"><div class="stat-card-header"><span class="stat-card-title">Jami 4% foyda</span><div class="stat-card-icon cyan"><i class="fas fa-piggy-bank"></i></div></div><div class="stat-number" style="font-size:1.3rem;color:var(--success)">${Number(d.total_profit).toLocaleString()} so'm</div></div>
        </div></div>`;
    }catch(e){console.error(e)}
}

async function logout(){await fetch('/logout',{method:'POST'});window.location.href='/'}

async function init(){
    try{
        const r=await fetch('/check_session');
        const d=await r.json();
        if(!d.username||d.user_type!=='superadmin'){
            window.location.href='/';
        } else {
            loadDashboard();
            // Bildirishnomalarni avtomatik tekshirish
            setInterval(checkNotifCount,30000);
            checkNotifCount();
        }
    }catch(e){window.location.href='/'}
}

async function checkNotifCount(){
    try{
        const r=await fetch('/notifications');
        const d=await r.json();
        if(d.success){
            const unread=d.notifications.filter(n=>!n.read).length;
            const badge=document.getElementById('adminNotifBadge');
            if(badge){badge.textContent=unread;badge.style.display=unread>0?'inline-flex':'none'}
        }
    }catch(e){}
}

init();