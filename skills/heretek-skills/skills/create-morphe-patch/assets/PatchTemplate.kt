/*
 * Patch template — copy this file to patches/src/main/kotlin/<bundle>/patches/<feature>/<Name>Patch.kt
 * and fill in the TODOs.
 *
 * Run `bash scripts/validate-patch.sh "<Name>"` after building to confirm the patch
 * is registered in patches-list.json.
 */

package app.morphe.patches.<feature>  // TODO: replace with your bundle namespace + feature folder

import app.morphe.patcher.Fingerprint
import app.morphe.patcher.bytecodePatch
import app.morphe.patcher.patch.Compatibility
import app.morphe.patcher.patch.AppTarget
import app.morphe.patcher.patch.PatchException
import app.morphe.patcher.Opcode
import app.morphe.patcher.opcode
import app.morphe.patcher.string
import app.morphe.patcher.fieldAccess
import app.morphe.patcher.methodCall

// TODO: replace with the actual Play-delegated signer SHA-256.
// Run: bash scripts/compute-signature.sh path/to/base.apk
private const val SIGNATURE = "<DELEGATED_SIGNER_SHA256>"

// TODO: replace with the Android package name + version you are targeting.
private const val PACKAGE_NAME = "<app.package.name>"
private const val VERSION = "<X.Y.Z>"

private val COMPATIBILITY = Compatibility(
    packageName = PACKAGE_NAME,
    name = "<App Name>",            // TODO: visible app name
    apkFileType = ApkFileType.APK_REQUIRED,
    appIconColor = 0x000000,         // TODO: 0xRRGGBB
    signatures = setOf(SIGNATURE),
    targets = listOf(AppTarget(version = VERSION)),
)

// TODO: replace with a fingerprint that uniquely identifies the method to patch.
// See references/fingerprinting.md for the full DSL.
private object TargetFingerprint : Fingerprint(
    definingClass = "L<package>/<class>;",  // Use obfuscated-safe strings (see docs).
    returnType = "V",
    parameters = listOf("Ljava/lang/String;"),
    filters = listOf(
        string("<unique-literal>"),
        // Add more filters if needed: fieldAccess, methodCall, opcode, literal.
    ),
)

@Suppress("unused")
val <name>Patch = bytecodePatch(
    name = "<Short verb-led name>",         // TODO: e.g., "Disable ads"
    description = "<Third-person description, ending with a period.>",  // TODO
    default = true,                          // Default on/off in the Manager UI.
) {
    compatibleWith(COMPATIBILITY)

    // Optional: dependsOn(otherPatch)
    // Optional: extendWith("extension.mpe")

    execute {
        TargetFingerprint.let { match ->
            // TODO: replace with the smali instructions you want to inject.
            match.method.addInstructions(
                0,
                """
                    const/4 v0, 0x0
                    return v0
                """,
            )
        }
    }
}
