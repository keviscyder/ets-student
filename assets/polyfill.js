/* ETS: senoms planšetėms (Android System WebView < 93) trūkstamos JS funkcijos. */
(function () {
  function def(obj, name, fn) {
    if (!obj[name]) { try { Object.defineProperty(obj, name, { value: fn, writable: true, configurable: true }); } catch (e) { obj[name] = fn; } }
  }
  def(String.prototype, 'replaceAll', function (search, repl) {
    if (search instanceof RegExp) {
      if (!search.global) throw new TypeError('replaceAll must be called with a global RegExp');
      return this.replace(search, repl);
    }
    var esc = String(search).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return this.replace(new RegExp(esc, 'g'), repl);
  });
  def(Object, 'hasOwn', function (o, k) { return Object.prototype.hasOwnProperty.call(o, k); });
  var at = function (i) { i = Math.trunc(i) || 0; if (i < 0) i += this.length; return (i < 0 || i >= this.length) ? undefined : this[i]; };
  def(Array.prototype, 'at', at);
  def(String.prototype, 'at', at);
  def(Array.prototype, 'findLast', function (f, t) { for (var i = this.length - 1; i >= 0; i--) if (f.call(t, this[i], i, this)) return this[i]; return undefined; });
  def(Array.prototype, 'findLastIndex', function (f, t) { for (var i = this.length - 1; i >= 0; i--) if (f.call(t, this[i], i, this)) return i; return -1; });
  // Dar senesnėms planšetėms (WebView 58–84)
  if (typeof globalThis === 'undefined') { try { window.globalThis = window; } catch (e) {} }
  def(Object, 'fromEntries', function (it) { var o = {}; Array.from(it).forEach(function (p) { o[p[0]] = p[1]; }); return o; });
  def(Array.prototype, 'flat', function (d) {
    d = d === undefined ? 1 : Math.floor(d);
    return d < 1 ? Array.prototype.slice.call(this) : Array.prototype.reduce.call(this, function (acc, v) {
      return acc.concat(Array.isArray(v) ? v.flat(d - 1) : v); }, []);
  });
  def(Array.prototype, 'flatMap', function (f, t) { return Array.prototype.map.call(this, f, t).flat(1); });
  def(String.prototype, 'trimStart', function () { return this.replace(/^\s+/, ''); });
  def(String.prototype, 'trimEnd', function () { return this.replace(/\s+$/, ''); });
  def(String.prototype, 'matchAll', function (re) {
    var r = new RegExp(re, (re.flags || '').indexOf('g') < 0 ? (re.flags || '') + 'g' : re.flags), s = String(this), out = [], m;
    while ((m = r.exec(s)) !== null) { out.push(m); if (m[0] === '') r.lastIndex++; }
    return out[Symbol.iterator]();
  });
  def(window, 'queueMicrotask', function (f) { Promise.resolve().then(f); });
  if (typeof Promise !== 'undefined') {
    def(Promise.prototype, 'finally', function (f) {
      var C = this.constructor;
      return this.then(function (v) { return C.resolve(f()).then(function () { return v; }); },
                       function (e) { return C.resolve(f()).then(function () { throw e; }); });
    });
    def(Promise, 'allSettled', function (ps) {
      return Promise.all(Array.from(ps).map(function (p) {
        return Promise.resolve(p).then(function (v) { return { status: 'fulfilled', value: v }; },
                                       function (e) { return { status: 'rejected', reason: e }; }); }));
    });
  }
  if (typeof Promise !== 'undefined') def(Promise, 'any', function (ps) {
    return new Promise(function (res, rej) { var n = 0, errs = [], arr = Array.from(ps); if (!arr.length) rej(new Error('All promises were rejected'));
      arr.forEach(function (p, i) { Promise.resolve(p).then(res, function (e) { errs[i] = e; if (++n === arr.length) rej(new Error('All promises were rejected')); }); }); });
  });
})();
