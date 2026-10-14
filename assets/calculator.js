/* E-testavimas skaičiuotuvas: plaukiojantis mygtukas ir langas testo puslapyje.
   Skaičiuoja be eval(): savas išraiškų skaitytuvas. Veikia ir senose naršyklėse. */
(function () {
  if (document.getElementById('ets-calc-btn')) return;

  var css = ''
    + '#ets-calc-btn{position:fixed;left:14px;bottom:14px;z-index:100000;width:54px;height:54px;border-radius:50%;'
    + 'background:#1e293b;color:#fff;font-size:26px;border:none;box-shadow:0 4px 12px rgba(0,0,0,.25);cursor:pointer}'
    + '#ets-calc{position:fixed;left:14px;bottom:78px;z-index:100000;width:290px;background:#fff;border:1px solid #cbd5e1;'
    + 'border-radius:14px;box-shadow:0 8px 28px rgba(0,0,0,.25);padding:10px;display:none;font-family:sans-serif;user-select:none}'
    + '#ets-calc .hd{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;font-size:13px;color:#64748b}'
    + '#ets-calc .x{background:none;border:none;font-size:20px;color:#64748b;cursor:pointer}'
    + '#ets-calc .ex{min-height:20px;font-size:15px;color:#64748b;text-align:right;word-break:break-all}'
    + '#ets-calc .rs{min-height:34px;font-size:28px;font-weight:600;color:#0f172a;text-align:right;word-break:break-all;margin-bottom:8px}'
    + '#ets-calc .g{display:grid;grid-template-columns:repeat(5,1fr);gap:6px}'
    + '#ets-calc .g button{height:44px;font-size:18px;border:1px solid #e2e8f0;border-radius:8px;background:#f8fafc;color:#0f172a;cursor:pointer}'
    + '#ets-calc .g button.op{background:#e2e8f0}'
    + '#ets-calc .g button.eq{background:#1e293b;color:#fff}'
    + '#ets-calc .g button.fn{font-size:15px}';
  var st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);

  var btn = document.createElement('button'); btn.id = 'ets-calc-btn'; btn.title = 'Skaičiuotuvas'; btn.textContent = '🧮';
  var box = document.createElement('div'); box.id = 'ets-calc';
  var keys = [
    ['C', 'fn'], ['⌫', 'fn'], ['(', 'op'], [')', 'op'], ['÷', 'op'],
    ['x²', 'fn'], ['7', ''], ['8', ''], ['9', ''], ['×', 'op'],
    ['√', 'fn'], ['4', ''], ['5', ''], ['6', ''], ['−', 'op'],
    ['xʸ', 'fn'], ['1', ''], ['2', ''], ['3', ''], ['+', 'op'],
    ['π', 'fn'], ['×10ⁿ', 'fn'], ['0', ''], [',', ''], ['=', 'eq']
  ];
  var html = '<div class="hd"><span>Skaičiuotuvas</span><button class="x" title="Uždaryti">✕</button></div>'
    + '<div class="ex"></div><div class="rs">0</div><div class="g">';
  for (var i = 0; i < keys.length; i++) html += '<button class="' + keys[i][1] + '" data-k="' + keys[i][0] + '">' + keys[i][0] + '</button>';
  box.innerHTML = html + '</div>';
  document.body.appendChild(btn); document.body.appendChild(box);

  var expr = '', last = null;
  var exEl = box.querySelector('.ex'), rsEl = box.querySelector('.rs');

  function fmt(x) {
    if (!isFinite(x)) return 'Klaida';
    var r = Math.abs(x) >= 1e12 || (Math.abs(x) < 1e-6 && x !== 0) ? x.toExponential(6) : String(parseFloat(x.toPrecision(12)));
    return r.replace('.', ',').replace('e+', ' ×10^').replace('e-', ' ×10^-');
  }
  function show() { rsEl.textContent = expr === '' ? (last === null ? '0' : fmt(last)) : expr; }

  /* --- išraiškos skaičiavimas --- */
  function evaluate(s) {
    s = s.replace(/×10\^/g, 'E').replace(/×/g, '*').replace(/÷/g, '/').replace(/−/g, '-')
         .replace(/,/g, '.').replace(/π/g, 'p').replace(/√/g, 'r').replace(/\s/g, '');
    var i = 0;
    function peek() { return s.charAt(i); }
    function num() {
      var j = i;
      while (/[0-9.]/.test(peek())) i++;
      var v = parseFloat(s.slice(j, i));
      if (isNaN(v)) throw 'x';
      if (peek() === 'E') { i++; var sg = 1; if (peek() === '-') { sg = -1; i++; } var k = i; while (/[0-9]/.test(peek())) i++; v = v * Math.pow(10, sg * parseInt(s.slice(k, i) || '0', 10)); }
      return v;
    }
    function atom() {
      var c = peek();
      if (c === '(') { i++; var v = add(); if (peek() === ')') i++; return v; }
      if (c === 'p') { i++; return Math.PI; }
      if (c === 'r') { i++; return Math.sqrt(unary()); }
      if (c === '-') { i++; return -unary(); }
      if (c === '+') { i++; return unary(); }
      return num();
    }
    function implicitMul(v) {   // 2π, 2(3+1), 3√4
      while (peek() === '(' || peek() === 'p' || peek() === 'r') v = v * power();
      return v;
    }
    function power() { var b = implicitMul(atom()); if (peek() === '^') { i++; return Math.pow(b, unary()); } return b; }
    function unary() { return power(); }
    function mul() { var v = unary(); while (peek() === '*' || peek() === '/') { var o = s.charAt(i++); var r = unary(); v = o === '*' ? v * r : v / r; } return v; }
    function add() { var v = mul(); while (peek() === '+' || peek() === '-') { var o = s.charAt(i++); var r = mul(); v = o === '+' ? v + r : v - r; } return v; }
    var res = add();
    if (i < s.length) throw 'x';
    return res;
  }

  box.addEventListener('click', function (e) {
    var t = e.target;
    if (t.classList.contains('x')) { box.style.display = 'none'; return; }
    var k = t.getAttribute && t.getAttribute('data-k'); if (!k) return;
    if (k === 'C') { expr = ''; last = null; exEl.textContent = ''; }
    else if (k === '⌫') { expr = expr.replace(/×10\^$/, '').slice(0, expr.match(/×10\^$/) ? expr.length : -1); }
    else if (k === '=') {
      if (!expr) return;
      try { last = evaluate(expr); exEl.textContent = expr + ' ='; expr = ''; }
      catch (err) { exEl.textContent = 'Neteisinga išraiška'; }
    } else {
      var add = { 'x²': '^2', 'xʸ': '^', '√': '√', '×10ⁿ': '×10^' }[k] || k;
      // po rezultato tęsiam su juo, jei spaudžiamas veiksmas
      if (expr === '' && last !== null && /^[+−×÷^]/.test(add)) expr = fmt(last).replace(/ ×10\^/, '×10^');
      expr += add;
    }
    show();
  });
  btn.addEventListener('click', function () { box.style.display = box.style.display === 'block' ? 'none' : 'block'; });
  window.__etsCalcEval = evaluate;  // testams
})();
