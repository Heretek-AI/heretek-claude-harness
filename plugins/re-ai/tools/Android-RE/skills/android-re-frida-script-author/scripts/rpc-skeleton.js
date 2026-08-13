// rpc-skeleton.js — a minimal agent template with rpc.exports + console
// log buffer. Drop your hook code into the marked section, then
// load with frida_load_script.

console.log('[agent] starting');

// ---- BEGIN HOOK SECTION ----
// Java.perform(function () {
//   var Cls = Java.use('com.example.Foo');
//   Cls.bar.overloads.forEach(function (m) {
//     m.implementation = function () {
//       console.log('[*] bar called with', arguments);
//       return this[Cls.bar.name].apply(this, arguments);
//     };
//   });
// });
// ---- END HOOK SECTION ----

// ---- rpc.exports ----
var _log = [];
var MAX = 200;

function _append(line) {
  if (_log.length >= MAX) _log.shift();
  _log.push({ ts: Date.now(), line: line });
}

rpc.exports = {
  ping: function () { return 'pong'; },
  getLog: function () { return JSON.stringify(_log); },
  clearLog: function () { _log = []; return 'ok'; },
  schema: function () {
    return JSON.stringify({
      ping: '() => "pong"',
      getLog: '() => JSON of [{ts, line}, ...]',
      clearLog: '() => "ok"'
    });
  }
};

console.log('[agent] ready');
