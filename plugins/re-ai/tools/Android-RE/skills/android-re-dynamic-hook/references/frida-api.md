# Frida API quick reference

A condensed cheat-sheet of the Frida JavaScript API for use in
`android-re-dynamic-hook` and `android-re-frida-script-author`
skills.

## Java bridge

```js
Java.perform(function () {
  var Cls = Java.use('com.example.Foo');
  var inst = Cls.$new();                      // construct
  var m = Cls.bar.overload('int', 'java.lang.String');  // overload by descriptor
  m.implementation = function (a, b) {        // replace
    console.log('a =', a, 'b =', b);
    return this.bar(a, b);                     // call original
  };
});
```

## Common patterns

### Iterate all overloads

```js
Cls.bar.overloads.forEach(function (m) {
  m.implementation = function () {
    console.log('overload:', m.argumentTypes);
    return this[Cls.bar.name].apply(this, arguments);
  };
});
```

### Hook a class method (static)

```js
Cls.staticMethod.implementation = function () {
  return this.staticMethod.apply(this, arguments);
};
```

### Hook a constructor

```js
Cls.$init.implementation = function () {
  console.log('constructing with', arguments);
  return this.$init.apply(this, arguments);
};
```

### Enumerate loaded classes

```js
Java.enumerateLoadedClasses({
  onMatch: function (c) { /* c is the class name */ },
  onComplete: function () { /* done */ }
});
```

### Use the backtracer

```js
m.implementation = function () {
  console.log(
    'backtrace:\n' +
    Java.use('android.util.Log')
      .getStackTraceString(
        Java.use('java.lang.Exception').$new()
      )
  );
  return this[Cls.bar.name].apply(this, arguments);
};
```

## Native (Module) bridge

```js
var mod = Process.findModuleByName('libfoo.so');
var sym = mod.findExportByName('Java_com_example_Foo_bar');
Interceptor.attach(sym, {
  onEnter: function (args) {
    this.arg0 = args[0];  // save for onLeave
  },
  onLeave: function (retval) {
    console.log('ret:', retval);
  }
});
```

## Memory

```js
var buf = Memory.alloc(16);
Memory.writeUtf8String(buf, 'hello');
console.log(Memory.readUtf8String(buf));
```

## RPC exports

```js
rpc.exports = {
  ping: function () { return 'pong'; },
  getState: function () { return JSON.stringify(state); }
};
```

Called from the MCP server with `frida_rpc_call(script_id, 'ping')`.

## Error handling

```js
try {
  Java.perform(function () {
    // ...
  });
} catch (e) {
  console.error('hook failed:', e);
}
```

## Stalker (code tracing)

```js
var mod = Process.findModuleByName('libfoo.so');
var base = mod.base;
var size = mod.size;

Interceptor.attach(Module.findExportByName('libc.so', 'open'), {
  onEnter: function (args) {
    Stalker.follow(this.threadId, {
      events: { call: true, ret: false },
      onCallSummary: function (s) { console.log(s); }
    });
  },
  onLeave: function (retval) {
    Stalker.unfollow();
    Stalker.flush();
  }
});
```

(Stalker is heavy; use with care on a real device.)
