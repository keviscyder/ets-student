/* E-testavimas: vienas bendras juodraštis visam testui.
   Viskas vyksta planšetėje: piešinys saugomas planšetės atmintyje (localStorage),
   o į serverį siunčiamas tik uždarius juodraštį (jei kas nors pasikeitė).
   Todėl rašant niekas nesiunčiama ir puslapis nestringa.
   Rašyta senu JavaScript (be => ir let), kad veiktų ir senose planšetėse. */
(function () {
  var CFG = window.__etsDraftCfg || {};
  var KEY = 'ets-draft-' + (CFG.key || 'x');
  var old = document.getElementById('ets-draft-btn');
  if (old && old.getAttribute('data-key') === KEY) return;
  // Kitas testas tame pačiame lange – senas juodraštis pašalinamas
  ['ets-draft-btn', 'ets-draft'].forEach(function (id) { var e = document.getElementById(id); if (e) e.remove(); });

  var css = ''
    + '#ets-draft-btn{position:fixed;left:78px;bottom:14px;z-index:100000;height:54px;padding:0 18px;border-radius:27px;'
    + 'background:#1d4ed8;color:#fff;font-size:18px;font-weight:600;border:none;box-shadow:0 4px 12px rgba(0,0,0,.25);cursor:pointer;font-family:sans-serif}'
    + '#ets-draft{position:fixed;left:0;right:0;bottom:0;height:72%;z-index:99990;background:#f1f5f9;display:none;'
    + 'flex-direction:column;box-shadow:0 -6px 24px rgba(0,0,0,.25);border-top:3px solid #1d4ed8;font-family:sans-serif}'
    + '#ets-draft .bar{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:8px 10px;background:#fff;border-bottom:1px solid #cbd5e1}'
    + '#ets-draft .b{font-size:15px;padding:8px 12px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;color:#1e293b;cursor:pointer;user-select:none}'
    + '#ets-draft .b.on{background:#1e293b;color:#fff;border-color:#1e293b}'
    + '#ets-draft .x{margin-left:auto;background:#1d4ed8;color:#fff;border-color:#1d4ed8;font-weight:600}'
    + '#ets-draft .sc{flex:1;overflow-y:auto;-webkit-overflow-scrolling:touch;padding:10px}'
    + '#ets-draft canvas{display:block;margin:0 auto;background:#fff;border:1px solid #94a3b8;border-radius:6px;touch-action:none}'
    + '#ets-draft .tt{font-size:14px;color:#475569;font-weight:600}';
  var st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);

  var btn = document.createElement('button');
  btn.id = 'ets-draft-btn'; btn.type = 'button'; btn.textContent = '✏️ Juodraštis';
  btn.setAttribute('data-key', KEY);
  document.body.appendChild(btn);

  var box = document.createElement('div'); box.id = 'ets-draft';
  box.innerHTML = '<div class="bar">'
    + '<span class="tt">✏️ Juodraštis</span>'
    + '<span class="b on" data-t="black">Juodas</span><span class="b" data-t="blue">Mėlynas</span>'
    + '<span class="b" data-t="eraser">Trintukas</span>'
    + '<span class="b" data-a="undo">↶ Atgal</span><span class="b" data-a="clear">Išvalyti</span>'
    + '<span class="b" data-a="more">➕ Vietos</span>'
    + '<span class="b x" data-a="close">Uždaryti ✕</span></div>'
    + '<div class="sc"><canvas></canvas></div>';
  document.body.appendChild(box);

  var C = box.querySelector('canvas'), X = C.getContext('2d'), SC = box.querySelector('.sc');
  var W = 0, H = 1400, GRID = 25;
  var strokes = [], cur = null, bg = null, color = '#111827', erase = false, penSeen = false;
  var dirty = false, saveTimer = null, loaded = false;

  function key() { return btn.getAttribute('data-key'); }
  function lsGet(k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { window.localStorage.setItem(k, v); } catch (e) {} }

  function paper() {
    X.globalCompositeOperation = 'source-over';
    X.fillStyle = '#ffffff'; X.fillRect(0, 0, W, H);
    X.strokeStyle = '#dbeafe'; X.lineWidth = 1;
    for (var x = GRID; x < W; x += GRID) { X.beginPath(); X.moveTo(x + .5, 0); X.lineTo(x + .5, H); X.stroke(); }
    for (var y = GRID; y < H; y += GRID) { X.beginPath(); X.moveTo(0, y + .5); X.lineTo(W, y + .5); X.stroke(); }
    if (bg) X.drawImage(bg, 0, 0, W, bg.height * W / bg.width);
  }
  function line(s, from) {
    var p = s.pts; if (!p.length) return;
    X.lineCap = 'round'; X.lineJoin = 'round';
    X.strokeStyle = s.erase ? '#ffffff' : s.color; X.lineWidth = s.erase ? 16 : 2.5;
    X.beginPath(); var a = p[Math.max(0, from - 1)]; X.moveTo(a[0], a[1]);
    if (p.length === 1) X.lineTo(a[0] + .1, a[1] + .1);
    for (var i = Math.max(1, from); i < p.length; i++) X.lineTo(p[i][0], p[i][1]);
    X.stroke();
  }
  function redraw() { paper(); for (var i = 0; i < strokes.length; i++) line(strokes[i], 0); }
  function size() {
    var w = Math.min(SC.clientWidth - 22, 1100);
    if (w < 200) w = 600;
    if (bg) { var need = Math.round(bg.height * w / bg.width); if (need > H) H = need; }
    if (w !== W || C.height !== H) { W = w; C.width = W; C.height = H; C.style.width = W + 'px'; C.style.height = H + 'px'; redraw(); }
  }
  function load(cb) {
    loaded = true;
    var src = lsGet(key()) || CFG.url;
    if (!src) { cb(); return; }
    var img = new Image(); img.crossOrigin = 'anonymous';
    img.onload = function () { bg = img; cb(); };
    img.onerror = function () { cb(); };
    img.src = src;
  }
  function saveLocal() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(function () {
      try { lsSet(key(), C.toDataURL('image/jpeg', 0.6)); } catch (e) {}
    }, 800);
  }
  function changed() { dirty = true; saveLocal(); }

  function pos(e) { var r = C.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; }
  C.addEventListener('pointerdown', function (e) {
    if (e.pointerType === 'pen') penSeen = true;
    if (penSeen && e.pointerType === 'touch') return;
    try { C.setPointerCapture(e.pointerId); } catch (er) {}
    cur = { pts: [pos(e)], color: color, erase: erase }; line(cur, 0); e.preventDefault();
  });
  C.addEventListener('pointermove', function (e) {
    if (!cur) return;
    var n0 = cur.pts.length;
    var evs = e.getCoalescedEvents ? e.getCoalescedEvents() : [e];
    for (var i = 0; i < evs.length; i++) cur.pts.push(pos(evs[i]));
    line(cur, n0); e.preventDefault();
  });
  function end() { if (!cur) return; strokes.push(cur); cur = null; changed(); }
  C.addEventListener('pointerup', end); C.addEventListener('pointercancel', end);

  var clearArmed = null;
  box.addEventListener('click', function (e) {
    var t = e.target; if (!t || !t.getAttribute) return;
    var tool = t.getAttribute('data-t'), act = t.getAttribute('data-a');
    if (tool) {
      var all = box.querySelectorAll('[data-t]');
      for (var i = 0; i < all.length; i++) all[i].className = 'b';
      t.className = 'b on';
      erase = tool === 'eraser'; if (tool === 'black') color = '#111827'; if (tool === 'blue') color = '#1d4ed8';
    }
    if (act === 'undo' && strokes.length) { strokes.pop(); redraw(); changed(); }
    if (act === 'more') { H += 600; size(); changed(); SC.scrollTop = SC.scrollHeight; }
    if (act === 'clear') {
      if (!clearArmed) {
        t.textContent = 'Tikrai išvalyti?'; t.style.background = '#fee2e2';
        clearArmed = setTimeout(function () { clearArmed = null; t.textContent = 'Išvalyti'; t.style.background = ''; }, 3000);
      } else {
        clearTimeout(clearArmed); clearArmed = null; t.textContent = 'Išvalyti'; t.style.background = '';
        strokes = []; bg = null; H = 1400; W = 0; size(); changed();
      }
    }
    if (act === 'close') close();
  });

  function push() {
    // Į serverį siunčiam tik uždarant ir tik jei kas nors pasikeitė
    if (!dirty) return;
    var inp = document.querySelector('input[aria-label="ets_draft"]');
    if (!inp) return;
    var data = '';
    try { data = C.toDataURL('image/jpeg', 0.6); } catch (e) { return; }
    var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setter.call(inp, data);
    inp.dispatchEvent(new Event('input', { bubbles: true }));
    // Streamlit laukelį įrašo paspaudus Enter (keypress)
    ['keydown', 'keypress', 'keyup'].forEach(function (t) {
      inp.dispatchEvent(new KeyboardEvent(t, { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, charCode: 13, bubbles: true }));
    });
    dirty = false;
  }
  function open() {
    box.style.display = 'flex'; btn.style.display = 'none';
    if (!loaded) load(function () { W = 0; size(); }); else size();
  }
  function close() {
    box.style.display = 'none'; btn.style.display = '';
    clearTimeout(saveTimer);
    try { lsSet(key(), C.toDataURL('image/jpeg', 0.6)); } catch (e) {}
    push();
  }
  btn.addEventListener('click', open);
  window.addEventListener('resize', function () { if (box.style.display === 'flex') size(); });
  // Pateikiant testą – nusiunčiam paskutinę juodraščio versiją
  document.addEventListener('click', function (e) {
    var b = e.target && e.target.closest && e.target.closest('button');
    if (b && b.innerText && b.innerText.indexOf('Pateikti testą') >= 0 && dirty) push();
  }, true);
})();
