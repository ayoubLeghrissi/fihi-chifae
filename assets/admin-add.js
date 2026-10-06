/* fihi-chifae : إدارة المنتجات والفئات عبر API v1 - واجهة عربية افتراضية */
(function () {
  'use strict';

  const $ = (s) => document.querySelector(s);
  const CAT_IMG_FALLBACK = {
    amlou: 'assets/prod-amlou.svg', miels: 'assets/prod-miel.svg', huiles: 'assets/cat-argan.svg',
    cosmetiques: 'assets/cat-promo.svg', autres: 'assets/prod-pack.svg', recettes: 'assets/prod-coffret.svg',
    packs: 'assets/prod-pack.svg', thes: 'assets/story.svg',
  };

  const DEL_SVG = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6" stroke-linecap="round"/></svg>';
  const REV_SVG = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9.2"/><path d="M8 12h8" stroke-linecap="round"/></svg>';
  const EDIT_SVG = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const SIZE_DEL_SVG = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12" stroke-linecap="round"/></svg>';

  const UNITS = [
    { v: 'kg', ar: 'كغ' },
    { v: 'L', ar: 'ل' },
  ];

  // Suggested sizes per category: oils default to litres, everything else to kg.
  function suggestSizes(cat) {
    if (cat === 'huiles') {
      return [{ size: '1', unit: 'L' }, { size: '5', unit: 'L' }];
    }
    return [{ size: '1', unit: 'kg' }, { size: '0.5', unit: 'kg' }];
  }

  function unitOptions(selected) {
    return UNITS.map((u) =>
      '<option value="' + u.v + '"' + (u.v === selected ? ' selected' : '') + '>' + u.v + ' (' + u.ar + ')</option>'
    ).join('');
  }

  // Build one editable size row. `s` = {size, unit, price}
  function sizeRowHTML(s) {
    s = s || {};
    return (
      '<div class="size-row" data-size-row>' +
      '  <input type="text" class="sr-size" value="' + esc(s.size != null ? s.size : '') + '" placeholder="1" inputmode="decimal">' +
      '  <select class="sr-unit">' + unitOptions(s.unit || 'kg') + '</select>' +
      '  <input type="number" class="sr-price" value="' + esc(s.price != null ? s.price : '') + '" min="0" step="0.01" placeholder="السعر">' +
      '  <button type="button" class="size-del" data-del-size title="حذف الحجم">' + SIZE_DEL_SVG + '</button>' +
      '</div>'
    );
  }

  function sizeTagsHTML(sizes) {
    if (!sizes || !sizes.length) return '';
    return '<div class="size-tags">' + sizes.map((s) =>
      '<span class="size-tag">' + esc(s.size) + ' ' + esc(s.unit) + (s.price != null ? ' · ' + fmt(s.price) : '') + '</span>'
    ).join('') + '</div>';
  }

  let CATS = [];

  function showMessage(text, ok) {
    const msg = $('#msg');
    msg.className = ok ? 'msg ok' : 'msg err';
    msg.textContent = text;
    clearTimeout(showMessage._t);
    showMessage._t = setTimeout(function () { msg.className = 'msg'; }, 4000);
  }

  async function api(path, opts) {
    opts = opts || {};
    opts.headers = opts.headers || {};
    if (opts.body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(opts.body);
    }
    const res = await AdminAuth.api(path, opts);
    let data = {};
    try { data = await res.json(); } catch (e) { data = {}; }
    if (!res.ok) {
      const e = data.error;
      const msg = (typeof e === 'string') ? e : (e && e.message) || 'خطأ في الخادم';
      const err = new Error(msg);
      err.status = res.status;
      err.payload = data;
      throw err;
    }
    return data;
  }

  function catTitle(slug) {
    const c = CATS.find((x) => x.id === slug);
    return c ? (c.title_ar || slug) : slug;
  }

  function normalize(s) {
    return String(s || '').trim().replace(/\s+/g, ' ').toLowerCase();
  }

  function findExactCategory(name) {
    const needle = normalize(name);
    return CATS.find((c) => normalize(c.title_ar) === needle || normalize(c.title_fr) === needle || normalize(c.title_en) === needle) || null;
  }

  function filterCats(prefix) {
    const needle = normalize(prefix);
    if (!needle) return CATS.slice();
    return CATS.filter((c) => {
      return [c.title_ar, c.title_fr, c.title_en].some((t) => normalize(t).indexOf(needle) === 0);
    });
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
  }

  function fmt(n) { return Number(n || 0).toFixed(2).replace('.', ','); }

  function renderDropdown() {
    const input = $('#fCat');
    const dd = $('#catDropdown');
    const q = input.value;
    const filtered = filterCats(q);
    const exact = findExactCategory(q);
    let html = '';
    if (!filtered.length && !q.trim()) {
      html = '<div class="combo-empty">لا توجد فئة</div>';
    } else {
      html = filtered.map((c) => {
        const label = esc(c.title_ar) + ' <span>' + esc(c.title_fr || c.title_en || c.id) + '</span>';
        return '<div class="combo-item" data-id="' + esc(c.id) + '"><b>' + label + '</b><span>slug: ' + esc(c.id) + '</span></div>';
      }).join('');
      if (q.trim() && !exact) {
        if (q.trim().length >= 2) {
          html += '<div class="combo-item create" data-create="1">+ إنشاء « ' + esc(q.trim()) + ' » كفئة جديدة</div>';
        } else {
          html += '<div class="combo-empty">واصل الكتابة لإنشاء « ' + esc(q.trim()) + ' »</div>';
        }
      }
      if (!html) html = '<div class="combo-empty">لا توجد فئة مطابقة — اكتب لإنشاء فئة جديدة</div>';
    }
    dd.innerHTML = html;
    dd.classList.add('show');

    dd.querySelectorAll('.combo-item').forEach((el) => {
      el.addEventListener('click', function () {
        if (el.dataset.create) {
          dd.classList.remove('show');
          input.focus();
          showMessage('سيتم إنشاء الفئة « ' + q.trim() + ' » تلقائياً عند إضافة المنتج.', true);
        } else {
          const cat = CATS.find((x) => x.id === el.dataset.id);
          if (cat) {
            input.value = cat.title_ar;
            dd.classList.remove('show');
          }
        }
      });
    });
  }

  function closeDropdown() {
    const dd = $('#catDropdown');
    if (dd) dd.classList.remove('show');
  }

  function initCategoryCombo() {
    const input = $('#fCat');
    const dd = $('#catDropdown');
    if (!input || !dd) return;
    input.addEventListener('input', renderDropdown);
    input.addEventListener('focus', renderDropdown);
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { closeDropdown(); }
    });
    document.addEventListener('click', function (e) {
      const combo = $('#catCombo');
      if (combo && !combo.contains(e.target)) closeDropdown();
    });
  }

  async function loadCatalog() {
    const data = await api('/api/v1/catalog');
    CATS = (data.categories || []).map((c) => ({
      id: c.id, title_ar: c.title_ar, title_fr: c.title_fr, title_en: c.title_en, img: c.img,
    }));
    return data;
  }

  async function loadList() {
    const box = $('#productList');
    const catBox = $('#catList');
    let data;
    try {
      data = await loadCatalog();
    } catch (e) {
      if (box) box.innerHTML = '<p class="empty">تعذر تحميل المنتجات.</p>';
      if (catBox) catBox.innerHTML = '<p class="empty">تعذر تحميل الفئات.</p>';
      showMessage(e.message, false);
      return;
    }
    // render categories
    if (catBox) {
      if (!data.categories || !data.categories.length) {
        catBox.innerHTML = '<p class="empty">لا توجد فئات.</p>';
      } else {
        catBox.innerHTML = data.categories.map((c) =>
          '<div class="prod-row">' +
          '  <div class="prod-view">' +
          '    <img src="' + esc(c.img) + '" alt="" onerror="this.style.visibility=\'hidden\'">' +
          '    <div class="info"><b>' + esc(c.title_ar || c.id) + '</b><span>ID: ' + esc(c.id) + '</span></div>' +
          '  <button class="btn-del" data-action="delete-cat" data-id="' + esc(c.id) + '" title="حذف الفئة">' + DEL_SVG + '</button>' +
          '  </div>' +
          '</div>'
        ).join('');
      }
    }
    const inp = $('#fCat');
    if (inp && document.activeElement === inp) renderDropdown();

    const rows = [];
    (data.categories || []).forEach((c) => {
      (c.products || []).forEach((p) => {
        rows.push({ id: p.id, name: p.name, price: p.min, cat: c.id, img: p.img || c.img, custom: p.custom, sizes: p.sizes || [] });
      });
    });
    if (!rows.length) { box.innerHTML = '<p class="empty">لا يوجد منتج في القائمة.</p>'; return; }
    box.innerHTML = rows.map((p) =>
      '<div class="prod-row" data-id="' + esc(p.id) + '">' +
      '  <div class="prod-view">' +
      '    <img src="' + esc(p.img) + '" alt="" onerror="this.style.visibility=\'hidden\'">' +
      '    <div class="info"><b>' + esc(p.name) + (p.custom ? ' <span class="badge-custom">خاص</span>' : '') + '</b>' +
      '      <span>الفئة : ' + esc(catTitle(p.cat)) + '</span>' + sizeTagsHTML(p.sizes) + '</div>' +
      '    <span class="price">' + fmt(Number(p.price) || 0) + ' د.م.</span>' +
      '    <button class="btn-edit" data-action="edit" data-id="' + esc(p.id) + '" title="تعديل" aria-label="تعديل">' + EDIT_SVG + '</button>' +
      (p.custom
        ? '  <button class="btn-del" data-action="delete" data-id="' + esc(p.id) + '" title="حذف نهائي" aria-label="حذف نهائي">' + DEL_SVG + '</button>'
        : '') +
      '    <button class="btn-revoke" data-action="revoke" data-id="' + esc(p.id) + '" title="إزالة من القائمة" aria-label="إزالة من القائمة">' + REV_SVG + '</button>' +
      '  </div>' +
      '  <div class="prod-edit">' +
      '    <div class="prod-edit-grid">' +
      '      <input type="text" class="edit-name" value="' + esc(p.name) + '" placeholder="اسم المنتج">' +
      '      <input type="number" class="edit-price" value="' + esc(p.price != null ? p.price : '') + '" min="0" step="0.01" placeholder="السعر">' +
      '    </div>' +
      '    <div class="sizes-box"><div class="sizes-list">' + (p.sizes.length ? p.sizes.map(sizeRowHTML).join('') : sizeRowHTML(null)) + '</div>' +
      '      <button type="button" class="btn-add-size" data-add-size>إضافة حجم</button></div>' +
      '    <div class="edit-cat-wrap"><input type="text" class="edit-cat" value="' + esc(catTitle(p.cat)) + '" placeholder="الفئة"><div class="combo-dropdown"></div></div>' +
      '    <div class="edit-img-row"><input type="file" class="edit-file" accept="image/png,image/jpeg,image/webp,image/gif"><input type="url" class="edit-url" placeholder="https://.../photo.jpg" value="' + esc(p.img && p.img.startsWith("assets/uploads/") ? "" : p.img) + '" style="height:2.2rem"><span class="hint" style="font-size:.7rem">اترك فارغا للاحتفاظ بالصورة</span></div>' +
      '    <div class="prod-edit-actions"><button class="btn-save-sm" data-save="' + esc(p.id) + '">حفظ</button><button class="btn-cancel-sm" data-cancel="' + esc(p.id) + '">إلغاء</button></div>' +
      '  </div>' +
      '</div>'
    ).join('');

    Array.from(document.querySelectorAll('#catList [data-action="delete-cat"], [data-action="delete"], [data-action="revoke"]')).forEach((btn) => {
      btn.addEventListener('click', function () { handleAction(btn.dataset.action, btn.dataset.id); });
    });
    Array.from(box.querySelectorAll('[data-action="edit"]')).forEach((btn) => {
      btn.addEventListener('click', function () { enterEdit(btn.dataset.id); });
    });
    Array.from(box.querySelectorAll('[data-cancel]')).forEach((btn) => {
      btn.addEventListener('click', function () { cancelEdit(btn.getAttribute('data-cancel')); });
    });
    Array.from(box.querySelectorAll('[data-save]')).forEach((btn) => {
      btn.addEventListener('click', function () { saveEdit(btn.getAttribute('data-save')); });
    });
    // init per-row category autocomplete
    Array.from(box.querySelectorAll('.prod-row')).forEach((row) => {
      const inpCat = row.querySelector('.edit-cat');
      const dd = row.querySelector('.combo-dropdown');
      if(inpCat && dd) {
        inpCat.addEventListener('input', () => renderEditDropdown(inpCat, dd));
        inpCat.addEventListener('focus', () => renderEditDropdown(inpCat, dd));
      }
      // per-row sizes editor
      const sList = row.querySelector('.sizes-list');
      const sBtn = row.querySelector('[data-add-size]');
      if (sList && sBtn) {
        sBtn.addEventListener('click', () => addSizeRow(sList, null));
        Array.from(sList.querySelectorAll('[data-del-size]')).forEach((b) => {
          b.addEventListener('click', function () {
            if (sList.children.length > 1) b.closest('[data-size-row]').remove();
            else { b.closest('[data-size-row]').querySelector('.sr-size').value = ''; b.closest('[data-size-row]').querySelector('.sr-price').value = ''; }
          });
        });
      }
    });
    document.addEventListener('click', function onDocClick(e){
      // close edit dropdowns when clicking outside
      box.querySelectorAll('.combo-dropdown.show').forEach(dd=>{
        const wrap = dd.closest('.edit-cat-wrap');
        if(wrap && !wrap.contains(e.target)) dd.classList.remove('show');
      });
    }, {once:false});
  }

  function renderEditDropdown(inp, dd){
    const q = inp.value;
    const filtered = filterCats(q);
    const exact = findExactCategory(q);
    let html='';
    if(!filtered.length && !q.trim()){
      html='<div class="combo-empty">لا توجد فئة</div>';
    } else {
      html = filtered.map(c=>{
        const label = esc(c.title_ar) + ' <span>' + esc(c.title_fr || c.title_en || c.id) + '</span>';
        return '<div class="combo-item" data-id="'+esc(c.id)+'"><b>'+label+'</b><span>slug: '+esc(c.id)+'</span></div>';
      }).join('');
      if(q.trim() && !exact){
        if(q.trim().length>=2) html += '<div class="combo-item create" data-create="1">+ إنشاء « '+esc(q.trim())+' » كفئة جديدة</div>';
        else html += '<div class="combo-empty">واصل الكتابة لإنشاء « '+esc(q.trim())+' »</div>';
      }
      if(!html) html='<div class="combo-empty">لا توجد فئة مطابقة</div>';
    }
    dd.innerHTML=html; dd.classList.add('show');
    dd.querySelectorAll('.combo-item').forEach(el=>{
      el.addEventListener('click', ()=>{
        if(el.dataset.create){
          dd.classList.remove('show'); inp.focus();
          showMessage('سيتم إنشاء الفئة « '+q.trim()+' » تلقائيا عند الحفظ.', true);
        } else {
          const cat = CATS.find(x=>x.id===el.dataset.id);
          if(cat){ inp.value=cat.title_ar; dd.classList.remove('show'); }
        }
      });
    });
  }

  function enterEdit(id){
    const row = document.querySelector('.prod-row[data-id="'+CSS.escape(id)+'"]');
    if(row) row.classList.add('editing');
  }
  function cancelEdit(id){
    const row = document.querySelector('.prod-row[data-id="'+CSS.escape(id)+'"]');
    if(row){ row.classList.remove('editing'); const dd=row.querySelector('.combo-dropdown'); if(dd) dd.classList.remove('show'); }
  }
  async function saveEdit(id){
    const row = document.querySelector('.prod-row[data-id="'+CSS.escape(id)+'"]');
    if(!row) return;
    const name = row.querySelector('.edit-name').value.trim();
    const priceRaw = row.querySelector('.edit-price').value.trim();
    const catInput = row.querySelector('.edit-cat').value.trim();
    const fileInput = row.querySelector('.edit-file');
    const urlInput = row.querySelector('.edit-url').value.trim();
    if(!name){ showMessage('يرجى إدخال اسم المنتج.', false); return; }
    if(!catInput){ showMessage('يرجى إدخال الفئة.', false); return; }
    let price = null;
    if(priceRaw !== ""){ price = parseFloat(priceRaw); if(isNaN(price)||price<0){ showMessage('يرجى إدخال سعر صحيح.', false); return; } }
    const sizes = collectSizes(row.querySelector('.sizes-list'));
    if(!validateSizes(sizes)) return;
    // resolve category slug (auto-create if needed)
    let catSlug;
    try{
      catSlug = await ensureCategory(catInput);
    }catch(e){ if(e.status!==401) showMessage(e.message,false); return; }
    // resolve image
    let img = null; // null = keep old
    if(fileInput && fileInput.files[0]){
      const f=fileInput.files[0];
      if(!/^image\//.test(f.type)){ showMessage('يجب أن يكون الملف صورة.', false); return; }
      if(f.size>8*1024*1024){ showMessage('الصورة كبيرة جدا.', false); return; }
      img = await new Promise((res,rej)=>{
        const r=new FileReader(); r.onload=()=>res(r.result); r.onerror=()=>{showMessage('تعذر قراءة الصورة.',false); res(null);}; r.readAsDataURL(f);
      });
      if(img===null) return;
    } else if(urlInput){
      img = urlInput;
    } else {
      img = null;
    }
    const payload={};
    payload.name=name; payload.cat=catSlug;
    if(price!==null) payload.price=price; else payload.price="";
    payload.sizes = sizes;
    if(img!==null) payload.img=img;
    try{
      await api('/api/v1/products/'+encodeURIComponent(id)+'/update', {method:'POST', body: payload});
      showMessage('تم تحديث المنتج بنجاح.', true);
      loadList();
    }catch(e){ if(e.status!==401) showMessage(e.message,false); }
  }

  async function handleAction(action, id) {
    const msg = action === 'delete-cat'
      ? 'هل تريد حذف هذه الفئة نهائياً؟ لا يمكن التراجع عن هذا الإجراء.'
      : action === 'delete'
      ? 'هل تريد حذف هذا المنتج نهائياً؟ لا يمكن التراجع عن هذا الإجراء.'
      : 'هل تريد إزالة هذا المنتج من القائمة؟ سيبقى في الأرشيف.';
    if (!confirm(msg)) return;
    try {
      if (action === 'delete-cat') {
        await api('/api/v1/categories/' + encodeURIComponent(id), { method: 'DELETE' });
        showMessage('تم حذف الفئة.', true);
      } else if (action === 'delete') {
        await api('/api/v1/products/' + encodeURIComponent(id), { method: 'DELETE' });
        showMessage('تم حذف المنتج.', true);
      } else {
        await api('/api/v1/products/' + encodeURIComponent(id) + '/revoke', { method: 'POST', body: {} });
        showMessage('تمت إزالة المنتج من القائمة.', true);
      }
      loadList();
    } catch (e) {
      if (e.status !== 401) showMessage(e.message, false);
    }
  }

  /* ---------- sizes editor ---------- */
  function addSizeRow(list, s) {
    const row = document.createElement('div');
    row.innerHTML = sizeRowHTML(s);
    const del = row.querySelector('[data-del-size]');
    if (del) {
      del.addEventListener('click', function () {
        if (list.children.length > 1) row.remove();
        else { row.querySelector('.sr-size').value = ''; row.querySelector('.sr-price').value = ''; }
      });
    }
    list.appendChild(row);
    return row;
  }

  function initSizesEditor(list, addBtn) {
    if (!list) return;
    addBtn.addEventListener('click', function () { addSizeRow(list, null); });
    addSizeRow(list, null);
  }

  // Collect non-empty size rows into the API payload shape.
  function collectSizes(list) {
    if (!list) return [];
    const out = [];
    Array.from(list.querySelectorAll('[data-size-row]')).forEach((row) => {
      const size = row.querySelector('.sr-size').value.trim();
      const unit = row.querySelector('.sr-unit').value;
      const priceRaw = row.querySelector('.sr-price').value.trim();
      if (!size && !priceRaw) return; // fully empty row -> ignore
      out.push({ size: size, unit: unit, price: priceRaw === '' ? null : priceRaw });
    });
    return out;
  }

  // Client-side validation with a friendly message; server re-validates anyway.
  function validateSizes(sizes) {
    for (let i = 0; i < sizes.length; i++) {
      const s = sizes[i];
      if (!s.size) { showMessage('يرجى إدخال قيمة الحجم.', false); return false; }
      if (s.price === null || isNaN(parseFloat(s.price)) || parseFloat(s.price) < 0) {
        showMessage('يرجى إدخال سعر صحيح لكل حجم.', false); return false;
      }
    }
    return true;
  }

  function readImage() {
    return new Promise(function (resolve) {
      const file = $('#fFile').files[0];
      const url = $('#fUrl').value.trim();
      if (file) {
        if (!/^image\//.test(file.type)) { showMessage('يجب أن يكون الملف صورة.', false); return resolve(null); }
        if (file.size > 8 * 1024 * 1024) { showMessage('الصورة كبيرة جداً (الحد 8 ميغا).', false); return resolve(null); }
        const reader = new FileReader();
        reader.onload = function () { resolve(reader.result); };
        reader.onerror = function () { showMessage('تعذر قراءة الصورة.', false); resolve(null); };
        reader.readAsDataURL(file);
      } else {
        resolve(url);
      }
    });
  }

  function previewImage() {
    const box = $('#imgPreview');
    const file = $('#fFile').files[0];
    const apply = function (src) {
      box.classList.remove('empty');
      box.innerHTML = '<img src="' + src + '" alt="معاينة">';
    };
    if (file) {
      const r = new FileReader();
      r.onload = function () { apply(r.result); };
      r.readAsDataURL(file);
    } else if ($('#fUrl').value.trim()) {
      apply($('#fUrl').value.trim());
    }
  }

  function resetForm() {
    const p = $('#imgPreview');
    $('#productForm').reset();
    const sList = $('#sizesList');
    if (sList) { sList.innerHTML = ''; addSizeRow(sList, null); }
    p.classList.add('empty');
    p.innerHTML = '';
    closeDropdown();
  }

  async function ensureCategory(name) {
    const exact = findExactCategory(name);
    if (exact) return exact.id;
    const data = await api('/api/v1/categories', { method: 'POST', body: { name: name } });
    const c = data.category;
    CATS.push({ id: c.slug, title_ar: c.title_ar, title_fr: c.title_fr, title_en: c.title_en, img: c.img });
    return c.slug;
  }

  async function submitProduct(e) {
    e.preventDefault();
    const name = $('#fName').value.trim();
    const priceRaw = $('#fPrice').value.trim();
    const price = priceRaw === '' ? NaN : parseFloat(priceRaw);
    const catInput = $('#fCat').value.trim();
    const sizes = collectSizes($('#sizesList'));
    if (!name) { showMessage('يرجى إدخال اسم المنتج.', false); return; }
    if (!catInput) { showMessage('يرجى إدخال الفئة.', false); return; }
    if (catInput.length < 2) { showMessage('اسم الفئة يجب أن يكون حرفين على الأقل.', false); return; }
    if (!validateSizes(sizes)) return;
    // price required only when no explicit sizes are given
    if (!sizes.length && (isNaN(price) || price < 0)) { showMessage('يرجى إدخال سعر صحيح.', false); return; }
    showMessage('جاري الإضافة…', true);
    const img = await readImage();
    if (img === null) return;
    const body = { name: name, cat: catInput, img: img, sizes: sizes };
    if (!isNaN(price) && price >= 0) body.price = price;
    try {
      const catSlug = await ensureCategory(catInput);
      body.cat = catSlug;
      await api('/api/v1/products', { method: 'POST', body: body });
      showMessage('تمت إضافة المنتج بنجاح إلى « ' + catTitle(catSlug) + ' » !', true);
      resetForm();
      loadList();
    } catch (err) {
      if (err.status === 409 && err.payload && err.payload.id) {
        try {
          const fallback = err.payload.id;
          const img2 = img;
          body.cat = fallback;
          await api('/api/v1/products', { method: 'POST', body: body });
          showMessage('تمت إضافة المنتج بنجاح!', true);
          resetForm();
          loadList();
          return;
        } catch (e2) { if (e2.status !== 401) showMessage(e2.message, false); return; }
      }
      if (err.status !== 401) showMessage(err.message, false);
    }
  }

  async function init() {
    $('#fFile').addEventListener('change', previewImage);
    $('#fUrl').addEventListener('input', previewImage);
    initCategoryCombo();
    initSizesEditor($('#sizesList'), $('#btnAddSize'));

    const lo = $('#btnLogout');
    if (lo) lo.addEventListener('click', function () { AdminAuth.logout(); });

    $('#productForm').addEventListener('submit', submitProduct);

    await loadList();
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (!window.AdminAuth) return;
    AdminAuth.require(init);
  });
})();
