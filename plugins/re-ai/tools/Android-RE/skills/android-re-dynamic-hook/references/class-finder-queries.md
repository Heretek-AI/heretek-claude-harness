# Class-finder queries for Android RE

Quick recipes for finding the right class/method to hook.

## Find a class by name

```js
Java.enumerateLoadedClasses({
  onMatch: function (c) {
    if (c.indexOf('com.example.payment') >= 0) console.log(c);
  },
  onComplete: function () {}
});
```

## Find all classes implementing an interface

```js
Java.perform(function () {
  Java.enumerateLoadedClasses({
    onMatch: function (c) {
      try {
        var k = Java.use(c);
        if (Java.cast(k, Java.use('com.example.IListener'))) {
          console.log(c);
        }
      } catch (e) {}
    },
    onComplete: function () {}
  });
});
```

## Find a class by package

```js
Java.enumerateLoadedClassesSync()
  .filter(function (c) { return c.startsWith('com.example.'); })
  .forEach(function (c) { console.log(c); });
```

## Find methods of a class

```js
var Cls = Java.use('com.example.Foo');
console.log(Cls.class.getDeclaredMethods().map(function (m) {
  return m.toString();
}));
```

## Find callers of a method

```js
// Static call-graph extraction via smali trace. See
// android-re-static-triage → decompile for the smali of the
// caller, then grep for the target's FQCN.
```

## Find strings near a class

Often the class declaration is preceded by a class-level JavaDoc
comment that gives a hint. Use jadx (`decompile_class`) to read
the class.

## Find resources

```js
var ctx = Java.use('android.app.ActivityThread')
  .currentApplication();
var res = ctx.getResources();
res.getString(0x7f0a0001);  // any R.string.* id
```

## Find intent extras

```js
var Intent = Java.use('android.content.Intent');
var act = Java.use('android.app.ActivityThread')
  .currentActivity();
var intent = act.getIntent();
intent.getExtras().keySet().toArray().forEach(function (k) {
  console.log(k, '=', intent.getExtras().get(k));
});
```

## List loaded native modules

```js
Process.enumerateModules().forEach(function (m) {
  console.log(m.name, m.base, m.size);
});
```

## List exports of a native module

```js
var mod = Process.findModuleByName('libfoo.so');
mod.enumerateExports().forEach(function (e) {
  console.log(e.name, e.address);
});
```

## Trace every JNI call from a specific class

Hook the `JNINativeInterface` function table to log every native
call. Heavy but comprehensive.

```js
var art = Process.findModuleByName('libart.so');
var jni = Module.findExportByName('libart.so', 'JNINativeInterface');
Interceptor.attach(jni, { /* ... */ });
```
