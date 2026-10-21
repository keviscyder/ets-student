/* E-testavimas: planšetės baterija. Rodo „🔋 54%“ viršuje dešinėje ir
   (testo metu) praneša mokytojui, kai lygis pasikeičia bent 5 %. Senas JavaScript. */
(function () {
  if (window.__etsBattery) { window.__etsBattery(); return; }
  if (!navigator.getBattery) return;   // naršyklė baterijos neparodo
  var B = null;
  var el = document.createElement('div');
  el.id = 'ets-batt';
  el.style.cssText = 'position:fixed;top:8px;right:12px;z-index:100000;font:600 14px sans-serif;'
    + 'padding:3px 9px;border-radius:12px;background:#f1f5f9;color:#334155;pointer-events:none';
  document.body.appendChild(el);

  function push(level) {
    var inp = document.querySelector('input[aria-label="ets_batt"]');
    if (!inp) return;
    // kiekvienam laukeliui (naujam testo puslapiui) siunčiam iš naujo
    if (inp.__etsSent !== undefined && Math.abs(inp.__etsSent - level) < 5) return;
    var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setter.call(inp, String(level));
    inp.dispatchEvent(new Event('input', { bubbles: true }));
    ['keydown', 'keypress', 'keyup'].forEach(function (t) {
      inp.dispatchEvent(new KeyboardEvent(t, { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, charCode: 13, bubbles: true }));
    });
    inp.__etsSent = level;
  }
  function show() {
    if (!B) return;
    var lv = Math.round(B.level * 100);
    el.textContent = (B.charging ? '⚡ ' : '🔋 ') + lv + '%';
    el.style.background = lv <= 15 && !B.charging ? '#fee2e2' : (lv <= 30 && !B.charging ? '#fef3c7' : '#f1f5f9');
    el.style.color = lv <= 15 && !B.charging ? '#b91c1c' : '#334155';
    push(lv);
  }
  window.__etsBattery = function () { setTimeout(show, 1500); };   // po perpiešimo patikrinam dar kartą
  navigator.getBattery().then(function (b) {
    B = b; show();
    b.addEventListener('levelchange', show);
    b.addEventListener('chargingchange', show);
  }).catch(function () { el.remove(); });
})();
