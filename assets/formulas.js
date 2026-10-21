/* E-testavimas: formulynas (VBE fizikos priedas) – mygtukas „📘 Formulynas“.
   Paveikslėliai atsisiunčiami tik pirmą kartą atidarius. Senas JavaScript. */
(function () {
  if (document.getElementById('ets-form-btn')) return;
  var base = new URL('app/static/', location.href).href;
  var pages = ['formulynas-1.jpg', 'formulynas-2.jpg'];

  var css = ''
    + '#ets-form-btn{position:fixed;right:14px;bottom:30px;z-index:100000;height:54px;padding:0 18px;border-radius:27px;'
    + 'background:#0f766e;color:#fff;font-size:18px;font-weight:600;border:none;box-shadow:0 4px 12px rgba(0,0,0,.25);cursor:pointer;font-family:sans-serif}'
    + '#ets-form{position:fixed;inset:0;left:0;top:0;right:0;bottom:0;z-index:99995;background:#e2e8f0;display:none;flex-direction:column;font-family:sans-serif}'
    + '#ets-form .bar{display:flex;gap:8px;align-items:center;padding:8px 10px;background:#fff;border-bottom:1px solid #cbd5e1}'
    + '#ets-form .b{font-size:16px;padding:8px 14px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;color:#1e293b;cursor:pointer;user-select:none}'
    + '#ets-form .x{margin-left:auto;background:#0f766e;color:#fff;border-color:#0f766e;font-weight:600}'
    + '#ets-form .sc{flex:1;overflow:auto;-webkit-overflow-scrolling:touch;padding:10px;text-align:center}'
    + '#ets-form img{display:block;margin:0 auto 12px;background:#fff;box-shadow:0 2px 8px rgba(0,0,0,.15)}'
    + '#ets-form .tt{font-size:15px;color:#334155;font-weight:600}';
  var st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);

  var btn = document.createElement('button');
  btn.id = 'ets-form-btn'; btn.type = 'button'; btn.textContent = '📘 Formulynas';
  document.body.appendChild(btn);

  var box = document.createElement('div'); box.id = 'ets-form';
  box.innerHTML = '<div class="bar"><span class="tt">📘 Formulės ir konstantos</span>'
    + '<span class="b" data-z="-1">−</span><span class="b" data-z="1">+</span>'
    + '<span class="b x" data-a="close">Uždaryti ✕</span></div><div class="sc"></div>';
  document.body.appendChild(box);
  var SC = box.querySelector('.sc'), zoom = 1, loaded = false;

  function size() {
    var w = Math.min(SC.clientWidth - 24, 900) * zoom;
    var imgs = SC.querySelectorAll('img');
    for (var i = 0; i < imgs.length; i++) imgs[i].style.width = Math.round(w) + 'px';
  }
  function others(show) {
    // Kol atidarytas formulynas, juodraščio ir formulyno mygtukai paslepiami (skaičiuotuvas lieka)
    ['ets-form-btn', 'ets-draft-btn'].forEach(function (id) { var e = document.getElementById(id); if (e) e.style.visibility = show ? '' : 'hidden'; });
  }
  function open() {
    box.style.display = 'flex'; others(false);
    if (!loaded) {
      loaded = true;
      for (var i = 0; i < pages.length; i++) {
        var im = document.createElement('img'); im.src = base + pages[i]; im.alt = 'Formulynas ' + (i + 1);
        SC.appendChild(im);
      }
    }
    size();
  }
  btn.addEventListener('click', open);
  box.addEventListener('click', function (e) {
    var t = e.target; if (!t || !t.getAttribute) return;
    var z = t.getAttribute('data-z');
    if (z) { zoom = Math.max(1, Math.min(2.5, zoom + parseInt(z, 10) * 0.5)); size(); }
    if (t.getAttribute('data-a') === 'close') { box.style.display = 'none'; others(true); }
  });
  window.addEventListener('resize', function () { if (box.style.display === 'flex') size(); });
})();
