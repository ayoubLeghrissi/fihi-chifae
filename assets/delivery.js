/* fihi-chifae : delivery fee rule shared by the storefront and the admin.
   Mirrors app/orders.py (the server always recomputes it):
   - free inside BHALIL / البهاليل (the shop's city), and for an empty city (in-shop sale);
   - free from 500 MAD of products;
   - otherwise 40 MAD. */
(function () {
  'use strict';

  var LATIN = ['bhalil', 'bahlil', 'bhalile', 'bhallil'];
  var ARABIC = ['البهاليل', 'بهاليل', 'البهليل', 'بهليل'];
  var settings = { delivery_fee: 40, free_delivery_threshold: 500 };

  function fold(s) {
    return String(s || '').normalize('NFKC').trim().replace(/[\s\-_.']+/g, '').toLowerCase();
  }

  /* Returns the canonical spelling of the shop's city, or the trimmed input. */
  function normalizeCity(city) {
    var c = String(city || '').replace(/\s+/g, ' ').trim();
    var f = fold(c);
    if (LATIN.indexOf(f) !== -1) return 'BHALIL';
    if (ARABIC.map(fold).indexOf(f) !== -1) return 'البهاليل';
    return c;
  }

  function isFreeCity(city) {
    var c = normalizeCity(city);
    return c === 'BHALIL' || c === 'البهاليل';
  }

  function fee(subtotal, city) {
    if (!String(city || '').trim() || isFreeCity(city)) return 0;
    if (Number(subtotal) >= Number(settings.free_delivery_threshold)) return 0;
    return Number(settings.delivery_fee);
  }

  function configure(s) {
    if (s && typeof s === 'object') {
      if (s.delivery_fee != null) settings.delivery_fee = Number(s.delivery_fee);
      if (s.free_delivery_threshold != null) settings.free_delivery_threshold = Number(s.free_delivery_threshold);
    }
  }

  window.Delivery = { fee: fee, normalizeCity: normalizeCity, isFreeCity: isFreeCity, configure: configure, settings: settings };
})();
