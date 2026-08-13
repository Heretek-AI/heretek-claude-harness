package <your.bundle.namespace>.extension.<name>;

/**
 * Stub class — replace with the Java/Kotlin class(es) your patch needs to call.
 *
 * From a patch, reference public static methods:
 *   invoke-static {}, L<your/bundle/namespace>/extension/<name>/Stub;->doSomething()V
 *
 * After building, place the produced .mpe artifact in your bundle's patches
 * resources and reference it via extendWith("<name>.mpe").
 */
public final class Stub {
    private Stub() {}

    public static void doSomething() {
        // Implementation goes here.
    }
}
