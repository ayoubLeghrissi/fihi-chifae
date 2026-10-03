/* fihi-chifae (فيه شفاء) - storefront : i18n (ar/fr/en), DB-driven catalog, cart, checkout, WhatsApp chat. */

(function () {
  'use strict';

  /* ---------- helpers ---------- */
  const $ = (s, c) => (c || document).querySelector(s);
  const $$ = (s, c) => Array.from((c || document).querySelectorAll(s));
  const esc = (s) => String(s).replace(/[&<>"']/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));

  /* ---------- brand ---------- */
  const BRAND = {
    ar: 'فيه <b>شفاء</b>',
    fr: 'fihi-<b>chifae</b>',
    en: 'fihi-<b>chifae</b>',
  };

  /* ---------- WhatsApp command ---------- */
  // Orders are also sent by WhatsApp to the shop's number (international format, digits only).
  const WHATSAPP_NUMBER = '212682884917';
  const WA_TEMPLATE = {
    ar: 'مرحباً، أرسل لكم طلبية جديدة من متجر فيه شفاء 🛒\n\nالمنتجات :\n{LINES}المجموع : {TOTAL}\n\nالاسم : {NAME}\nالهاتف : {PHONE}\n\nشكراً لكم 🌿',
    fr: "Bonjour, je vous envoie une nouvelle commande depuis la boutique fihi-chifae 🛒\n\nProduits :\n{LINES}Total : {TOTAL}\n\nNom : {NAME}\nTéléphone : {PHONE}\n\nMerci 🌿",
    en: "Hello, here is a new order from fihi-chifae 🛒\n\nProducts:\n{LINES}Total: {TOTAL}\n\nName: {NAME}\nPhone: {PHONE}\n\nThank you 🌿",
  };

  function waMessage() {
    const tpl = WA_TEMPLATE[LANG] || WA_TEMPLATE.en;
    const lines = cart.length
      ? cart.map((it) => '• ' + it.qty + ' × ' + it.name + ' (' + money(Number(it.price) || 0) + ')').join('\n') + '\n'
      : '';
    return tpl
      .replace('{LINES}', lines)
      .replace('{TOTAL}', money(cartTotal()))
      .replace('{NAME}', $('#checkoutName').value.trim() || '—')
      .replace('{PHONE}', $('#checkoutPhone').value.trim() || '—');
  }

  function updateWaHref() {
    const btn = $('#waBtn');
    if (!btn) return;
    btn.href = 'https://wa.me/' + String(WHATSAPP_NUMBER).replace(/[^0-9]/g, '') + '?text=' + encodeURIComponent(waMessage());
  }

  const CARtIcon = '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="21" r="1.6" fill="currentColor" stroke="none"/><circle cx="20" cy="21" r="1.6" fill="currentColor" stroke="none"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const HEART_ICON = '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" stroke-linejoin="round"/></svg>';

  /* ---------- i18n ---------- */
  let LANG = 'ar';
  const NATIVE = { ar: 'العربية', fr: 'Français', en: 'English' };

  const T = {
    ar: {
      announce: 'التوصيل مجاني ابتداءً من 500 درهم، وبخلاف ذلك تكون تكاليف التوصيل 40 درهم.',
      masthead_sub: 'الطبيعة المغربية',
      account: 'حسابي',
      cart_title: '{n} منتوج في السلة',
      search_placeholder: 'ابحث عن منتج',
      search_btn: 'بحث',
      open_cart: 'فتح السلة',
      view_cart: 'مشاهدة السلة',
      hero_title: '"فيه شفاء"... الطعم الأصيل للطبيعة المغربية، منتجات طبيعية 100% بدون إضافات',
      hero_sub: 'العسل المغربي الخالص... كما يجب أن يكون',
      hero_cta: 'اكتشف منتجاتنا',
      trust_natural: '100% طبيعي',
      trust_delivery: 'التوصيل داخل المغرب',
      trust_additives: 'بدون إضافات',
      hf1_sub: 'ضمان بدون إضافات',
      hf2_sub: 'آراء العملاء',
      featured_eyebrow: 'أفضل مبيعاتنا',
      featured_title: 'المنتجات الأكثر مبيعاً',
      featured_sub: 'تشكيلة من المنتجات المفضلة لدى عملائنا، مباشرة من قلب الطبيعة المغربية.',
      strip1_title: 'منتجات طازجة',
      strip1_sub: 'محضّرة بعناية',
      strip2_title: 'توصيل سريع',
      strip2_sub: 'في جميع أنحاء المغرب',
      strip3_title: 'الدفع عند الاستلام',
      strip3_sub: 'قرب منزلك',
      strip4_title: '100% طبيعي',
      strip4_sub: 'بدون إضافات',
      news_title: 'توصل بآخر المنتجات والعروض الحصرية',
      news_sub: 'مباشرة إلى بريدك الإلكتروني',
      news_placeholder: 'أدخل بريدك الإلكتروني',
      news_btn: 'اشترك',
      footer_brand: 'فيه شفاء علامة مغربية متخصصة في إنتاج وتعبئة العسل الطبيعي ومنتجات الخلية. نقدم عسلاً نقياً 100% ومنتجات تقليدية عالية الجودة من قلب الطبيعة المغربية.',
      fc1_title: 'الشركة',
      fc1_about: 'من نحن',
      fc1_privacy: 'سياسة الخصوصية',
      fc1_terms: 'شروط الاستخدام',
      fc1_faq: 'الأسئلة الشائعة',
      fc2_title: 'مساعدة',
      fc2_track: 'تتبع الطلبية',
      fc2_ship: 'الشحن والتوصيل',
      fc2_return: 'سياسة الإرجاع',
      fc2_contact: 'اتصل بنا',
      fc3_title: 'تواصل معنا',
      copyright: 'جميع الحقوق محفوظة © 2026 fihi-chifae',
      wa_chat: 'شات معنا عبر واتساب',
      admin_link: 'الإدارة',
      wa_bot_name: 'فيه شفاء - المساعد',
      wa_bot_status: 'متصل الآن • يرد عادة خلال دقائق',
      wa_bot_placeholder: 'اكتب رسالتك...',
      search_hint: 'اكتب اسم منتج لبدء البحث.',
      search_ph: 'ابحث عن منتج...',
      no_results: 'لا يوجد منتج يطابق « {q} »',
      count_products: '{n} منتوج',
      add_to_cart: 'أضف إلى السلة',
      add_fav: 'أضف إلى المفضلة',
      promo: 'عرض',
      price_on_request: 'السعر عند الطلب',
      cart_empty: 'سلتك فارغة.',
      cart_remove: 'إزالة',
      cart_dec: 'تخفيض',
      cart_inc: 'زيادة',
      cart_total_label: 'المجموع',
      checkout_btn: 'تأكيد الطلب',
      checkout_name: 'الاسم الكامل',
      checkout_phone: 'رقم الهاتف',
      name_required: 'يرجى إدخال اسمك الكامل قبل تأكيد الطلب.',
      newsletter_invalid: 'يرجى إدخال بريد إلكتروني صحيح.',
      newsletter_ok: 'شكراً! تم اشتراكك بنجاح.',
      added_to_cart: 'تمت إضافة « {p} » إلى السلة',
      order_success: 'تم تأكيد طلبيتك بنجاح. شكراً!',
      order_error: 'تعذر إرسال الطلب. يرجى المحاولة مرة أخرى.',
      catalog_offline: 'تعذر تحميل المنتجات. تأكد من تشغيل الخادم (python server.py).',
    },

    fr: {
      announce: 'Livraison gratuite à partir de 500 MAD, sinon les frais de livraison sont de 40 MAD.',
      masthead_sub: 'Maroc naturel',
      account: 'Mon compte',
      cart_title: '{n} article dans le panier',
      search_placeholder: 'Rechercher un produit',
      search_btn: 'Rechercher',
      open_cart: 'Ouvrir le panier',
      view_cart: 'Voir le panier',
      hero_title: "fihi-chifae... le goût authentique de la nature marocaine, des produits 100% naturels sans additifs.",
      hero_sub: 'Le miel pur marocain... comme il doit être',
      hero_cta: 'Découvrez nos produits',
      trust_natural: '100% Naturel',
      trust_delivery: 'Livraison au Maroc',
      trust_additives: 'Sans additifs',
      hf1_sub: 'garanti sans additifs',
      hf2_sub: 'avis clients',
      featured_eyebrow: 'Nos coups de cœur',
      featured_title: 'Produits les plus vendus',
      featured_sub: 'Une sélection des produits préférés de nos clients, directement du cœur de la nature marocaine.',
      strip1_title: 'Produits frais',
      strip1_sub: 'récoltés avec soin',
      strip2_title: 'Livraison rapide',
      strip2_sub: 'partout au Maroc',
      strip3_title: 'Paiement à la livraison',
      strip3_sub: 'près de chez vous',
      strip4_title: '100% Naturel',
      strip4_sub: 'sans additifs',
      news_title: 'Recevez les derniers produits et offres exclusives',
      news_sub: 'directement dans votre boîte mail',
      news_placeholder: 'Entrez votre email',
      news_btn: "S'abonner",
      footer_brand: 'fihi-chifae est une marque marocaine spécialisée dans la production et le conditionnement du miel naturel et des produits de la ruche. Nous proposons un miel pur à 100% et des produits traditionnels de haute qualité issus du cœur de la nature marocaine.',
      fc1_title: 'Entreprise',
      fc1_about: 'À propos de notre marque',
      fc1_privacy: 'Politique de confidentialité',
      fc1_terms: "Conditions d'utilisation",
      fc1_faq: 'Questions fréquentes',
      fc2_title: 'Aide',
      fc2_track: 'Suivre la commande',
      fc2_ship: 'Expédition et livraison',
      fc2_return: 'Politique de retour',
      fc2_contact: 'Contactez-nous',
      fc3_title: 'Nous contacter',
      copyright: "Droits d'auteur © 2026 fihi-chifae. Tous droits réservés.",
      wa_chat: 'Discuter avec nous sur WhatsApp',
      admin_link: 'Administration',
      wa_bot_name: 'fihi-chifae - Assistant',
      wa_bot_status: 'En ligne • répond en quelques minutes',
      wa_bot_placeholder: 'Écrivez votre message...',
      search_hint: 'Tapez un nom de produit pour lancer la recherche.',
      search_ph: 'Rechercher un produit...',
      no_results: 'Aucun produit ne correspond à « {q} »',
      count_products: '{n} produits',
      add_to_cart: 'Ajouter au panier',
      add_fav: 'Ajouter aux favoris',
      promo: 'Promo',
      price_on_request: 'Prix sur demande',
      cart_empty: 'Votre panier est vide.',
      cart_remove: 'Retirer',
      cart_dec: 'Diminuer',
      cart_inc: 'Augmenter',
      cart_total_label: 'Total',
      checkout_btn: 'Valider la commande',
      checkout_name: 'Nom complet',
      checkout_phone: 'Téléphone',
      name_required: 'Veuillez saisir votre nom complet pour valider la commande.',
      newsletter_invalid: 'Veuillez saisir un email valide.',
      newsletter_ok: 'Merci ! Vous êtes bien abonné(e).',
      added_to_cart: '« {p} » ajouté au panier',
      order_success: 'Commande validée. Merci !',
      order_error: "Impossible d'envoyer la commande. Réessayez.",
      catalog_offline: 'Impossible de charger les produits. Assurez-vous que le serveur tourne (python server.py).',
    },

    en: {
      announce: 'Free delivery from 500 MAD, otherwise delivery fees are 40 MAD.',
      masthead_sub: 'Natural Morocco',
      account: 'My account',
      cart_title: '{n} items in cart',
      search_placeholder: 'Search for a product',
      search_btn: 'Search',
      open_cart: 'Open cart',
      view_cart: 'View cart',
      hero_title: 'fihi-chifae... the authentic taste of Moroccan nature, 100% natural products with no additives.',
      hero_sub: 'Pure Moroccan honey... as it should be',
      hero_cta: 'Discover our products',
      trust_natural: '100% Natural',
      trust_delivery: 'Delivery in Morocco',
      trust_additives: 'No additives',
      hf1_sub: 'guaranteed no additives',
      hf2_sub: 'customer reviews',
      featured_eyebrow: 'Our favourites',
      featured_title: 'Best selling products',
      featured_sub: 'A selection of our customers’ favourite products, straight from the heart of Moroccan nature.',
      strip1_title: 'Fresh products',
      strip1_sub: 'harvested with care',
      strip2_title: 'Fast delivery',
      strip2_sub: 'anywhere in Morocco',
      strip3_title: 'Cash on delivery',
      strip3_sub: 'close to you',
      strip4_title: '100% Natural',
      strip4_sub: 'no additives',
      news_title: 'Get the latest products and exclusive offers',
      news_sub: 'straight to your inbox',
      news_placeholder: 'Enter your email',
      news_btn: 'Subscribe',
      footer_brand: 'fihi-chifae is a Moroccan brand specialising in the production and packaging of natural honey and hive products. We offer 100% pure honey and high-quality traditional products from the heart of Moroccan nature.',
      fc1_title: 'Company',
      fc1_about: 'About our brand',
      fc1_privacy: 'Privacy policy',
      fc1_terms: 'Terms of use',
      fc1_faq: 'Frequently asked questions',
      fc2_title: 'Help',
      fc2_track: 'Track order',
      fc2_ship: 'Shipping and delivery',
      fc2_return: 'Return policy',
      fc2_contact: 'Contact us',
      fc3_title: 'Contact us',
      copyright: '© 2026 fihi-chifae. All rights reserved.',
      wa_chat: 'Chat with us on WhatsApp',
      admin_link: 'Administration',
      wa_bot_name: 'fihi-chifae - Assistant',
      wa_bot_status: 'Online • replies in minutes',
      wa_bot_placeholder: 'Type a message...',
      search_hint: 'Type a product name to start searching.',
      search_ph: 'Search for a product...',
      no_results: 'No product matches « {q} »',
      count_products: '{n} products',
      add_to_cart: 'Add to cart',
      add_fav: 'Add to favourites',
      promo: 'Promo',
      price_on_request: 'Price on request',
      cart_empty: 'Your cart is empty.',
      cart_remove: 'Remove',
      cart_dec: 'Decrease',
      cart_inc: 'Increase',
      cart_total_label: 'Total',
      checkout_btn: 'Place order',
      checkout_name: 'Full name',
      checkout_phone: 'Phone',
      name_required: 'Please enter your full name to place the order.',
      newsletter_invalid: 'Please enter a valid email.',
      newsletter_ok: 'Thank you! You are now subscribed.',
      added_to_cart: '« {p} » added to cart',
      order_success: 'Order confirmed. Thank you!',
      order_error: 'Unable to send the order. Please try again.',
      catalog_offline: 'Unable to load products. Make sure the server is running (python server.py).',
    },
  };

  function t(key, sub) {
    let s = (T[LANG] && T[LANG][key]) || T.fr[key] || key;
    if (sub !== undefined && sub !== null && s.indexOf('{') !== -1) s = s.replace('{p}', String(sub)).replace('{n}', String(sub)).replace('{q}', String(sub));
    return s;
  }

  function money(n) {
    const v = Number(n || 0);
    const base = v.toFixed(2);
    const s = LANG === 'en' ? base : base.replace('.', ',');
    if (LANG === 'ar') return 'د.م. ' + s;
    return s + ' MAD';
  }

  /* ---------- data (from SQLite via API) ---------- */
  const DATA = { categories: [], featured: [] };
  let loaded = false;

  function locCat(slug) {
    const s = String(slug).replace(/^cat-/, '');
    const c = DATA.categories.find((x) => x.id === s);
    if (!c) return null;
    return c['title_' + LANG] || c.title_ar;
  }

  function loadCatalog(cb) {
    fetch('/api/v1/catalog', { cache: 'no-store' })
      .then((r) => { if (!r.ok) throw new Error('api'); return r.json(); })
      .then((data) => {
        if (Array.isArray(data.categories)) { DATA.categories = data.categories; DATA.featured = data.featured || []; loaded = true; }
        cb();
      })
      .catch(() => { loaded = false; cb(); });
  }

  /* ---------- i18n apply ---------- */
  function applyI18n() {
    document.documentElement.lang = LANG;
    document.documentElement.dir = LANG === 'ar' ? 'rtl' : 'ltr';
    $('#langCurrent').textContent = NATIVE[LANG] || 'العربية';
    $$('#langMenu .lang-item').forEach((el) => el.classList.toggle('active', el.dataset.lang === LANG));
    $$('.footer-lang a').forEach((el) => el.classList.toggle('active', el.dataset.lang === LANG));

    $$('.logo-text').forEach((el) => { el.innerHTML = BRAND[LANG] || BRAND.en; });

    $$('[data-i18n]').forEach((el) => {
      const key = el.dataset.i18n;
      const k = key.replace(/-/g, '_');
      if (key.indexOf('cat-') === 0) { el.textContent = locCat(key) || t(k); }
      else el.textContent = t(k);
    });
    $$('[data-i18n-title]').forEach((el) => { el.title = t(el.dataset.i18nTitle.replace(/-/g, '_')); });
    $$('[data-i18n-ph]').forEach((el) => { el.placeholder = t(el.dataset.i18nPh.replace(/-/g, '_')); });

    const si = $('#searchInput'), sl = $('#searchLive');
    if (si) si.placeholder = t('search_placeholder');
    if (sl) sl.placeholder = t('search_ph');
    if (sl) sl.setAttribute('aria-label', t('search_placeholder'));

    $('#checkoutName').placeholder = t('checkout_name');
    $('#checkoutName').setAttribute('aria-label', t('checkout_name'));
    $('#checkoutPhone').placeholder = t('checkout_phone');
    $('#checkoutPhone').setAttribute('aria-label', t('checkout_phone'));

    if (loaded) renderCatalog();
    renderCart();
  }

  function setLang(l) {
    LANG = l;
    try { localStorage.setItem('dhenbio_lang', l); } catch (e) { /* ignore */ }
    applyI18n();
  }

  /* ---------- price ---------- */
  function priceLabel(p) {
    if (p.min && p.max) return money(p.min) + ' - ' + money(p.max);
    if (p.min) return money(p.min);
    return t('price_on_request');
  }

  function cardHTML(p, img) {
    return (
      '<article class="prod-card" data-name="' + esc(p.name) + '" data-price="' + (p.min || '') + '" data-cat="' + esc(p.cat || 'autres') + '" data-img="' + esc(img) + '">' +
      '  <div class="prod-media">' +
      (p.ribbon ? '<span class="prod-ribbon">' + t('promo') + '</span>' : '') +
      '    <img src="' + esc(img) + '" alt="' + esc(p.name) + '">' +
      '    <button class="prod-heart" aria-label="' + t('add_fav') + '">' + HEART_ICON + '</button>' +
      '  </div>' +
      '  <div class="prod-body">' +
      '    <h3 class="prod-name">' + esc(p.name) + '</h3>' +
      '    <span class="prod-price">' + priceLabel(p) + '</span>' +
      '    <button class="btn-add">' + CARtIcon + ' ' + t('add_to_cart') + '</button>' +
      '  </div>' +
      '</article>'
    );
  }

  function buildFLAT() {
    const out = [];
    DATA.categories.forEach((cat) => {
      cat.products.forEach((p) => out.push({ name: p.name, min: p.min, max: p.max, img: p.img || cat.img, cat: cat.id, catTitle: cat['title_' + LANG] || cat.title_ar }));
    });
    return out;
  }

  /* ---------- render catalog ---------- */
  function renderCatalog() {
    const featured = $('#featuredGrid');
    if (featured) featured.innerHTML = loaded ? DATA.featured.map((p) => cardHTML(p, p.img || PIMG(p.cat))).join('') : offlineMsg();
    const wrap = $('#catSections');
    if (!loaded) { wrap.innerHTML = offlineMsg(); applyCatalogTitles(); return; }

    wrap.innerHTML = DATA.categories.map((cat) => {
      const title = cat['title_' + LANG] || cat.title_ar;
      return (
        '<section class="cat-section" id="' + 'cat-' + cat.id + '" data-title="' + esc(title) + '">' +
        '  <div class="cat-head" role="button" tabindex="0" aria-expanded="true">' +
        '    <h2>' + esc(title) + '</h2>' +
        '    <span class="count">' + t('count_products', cat.products.length) + '</span>' +
        '    <svg class="cat-caret" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m6 9 6 6 6-6" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
        '  </div>' +
        '  <div class="cat-body">' + cat.products.map((p) => cardHTML(p, p.img || cat.img)).join('') + '</div>' +
        '</section>'
      );
    }).join('');

    $$('.cat-head').forEach((head) => {
      const sec = head.closest('.cat-section');
      head.addEventListener('click', () => {
        const collapsed = sec.classList.toggle('collapsed');
        head.setAttribute('aria-expanded', String(!collapsed));
      });
      head.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); head.click(); } });
    });

    applyCatalogTitles();
    bindCartButtons();
  }

  function PIMG(catSlug) {
    const c = DATA.categories.find((x) => x.id === catSlug);
    return c ? c.img : 'assets/hero.svg';
  }

  function offlineMsg() {
    return '<div class="search-empty" style="grid-column:1/-1;padding:3rem">' + esc(t('catalog_offline')) + '</div>';
  }

  function renderCatBar() {
    const bar = $('#catBar');
    const mob = $('#mobileNav');
    if (!bar && !mob) return;
    if (!loaded || !DATA.categories.length) {
      if (bar) bar.innerHTML = '';
      if (mob) mob.innerHTML = '';
      return;
    }
    const html = DATA.categories.map((cat, idx) => {
      const title = esc(cat['title_' + LANG] || cat.title_ar);
      const active = idx === 0 ? ' active' : '';
      return '<a href="#cat-' + esc(cat.id) + '" class="cat-link' + active + '">' + title + '</a>';
    }).join('');
    const mobHtml = DATA.categories.map((cat) => {
      const title = esc(cat['title_' + LANG] || cat.title_ar);
      return '<a href="#cat-' + esc(cat.id) + '" class="mobile-nav-link">' + title + '</a>';
    }).join('');
    if (bar) bar.innerHTML = html;
    if (mob) mob.innerHTML = mobHtml;
    // re-bind smooth scroll closing mobile menu
    $$('#mobileNav .mobile-nav-link').forEach((a) => {
      a.addEventListener('click', () => {
        const menu = $('#mobileMenu');
        if (menu) menu.classList.remove('open');
        document.body.style.overflow = '';
      });
    });
  }

  function applyCatalogTitles() {
    renderCatBar();
  }

  /* ---------- cart ---------- */
  let cart = [];
  try { cart = JSON.parse(localStorage.getItem('dhenbio_cart') || '[]'); } catch (e) { cart = []; }

  function saveCart() { try { localStorage.setItem('dhenbio_cart', JSON.stringify(cart)); } catch (e) { /* ignore */ } }
  function cartCount() { return cart.reduce((s, it) => s + it.qty, 0); }
  function cartTotal() { return cart.reduce((s, it) => s + it.qty * (Number(it.price) || 0), 0); }

  function updateBadges() {
    const c = String(cartCount());
    const badge = $('#cartCount');
    if (badge) badge.textContent = c;
    const top = $('#topCartCount');
    if (top) top.textContent = c;
    const head = $('#cartDrawer h3');
    if (head) head.textContent = t('cart_title', cartCount());
    const cartLink = document.querySelector('.link-cart');
    if (cartLink) cartLink.title = t('cart_title', cartCount());
  }

  function addToCart(name, price, img, cat, qty) {
    const existing = cart.find((it) => it.name === name);
    if (existing) existing.qty += qty; else cart.push({ name: name, price: Number(price) || 0, img: img, cat: cat || 'autres', qty: qty });
    saveCart(); updateBadges(); renderCart();
    toast(t('added_to_cart', name));
  }

  function renderCart() {
    const body = $('#cartBody');
    const foot = $('#cartFoot');
    updateBadges();
    if (!cart.length) {
      body.innerHTML = '<div class="cart-empty">' + CARtIcon + '<p>' + t('cart_empty') + '</p></div>';
      if (foot) foot.style.display = 'none';
      $('#cartTotal').textContent = money(0);
      updateWaHref();
      return;
    }
    if (foot) foot.style.display = 'block';
    body.innerHTML =
      '<ul class="cart-items">' + cart.map((it, i) =>
        '<li class="cart-item">' +
        '  <img src="' + esc(it.img) + '" alt="' + esc(it.name) + '">' +
        '  <div class="cart-item-info"><b>' + esc(it.name) + '</b><span>' + money(it.price) + '</span>' +
        '    <div class="qty">' +
        '      <button data-dec="' + i + '" aria-label="' + t('cart_dec') + '">−</button><em>' + it.qty + '</em><button data-inc="' + i + '" aria-label="' + t('cart_inc') + '">+</button>' +
        '    </div></div>' +
        '  <button class="cart-item-del" data-del="' + i + '" aria-label="' + t('cart_remove') + '">' +
        '    <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6" stroke-linecap="round"/></svg>' +
        '  </button>' +
        '</li>'
      ).join('') + '</ul>';
    $('#cartTotal').textContent = money(cartTotal());

    $$('.qty button').forEach((b) => {
      b.addEventListener('click', () => {
        const i = Number(b.dataset.dec !== undefined ? b.dataset.dec : b.dataset.inc);
        cart[i].qty += b.dataset.inc !== undefined ? 1 : -1;
        if (cart[i].qty <= 0) cart.splice(i, 1);
        saveCart(); updateBadges(); renderCart();
      });
    });
    $$('.cart-item-del').forEach((b) => {
      b.addEventListener('click', () => {
        cart.splice(Number(b.dataset.del), 1);
        saveCart(); updateBadges(); renderCart();
      });
    });
    updateWaHref();
  }

  function bindCartButtons() {
    $$('.btn-add').forEach((btn) => {
      btn.addEventListener('click', () => {
        const card = btn.closest('.prod-card');
        addToCart(card.dataset.name, card.dataset.price, card.dataset.img, card.dataset.cat, 1);
      });
    });
    $$('.prod-heart').forEach((btn) => {
      btn.addEventListener('click', () => {
        btn.classList.toggle('liked');
        btn.querySelector('svg').setAttribute('fill', btn.classList.contains('liked') ? 'currentColor' : 'none');
      });
    });
  }

  /* ---------- toasts ---------- */
  function toast(msg) {
    const box = $('#toasts');
    const el = document.createElement('div');
    el.className = 'toast';
    el.innerHTML = '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M20 6 9 17l-5-5" stroke-linecap="round" stroke-linejoin="round"/></svg>' + esc(msg);
    box.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; el.style.transform = 'translateY(8px)'; setTimeout(() => el.remove(), 300); }, 2600);
  }

  /* ---------- search ---------- */
  function openSearch() {
    $('#searchPanel').classList.add('open');
    const box = $('#searchLive');
    box.value = $('#searchInput').value || '';
    $('#searchInput').value = '';
    box.focus();
    doSearch(box.value);
  }

  function closeSearch() { $('#searchPanel').classList.remove('open'); }

  function doSearch(q) {
    const res = $('#searchResults');
    const ql = (q || '').trim().toLowerCase();
    if (!ql) { res.innerHTML = '<div class="search-empty">' + t('search_hint') + '</div>'; return; }
    const FLAT = buildFLAT();
    const hits = FLAT.filter((p) => p.name.toLowerCase().indexOf(ql) !== -1);
    if (!hits.length) { res.innerHTML = '<div class="search-empty">' + t('no_results', q.trim()) + '</div>'; return; }
    res.innerHTML = hits.map((p) => cardHTML(p, p.img)).join('');
    bindCartButtons();
  }

  /* ---------- language dropdown ---------- */
  function initLang() {
    const btn = $('#langBtn'), menu = $('#langMenu');
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const open = menu.classList.toggle('show');
      btn.setAttribute('aria-expanded', String(open));
    });
    $$('#langMenu .lang-item').forEach((item) => {
      item.addEventListener('click', () => setLang(item.dataset.lang));
    });
    $$('.footer-lang a').forEach((a) => { a.addEventListener('click', (e) => { e.preventDefault(); setLang(a.dataset.lang); }); });
    document.addEventListener('click', (e) => {
      if (!$('#langSelect').contains(e.target)) { menu.classList.remove('show'); btn.setAttribute('aria-expanded', 'false'); }
    });
    btn.addEventListener('keydown', (e) => { if (e.key === 'Escape') menu.classList.remove('show'); });
  }

  /* ---------- mobile menu / drawers ---------- */
  function initMenus() {
    const menu = $('#mobileMenu');
    $('#menuBtn').addEventListener('click', () => { menu.classList.add('open'); document.body.style.overflow = 'hidden'; });
    function closeMenu() { menu.classList.remove('open'); document.body.style.overflow = ''; }
    $('#closeMenu').addEventListener('click', closeMenu);
    menu.addEventListener('click', (e) => { if (e.target === menu) closeMenu(); });
    $$('a', menu).forEach((a) => a.addEventListener('click', closeMenu));

    const drawer = $('#cartDrawer'), overlay = $('#overlay');
    const openCart = () => { drawer.classList.add('open'); overlay.classList.add('show'); };
    const closeCart = () => { drawer.classList.remove('open'); overlay.classList.remove('show'); };
    $('#openCart').addEventListener('click', openCart);
    $('#mobileCartBtn').addEventListener('click', () => { closeMenu(); openCart(); });
    $('#closeCart').addEventListener('click', closeCart);
    overlay.addEventListener('click', closeCart);
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { closeCart(); closeSearch(); $('.mobile-menu').classList.remove('open'); } });
  }

  /* ---------- newsletter / checkout ---------- */
  function initForms() {
    $('#newsletterForm').addEventListener('submit', (e) => {
      e.preventDefault();
      const em = $('#newsletterEmail');
      if (!em.value || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(em.value)) { toast(t('newsletter_invalid')); return; }
      em.value = ''; toast(t('newsletter_ok'));
    });
    $('#checkoutBtn').addEventListener('click', submitOrder);
  }

  function submitOrder() {
    if (!cart.length) { toast(t('cart_empty')); return; }
    const buyer = $('#checkoutName').value.trim();
    if (!buyer) { toast(t('name_required')); return; }
    const phone = $('#checkoutPhone').value.trim();
    const items = cart.map((it) => ({ name: it.name, price: it.price, qty: it.qty, cat: it.cat || 'autres' }));

    // Chat via WhatsApp with the order details (name + products + quantities).
    const waHref = 'https://wa.me/' + WHATSAPP_NUMBER + '?text=' + encodeURIComponent(waMessage());

    const checkoutBtn = $('#checkoutBtn');
    checkoutBtn.disabled = true;

    // 1) record the order server-side (admin dashboard + Excel export)
    fetch('/api/v1/orders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ buyer: buyer, phone: phone, items: items }),
    }).catch(() => { /* WhatsApp below is the reliable channel even offline */ });

    // 2) deliver the order to the shop via WhatsApp (opened in the click gesture)
    window.open(waHref, '_blank');

    cart = []; saveCart(); updateBadges(); renderCart();
    $('#checkoutName').value = ''; $('#checkoutPhone').value = '';
    toast(t('order_success'));
    setTimeout(() => { checkoutBtn.disabled = false; }, 400);
  }

  /* ---------- WhatsApp Chatbot (simple, order-integrated) ---------- */
  const BOT_T = {
    ar: {
      name: 'فيه شفاء - المساعد',
      status: 'متصل الآن • يرد عادة خلال دقائق',
      placeholder: 'اكتب رسالتك...',
      welcome: 'مرحبا بكم في فيه شفاء 🌿\nأنا مساعدكم الواتساب. كيف أساعدكم في طلبكم؟',
      emptyCart: 'سلتك فارغة حاليا.\nتصفح منتجاتنا وأضف ما يعجبك، ثم ارجع لتأكيد الطلب.',
      cartHeader: 'لديك {n} منتج في السلة:',
      cartTotal: 'المجموع: {t}',
      askName: 'ما هو اسمكم الكريم؟ (سيُستخدم لتأكيد الطلب)',
      askPhone: 'ما هو رقم هاتفكم للتواصل والتوصيل؟',
      askConfirm: 'هل تريد تأكيد الطلب الآن؟',
      confirmBtn: 'تأكيد الطلب ✅',
      viewCartBtn: 'عرض السلة 🛒',
      helpBtn: 'المساعدة 💬',
      deliveryBtn: 'معلومات التوصيل 🚚',
      productsBtn: 'تصفح المنتجات 🍯',
      yes: 'نعم، تأكيد',
      no: 'إلغاء',
      thanks: 'شكرا! تم استلام طلبكم بنجاح ✅\nسأحولكم إلى واتساب لإرسال التفاصيل مباشرة.',
      waOpen: 'فتح واتساب 📲',
      fallback: 'لم أفهم تماما. اختر من الأزرار السريعة أو اكتب: تأكيد، سلة، توصيل، منتجات.',
      deliveryInfo: 'التوصيل مجاني ابتداء من 500 درهم، وإلا 40 درهم. نوصل جميع أنحاء المغرب خلال 24-48 ساعة. الدفع عند الاستلام.',
      invalidPhone: 'يرجى إدخال رقم هاتف صحيح (8 أرقام على الأقل).',
      needName: 'يرجى إدخال الاسم أولا.',
      orderEmpty: 'لا يمكن تأكيد طلب فارغ. أضف منتجات أولا.'
    },
    fr: {
      name: 'fihi-chifae - Assistant',
      status: 'En ligne • répond en quelques minutes',
      placeholder: 'Écrivez votre message...',
      welcome: 'Bienvenue chez fihi-chifae 🌿\nJe suis votre assistant WhatsApp. Comment vous aider pour votre commande ?',
      emptyCart: 'Votre panier est vide.\nParcourez nos produits et revenez pour confirmer.',
      cartHeader: 'Vous avez {n} article dans le panier :',
      cartTotal: 'Total : {t}',
      askName: 'Quel est votre nom ?',
      askPhone: 'Quel est votre numéro de téléphone ?',
      askConfirm: 'Voulez-vous confirmer la commande ?',
      confirmBtn: 'Confirmer ✅',
      viewCartBtn: 'Voir panier 🛒',
      helpBtn: 'Aide 💬',
      deliveryBtn: 'Livraison 🚚',
      productsBtn: 'Produits 🍯',
      yes: 'Oui, confirmer',
      no: 'Annuler',
      thanks: 'Merci ! Commande reçue ✅\nJe vous redirige vers WhatsApp.',
      waOpen: 'Ouvrir WhatsApp 📲',
      fallback: "Je n'ai pas compris. Choisissez un bouton ou écrivez : confirmer, panier, livraison, produits.",
      deliveryInfo: 'Livraison gratuite dès 500 MAD, sinon 40 MAD. Partout au Maroc en 24-48h. Paiement à la livraison.',
      invalidPhone: 'Veuillez saisir un numéro valide (au moins 8 chiffres).',
      needName: 'Veuillez saisir votre nom.',
      orderEmpty: 'Impossible de confirmer un panier vide.'
    },
    en: {
      name: 'fihi-chifae - Assistant',
      status: 'Online • replies in minutes',
      placeholder: 'Type a message...',
      welcome: 'Welcome to fihi-chifae 🌿\nI am your WhatsApp assistant. How can I help with your order?',
      emptyCart: 'Your cart is empty.\nBrowse products and come back to confirm.',
      cartHeader: 'You have {n} item in cart:',
      cartTotal: 'Total: {t}',
      askName: 'What is your name?',
      askPhone: 'What is your phone number?',
      askConfirm: 'Do you want to confirm the order?',
      confirmBtn: 'Confirm ✅',
      viewCartBtn: 'View cart 🛒',
      helpBtn: 'Help 💬',
      deliveryBtn: 'Delivery 🚚',
      productsBtn: 'Products 🍯',
      yes: 'Yes, confirm',
      no: 'Cancel',
      thanks: 'Thank you! Order received ✅\nRedirecting you to WhatsApp.',
      waOpen: 'Open WhatsApp 📲',
      fallback: 'Sorry, I did not understand. Choose a button or type: confirm, cart, delivery, products.',
      deliveryInfo: 'Free delivery from 500 MAD, otherwise 40 MAD. All over Morocco 24-48h. Cash on delivery.',
      invalidPhone: 'Please enter a valid phone (at least 8 digits).',
      needName: 'Please enter your name.',
      orderEmpty: 'Cannot confirm empty cart.'
    }
  };
  function botLang(){ return BOT_T[LANG] || BOT_T.ar; }
  let botStage = 'idle';
  let botFirstOpen = true;
  function waBotTime(){ return new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}); }
  function waBotScroll(){ const c = $('#waBotMessages'); if(c) c.scrollTop = c.scrollHeight; }
  function waBotAddBot(text, quicks){
    const box = $('#waBotMessages'); if(!box) return;
    const div = document.createElement('div'); div.className='wa-msg bot';
    div.innerHTML = esc(text).replace(/\n/g,'<br>') + '<small>'+waBotTime()+'</small>';
    box.appendChild(div); waBotScroll();
    waBotShowQuick(quicks);
  }
  function waBotAddUser(text){
    const box = $('#waBotMessages'); if(!box) return;
    const div = document.createElement('div'); div.className='wa-msg user';
    div.innerHTML = esc(text).replace(/\n/g,'<br>') + '<small>'+waBotTime()+'</small>';
    box.appendChild(div); waBotScroll();
  }
  function waBotShowQuick(quicks){
    const q = $('#waBotQuick'); if(!q) return; q.innerHTML='';
    (quicks||[]).forEach(o=>{
      const b=document.createElement('button'); b.className='wa-quick-btn'; b.textContent=o.label;
      b.addEventListener('click', ()=> waBotHandle(o.value||o.label));
      q.appendChild(b);
    });
  }
  function waBotCartSummary(){
    const b = botLang();
    if(!cart.length) return b.emptyCart;
    const items = cart.map(it=> '• '+it.qty+' × '+it.name+' ('+money(Number(it.price)||0)+')').join('\n');
    return b.cartHeader.replace('{n}', cart.length) + '\n' + items + '\n' + b.cartTotal.replace('{t}', money(cartTotal()));
  }
  function waBotHandle(input){
    const raw = String(input||'').trim(); if(!raw) return;
    const norm = raw.toLowerCase();
    const b = botLang();
    // stages awaiting name/phone/confirm
    if(botStage==='awaitName'){
      if(raw.length<2){ waBotAddBot(b.needName); return; }
      $('#checkoutName').value = raw; updateWaHref();
      botStage='idle'; waBotAddUser(raw);
      setTimeout(()=> waBotAskPhone(), 400); return;
    }
    if(botStage==='awaitPhone'){
      const digits = raw.replace(/[^0-9+]/g,'');
      if(digits.replace(/[^0-9]/g,'').length < 8){ waBotAddBot(b.invalidPhone); return; }
      $('#checkoutPhone').value = raw; updateWaHref();
      botStage='idle'; waBotAddUser(raw);
      setTimeout(()=> waBotAskConfirm(), 400); return;
    }
    if(botStage==='awaitConfirm'){
      if(norm.includes('نعم')||norm.includes('confirm')||norm.includes('oui')||norm.includes('yes')||norm==='confirm'){
        waBotAddUser(raw); botStage='idle'; waBotDoOrder(); return;
      }
      if(norm.includes('إلغاء')||norm.includes('cancel')||norm.includes('annuler')){
        waBotAddUser(raw); botStage='idle'; waBotAddBot(b.fallback, waBotDefaultQuicks()); return;
      }
    }
    waBotAddUser(raw);
    // intent routing
    if(norm.includes('تأكيد')||norm.includes('confirm')||norm.includes('confirmer')||norm.includes('تاكيد')){
      waBotTryConfirm(); return;
    }
    if(norm.includes('سلة')||norm.includes('panier')||norm.includes('cart')||norm.includes('عرض')){
      waBotAddBot(waBotCartSummary(), [{label:b.confirmBtn,value:'confirm'},{label:b.deliveryBtn,value:'delivery'}]); return;
    }
    if(norm.includes('توصيل')||norm.includes('livraison')||norm.includes('delivery')){
      waBotAddBot(b.deliveryInfo, waBotDefaultQuicks()); return;
    }
    if(norm.includes('منتج')||norm.includes('produit')||norm.includes('product')||norm.includes('عسل')||norm.includes('miel')){
      waBotAddBot(b.help+ '\n' + b.deliveryInfo, waBotDefaultQuicks()); return;
    }
    if(norm.includes('مرحبا')||norm.includes('سلام')||norm.includes('bonjour')||norm.includes('hello')||norm.includes('hi')){
      waBotWelcome(); return;
    }
    if(norm.includes('مساعدة')||norm.includes('aide')||norm.includes('help')){
      waBotAddBot(b.help, waBotDefaultQuicks()); return;
    }
    waBotAddBot(b.fallback, waBotDefaultQuicks());
  }
  function waBotDefaultQuicks(){
    const b=botLang();
    if(!cart.length) return [{label:b.productsBtn,value:'products'},{label:b.helpBtn,value:'help'}];
    return [{label:b.confirmBtn,value:'confirm'},{label:b.viewCartBtn,value:'cart'},{label:b.deliveryBtn,value:'delivery'}];
  }
  function waBotWelcome(){
    const b=botLang();
    waBotAddBot(b.welcome + '\n\n' + waBotCartSummary(), waBotDefaultQuicks());
  }
  function waBotAskName(){
    const b=botLang(); botStage='awaitName';
    waBotAddBot(b.askName, []);
  }
  function waBotAskPhone(){
    const b=botLang(); botStage='awaitPhone';
    waBotAddBot(b.askPhone, []);
  }
  function waBotAskConfirm(){
    const b=botLang(); botStage='awaitConfirm';
    waBotAddBot(waBotCartSummary() + '\n\n' + b.askConfirm, [{label:b.yes,value:'confirm'},{label:b.no,value:'cancel'}]);
  }
  function waBotTryConfirm(){
    const b=botLang();
    if(!cart.length){ waBotAddBot(b.orderEmpty, [{label:b.productsBtn,value:'products'}]); return; }
    const name = ($('#checkoutName').value||'').trim();
    const phone = ($('#checkoutPhone').value||'').trim();
    if(!name){ waBotAskName(); return; }
    if(!phone){ waBotAskPhone(); return; }
    waBotAskConfirm();
  }
  function waBotDoOrder(){
    const b=botLang();
    const name = ($('#checkoutName').value||'').trim();
    const phone = ($('#checkoutPhone').value||'').trim();
    if(!name||!phone||!cart.length){ waBotAddBot(b.fallback); return; }
    const items = cart.map(it=>({name:it.name,price:it.price,qty:it.qty,cat:it.cat||'autres'}));
    // record order same as submitOrder but without opening blank immediately (keep in bot)
    fetch('/api/v1/orders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({buyer:name,phone:phone,items:items})}).catch(()=>{});
    const href = 'https://wa.me/'+String(WHATSAPP_NUMBER).replace(/[^0-9]/g,'')+'?text='+encodeURIComponent(waMessage());
    waBotAddBot(b.thanks, [{label:b.waOpen,value:'__wa'}]);
    // quick action to open wa
    setTimeout(()=>{
      const q = $('#waBotQuick'); if(!q) return;
      const btn = q.querySelector('button');
      // override first quick to open wa
      const waBtn = document.createElement('button'); waBtn.className='wa-quick-btn'; waBtn.textContent=b.waOpen;
      waBtn.addEventListener('click', ()=> window.open(href,'_blank'));
      q.innerHTML=''; q.appendChild(waBtn);
      const closeBtn = document.createElement('button'); closeBtn.className='wa-quick-btn'; closeBtn.textContent=b.no;
      closeBtn.addEventListener('click', ()=> waBotAddBot(b.help, waBotDefaultQuicks()));
      q.appendChild(closeBtn);
    }, 300);
    cart=[]; try{localStorage.setItem('dhenbio_cart', JSON.stringify(cart));}catch(e){}
    updateBadges(); renderCart(); updateWaHref();
    toast(t('order_success'));
  }
  function waBotOpen(){
    const ov = $('#waBotOverlay'); if(!ov) return;
    ov.classList.add('open'); ov.setAttribute('aria-hidden','false');
    document.body.style.overflow='hidden';
    if(botFirstOpen){ botFirstOpen=false; setTimeout(waBotWelcome, 300); }
    setTimeout(()=>{ const inp=$('#waBotInput'); if(inp) inp.focus(); }, 250);
  }
  function waBotClose(){
    const ov = $('#waBotOverlay'); if(!ov) return;
    ov.classList.remove('open'); ov.setAttribute('aria-hidden','true');
    document.body.style.overflow=''; botStage='idle';
  }
  function initChatbot(){
    const overlay = $('#waBotOverlay');
    const closeBtn = $('#waBotClose');
    const input = $('#waBotInput');
    const send = $('#waBotSend');
    const waBtn = $('#waBtn');
    if(!overlay||!input||!send) return;
    // waBtn in cart drawer: intercept to open bot instead of direct wa.me
    if(waBtn){
      waBtn.addEventListener('click', (e)=>{
        e.preventDefault();
        // close cart drawer first
        const drawer = $('#cartDrawer'); const ov2 = $('#overlay');
        if(drawer) drawer.classList.remove('open'); if(ov2) ov2.classList.remove('show');
        waBotOpen();
      });
    }
    // also FAB if any (not yet, but input will handle)
    if(closeBtn) closeBtn.addEventListener('click', waBotClose);
    overlay.addEventListener('click', (e)=>{ if(e.target===overlay) waBotClose(); });
    function doSend(){
      const v = input.value.trim(); if(!v) return; input.value=''; waBotHandle(v);
    }
    send.addEventListener('click', doSend);
    input.addEventListener('keydown', (e)=>{ if(e.key==='Enter'){ e.preventDefault(); doSend(); } });
    // keep bot language in sync with LANG changes
    const origSetLang = window.setLang;
    // expose for i18n refresh: update placeholder and header on lang change
    const origApply = window.applyI18n;
    // we hook via polling LANG in waBotTime? simpler: on every applyI18n we could update placeholder, but main.js applyI18n is private.
    // So we listen to storage or just update placeholder on open via botLang()
    // add helper to update bot UI language
    document.addEventListener('click', (e)=>{
      const t = e.target.closest('[data-lang]');
      if(t){ setTimeout(()=>{
        const inp2 = $('#waBotInput'); if(inp2) inp2.placeholder = botLang().placeholder;
        const nameEl = document.querySelector('[data-i18n="wa_bot_name"]'); if(nameEl) nameEl.textContent=botLang().name;
        const stEl = document.querySelector('[data-i18n="wa_bot_status"]'); if(stEl) stEl.textContent=botLang().status;
      }, 100); }
    });
    // init placeholder
    input.placeholder = botLang().placeholder;
  }

  /* ---------- init ---------- */
  document.addEventListener('DOMContentLoaded', function () {
    try { const l = localStorage.getItem('dhenbio_lang'); if (l && T[l]) LANG = l; } catch (e) { /* ignore */ }
    document.documentElement.lang = LANG;
    document.documentElement.dir = LANG === 'ar' ? 'rtl' : 'ltr';

    loadCatalog(function () {
      applyI18n();
      updateBadges();
      renderCart();
      initLang();
      initMenus();
      initForms();
      try{ initChatbot(); }catch(e){}

      $('#searchBtn').addEventListener('click', openSearch);
      $('#searchInput').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); openSearch(); } });
      $('#closeSearch').addEventListener('click', closeSearch);
      $('#searchLive').addEventListener('input', (e) => doSearch(e.target.value));
      $('#searchPanel').addEventListener('click', (e) => { if (e.target === e.currentTarget) closeSearch(); });

      const sections = $$('.cat-section');
      const barLinks = $$('.cat-link');
      const io = new IntersectionObserver((entries) => {
        entries.forEach((en) => {
          if (en.isIntersecting) {
            barLinks.forEach((l) => l.classList.toggle('active', l.getAttribute('href') === '#' + en.target.id));
          }
        });
      }, { rootMargin: '-40% 0px -55% 0px' });
      sections.forEach((s) => io.observe(s));
    });
  });
})();