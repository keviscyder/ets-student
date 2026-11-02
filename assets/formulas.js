/* E-testavimas: egzaminų formulynai (NŠA priedai) – mygtukas „📘 Formulynas“.
   Kurie formulynai rodomi – window.ETS_FORM_SHEETS = [{t: 'Fizika', p: ['formulynas-1.jpg', ...]}, ...].
   Paveikslėliai atsisiunčiami tik pirmą kartą atidarius. Senas JavaScript (WebView 119). */
(function () {
  if (document.getElementById('ets-form-btn')) return;
  var base = new URL('app/static/', location.href).href;
  var sheets = window.ETS_FORM_SHEETS || [{ t: 'Fizika', p: ['formulynas-1.jpg', 'formulynas-2.jpg'] }];
  var cur = 0;

  var css = ''
    + '#ets-form-btn{position:fixed;right:14px;bottom:30px;z-index:100000;height:54px;padding:0 18px;border-radius:27px;'
    + 'background:#0f766e;color:#fff;font-size:18px;font-weight:600;border:none;box-shadow:0 4px 12px rgba(0,0,0,.25);cursor:pointer;font-family:sans-serif}'
    + '#ets-form{position:fixed;inset:0;left:0;top:0;right:0;bottom:0;z-index:99995;background:#e2e8f0;display:none;flex-direction:column;font-family:sans-serif}'
    + '#ets-form .bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:8px 10px;background:#fff;border-bottom:1px solid #cbd5e1}'
    + '#ets-form .b{font-size:16px;padding:8px 14px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;color:#1e293b;cursor:pointer;user-select:none}'
    + '#ets-form .x{margin-left:auto;background:#0f766e;color:#fff;border-color:#0f766e;font-weight:600}'
    + '#ets-form .sc{flex:1;overflow:auto;-webkit-overflow-scrolling:touch;padding:10px;text-align:center}'
    + '#ets-form img{display:block;margin:0 auto 12px;background:#fff;box-shadow:0 2px 8px rgba(0,0,0,.15)}'
    + '#ets-form .tt{font-size:15px;color:#334155;font-weight:600}'
    + '#ets-form .tabs{display:flex;gap:6px;flex-wrap:wrap}'
    + '#ets-form .tab{font-size:15px;padding:7px 12px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;color:#1e293b;cursor:pointer;user-select:none}'
    + '#ets-form .tab.on{background:#ccfbf1;border-color:#0f766e;color:#0f766e;font-weight:600}';
  var st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);

  var btn = document.createElement('button');
  btn.id = 'ets-form-btn'; btn.type = 'button'; btn.textContent = '📘 Formulynas';
  btn.setAttribute('data-key', window.ETS_FORM_KEY || '');
  document.body.appendChild(btn);

  var box = document.createElement('div'); box.id = 'ets-form';
  var tabs = '';
  if (sheets.length > 1) {
    tabs = '<span class="tabs">';
    for (var k = 0; k < sheets.length; k++) tabs += '<span class="tab' + (k === 0 ? ' on' : '') + '" data-s="' + k + '">' + sheets[k].t + '</span>';
    tabs += '</span>';
  } else tabs = '<span class="tt">📘 ' + sheets[0].t + '</span>';
  box.innerHTML = '<div class="bar">' + tabs
    + '<span class="b" data-z="-1">−</span><span class="b" data-z="1">+</span>'
    + '<span class="b x" data-a="close">Uždaryti ✕</span></div><div class="sc"></div>';
  document.body.appendChild(box);
  var SC = box.querySelector('.sc'), zoom = 1, shown = -1;

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
    show(cur);
  }
  function show(n) {
    cur = n;
    if (shown !== n) {
      shown = n; SC.innerHTML = ''; SC.scrollTop = 0;
      var pages = sheets[n].p;
      for (var i = 0; i < pages.length; i++) {
        var im = document.createElement('img'); im.src = base + pages[i]; im.alt = sheets[n].t + ' ' + (i + 1);
        SC.appendChild(im);
      }
      var tb = box.querySelectorAll('.tab');
      for (var j = 0; j < tb.length; j++) tb[j].className = 'tab' + (j === n ? ' on' : '');
    }
    size();
  }
  btn.addEventListener('click', open);
  box.addEventListener('click', function (e) {
    var t = e.target; if (!t || !t.getAttribute) return;
    var sIdx = t.getAttribute('data-s');
    if (sIdx !== null) { show(parseInt(sIdx, 10)); return; }
    var z = t.getAttribute('data-z');
    if (z) { zoom = Math.max(1, Math.min(2.5, zoom + parseInt(z, 10) * 0.5)); size(); }
    if (t.getAttribute('data-a') === 'close') { box.style.display = 'none'; others(true); }
  });
  window.addEventListener('resize', function () { if (box.style.display === 'flex') size(); });
})();
