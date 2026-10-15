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
  if (typeof Promise !== 'undefined') def(Promise, 'any', function (ps) {
    return new Promise(function (res, rej) { var n = 0, errs = [], arr = Array.from(ps); if (!arr.length) rej(new Error('All promises were rejected'));
      arr.forEach(function (p, i) { Promise.resolve(p).then(res, function (e) { errs[i] = e; if (++n === arr.length) rej(new Error('All promises were rejected')); }); }); });
  });
})();
