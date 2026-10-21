/* E-testavimas: rašomų atsakymų apsauga.
   1) Kol mokinys rašo, tekstas nuolat saugomas planšetės atmintyje (localStorage).
   2) Kai mokinys 4 s nieko nerašo, atsakymas nusiunčiamas į serverį
      (nereikia spausti už laukelio ribų, klaviatūra lieka atidaryta).
   3) Jei programa persikrovė ir laukelis tuščias, tekstas grąžinamas iš atminties
      ir nusiunčiamas į serverį.
   Rašyta senu JavaScript, kad veiktų ir senose planšetėse. */
(function () {
  var CFG = window.__etsGuardCfg || {};
  var SUB = CFG.key || 'x';
  if (window.__etsGuardSub === SUB) return;
  var first = !window.__etsGuardSub;
  window.__etsGuardSub = SUB;
  if (!first) return;   // klausytojai jau įdiegti – naudos naują SUB

  function wkey(el) {
    var c = el.closest && el.closest('[class*="st-key-ans_"],[class*="st-key-final_"]');
    if (!c) return null;
    var cl = c.className.split(' ');
    for (var i = 0; i < cl.length; i++) if (cl[i].indexOf('st-key-') === 0) return cl[i].slice(7);
    return null;
  }
  function sk(k) { return 'ets-ans-' + window.__etsGuardSub + '-' + k; }
  function get(k) { try { return window.localStorage.getItem(sk(k)); } catch (e) { return null; } }
  function put(k, v) { try { window.localStorage.setItem(sk(k), v); } catch (e) {} }
  function isField(el) { return el && (el.tagName === 'TEXTAREA' || (el.tagName === 'INPUT' && el.type === 'text')); }

  function commit(el) {
    if (!el || !el.isConnected) return;
    var o = { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, charCode: 13, bubbles: true };
    if (el.tagName === 'TEXTAREA') {
      o.ctrlKey = true;   // Streamlit tekstinį lauką išsaugo Ctrl+Enter
      el.dispatchEvent(new KeyboardEvent('keydown', o));
    } else {
      ['keydown', 'keypress', 'keyup'].forEach(function (t) { el.dispatchEvent(new KeyboardEvent(t, o)); });
    }
  }
  function setVal(el, v) {
    var proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, v);
    el.dispatchEvent(new Event('input', { bubbles: true }));
  }

  var timers = {};
  document.addEventListener('input', function (e) {
    var el = e.target;
    if (!isField(el) || el.__etsRestoring) return;
    var k = wkey(el); if (!k) return;
    put(k, el.value);
    clearTimeout(timers[k]);
    timers[k] = setTimeout(function () { commit(el); }, 4000);
  }, true);

  // Išeinant iš programėlės – iškart nusiunčiam rašomą atsakymą
  function flush() {
    var el = document.activeElement;
    if (isField(el) && wkey(el)) commit(el);
  }
  document.addEventListener('visibilitychange', function () { if (document.hidden) flush(); });
  window.addEventListener('ets-hidden', flush);

  // Po persikrovimo: tušti laukeliai užpildomi iš planšetės atminties
  var restored = {};
  function restore() {
    var els = document.querySelectorAll('[class*="st-key-ans_"] textarea,[class*="st-key-ans_"] input[type="text"],[class*="st-key-final_"] input[type="text"]');
    for (var i = 0; i < els.length; i++) {
      var el = els[i], k = wkey(el);
      if (!k || restored[k]) continue;
      var v = get(k);
      if (v && !el.value) {
        restored[k] = true;
        el.__etsRestoring = true;
        setVal(el, v);
        el.__etsRestoring = false;
        (function (x) { setTimeout(function () { commit(x); }, 300); })(el);
      } else if (el.value) {
        restored[k] = true;
      }
    }
  }
  setInterval(restore, 2000);
  setTimeout(restore, 800);
})();
