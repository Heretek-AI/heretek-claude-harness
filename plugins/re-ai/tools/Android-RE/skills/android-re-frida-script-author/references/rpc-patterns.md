# RPC patterns for Frida scripts

`rpc.exports` is the cleanest way to retrieve state from a Frida
agent. The MCP server's `frida_rpc_call` tool invokes these
methods with positional arguments and a timeout.

## Ping pattern (health-check)

```js
rpc.exports = {
  ping: function () { return 'pong'; }
};
```

Call it from the MCP client:

```
frida_rpc_call(script_id, "ping")
```

If you get back `{"error": "script_not_found"}` or
`{"error": "rpc_failed"}`, the script didn't load or crashed.

## Return JSON state

```js
var state = { call_count: 0, last_args: null };

Java.perform(function () {
  var Cls = Java.use('com.example.Foo');
  Cls.bar.implementation = function () {
    state.call_count += 1;
    state.last_args = Array.prototype.slice.call(arguments).map(String);
    return this.bar.apply(this, arguments);
  };
});

rpc.exports = {
  getState: function () { return JSON.stringify(state); }
};
```

Call:

```
frida_rpc_call(script_id, "getState")
```

Returns a JSON string the MCP client can `json.loads` on.

## Reset

```js
rpc.exports = {
  reset: function () {
    state.call_count = 0;
    state.last_args = null;
    return 'ok';
  }
};
```

Useful for repeated experiments.

## Bounded buffer

```js
var MAX = 100;
var buf = [];

rpc.exports = {
  push: function (entry) {
    if (buf.length >= MAX) buf.shift();
    buf.push(entry);
  },
  drain: function () {
    var out = buf.slice();
    buf.length = 0;
    return JSON.stringify(out);
  }
};
```

This pattern: the agent pushes events into a bounded buffer; the
client drains it. Avoids growing the agent's heap unboundedly.

## Exceptions

`rpc.exports` methods can throw; the MCP server catches the
exception and returns `{"error": "rpc_failed", "message": ...}`.

```js
rpc.exports = {
  compute: function (n) {
    if (n < 0) {
      throw new Error('n must be non-negative');
    }
    return n * 2;
  }
};
```

## Timeouts

`frida_rpc_call` accepts a `timeout_s` argument (default 30s).
If the agent takes longer, the call is cancelled with
`OperationCancelledError`. Design the agent to either return
quickly or to be cancellable.

```js
var cancelled = false;
rpc.exports = {
  longOp: function () {
    Java.perform(function () {
      for (var i = 0; i < 1_000_000; i++) {
        if (cancelled) return null;
        // do work
      }
    });
  },
  cancel: function () { cancelled = true; return 'ok'; }
};
```

## Schema export

```js
rpc.exports = {
  schema: function () {
    return JSON.stringify({
      getState: '() => string',
      reset: '() => "ok"',
      compute: '(n: int) => int'
    });
  }
};
```

Useful for the client to introspect what's available without
reading the source.
