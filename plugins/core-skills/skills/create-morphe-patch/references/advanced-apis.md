# Advanced APIs

A handful of helpers make patch development faster than raw smali mutation.

## `classDefBy(String)`

Look up an immutable class definition by its fully-qualified name.

```kotlin
execute {
    val superClassOfReturnType = classDefBy(match().originalMethod.returnType).superclass
}
```

Use this when you need to walk a class hierarchy without going through a fingerprint match.

## `mutableClassDefBy(ClassDef)`

Make a class definition mutable so you can add/remove methods or fields.

```kotlin
execute {
    val immutable = classDefBy("Lcom/some/app/Hook;")
    val mutable = mutableClassDefBy(immutable)
    mutable.methods.add(Method().apply {
        definingClass = "Lcom/some/app/Hook;"
        accessFlags = AccessFlags.PUBLIC or AccessFlags.STATIC
        name = "injectedMethod"
        returnType = "V"
    })
}
```

> The first call to `mutableClassDefBy` swaps the original class definition with the mutable copy in `context.classes`. Subsequent calls return the same mutable copy.

## `get(String, Boolean)` and `delete(String)`

Read, write, or delete resource files (any file inside the APK, not just `res/`).

```kotlin
execute {
    val file = get("res/values/strings.xml")
    val content = file.readText()
    file.writeText(content.replace("Hello", "Goodbye"))
}

execute {
    delete("res/values/strings.xml")
}
```

The second argument to `get` is `createIfMissing` — pass `true` if the patch should create the file if it doesn't exist.

## `document(String)` and `document(InputStream)`

Read and write XML files as DOM.

```kotlin
execute {
    document("AndroidManifest.xml").use { doc ->
        val element = doc.createElement("uses-permission").apply {
            setAttribute("android:name", "android.permission.INTERNET")
        }
        doc.documentElement.appendChild(element)
    }
}
```

Use the `InputStream` overload for resources embedded in the patch bundle:

```kotlin
execute {
    val inputStream = classLoader.getResourceAsStream("fragment.xml")
    document(inputStream).use { doc ->
        // ... modify ...
    }
}
```

The `.use { }` form ensures the document is closed and flushed.

## `originalMethod` vs `method`

When working with a fingerprint match:

- `originalMethod` — immutable view. Read-only access.
- `method` — mutable copy. First access creates the copy and replaces the original in `context.classes`.

```kotlin
execute {
    val match = myFingerprint
    // Reading only? Use originalMethod.
    val accessFlags = match.originalMethod.accessFlags
    // Modifying? Use method.
    match.method.addInstructions(0, "return-void")
}
```

## Common combinations

**Modify a method's parameters:**

```kotlin
execute {
    match.method.parameters = listOf("Ljava/lang/String;")
}
```

**Replace a method entirely:**

```kotlin
execute {
    match.method.replaceInstructions(
        """
            const-string v0, "replaced"
            return-void
        """,
    )
}
```

**Add a new field to a class:**

```kotlin
execute {
    val mutable = mutableClassDefBy(match.originalClassDef)
    mutable.fields.add(Field().apply {
        definingClass = mutable.type
        accessFlags = AccessFlags.PUBLIC or AccessFlags.STATIC
        name = "addedField"
        type = "I"
        // initialValue = 0  // omit; default-initialized
    })
}
```

## Threading and idempotency

Patches run on the JVM thread Morphe Patcher assigns. They are run sequentially in dependency order. Avoid global state, but if you must share between a dependency and the dependent patch, use a `Supplier<InputStream>` provider exposed through `extendWithAll` rather than mutable globals.

## Error handling

Throw `PatchException` to abort the apply with a clear message:

```kotlin
execute {
    val match = myFingerprint.matchOrNull
        ?: throw PatchException("Could not find ShowAds in ${PACKAGE_NAME}")
}
```

The exception propagates, terminating the patch and rolling back any partial changes if the patcher supports it.
