# Telemetry leaks — Sentry SDK + cross-publisher view

**Pattern:** Pattern D in `ANTI-TAMPER-TAXONOMY.md`

## Headline

A representative IL2CPP target analysis found Sentry SDK crash-reporting resource files in the Unity `Resources/` subdir:

- `Sentry.System.Buffers.dll-resources.dat`
- `Sentry.System.Collections.Immutable.dll-resources.dat`
- `Sentry.System.Memory.dll-resources.dat`
- `Sentry.System.Numerics.Vectors.dll-resources.dat`
- `Sentry.System.Reflection.Metadata.dll-resources.dat`
- `Sentry.System.Text.Encodings.Web.dll-resources.dat`
- `Sentry.System.Text.Json.dll-resources.dat`

The Sentry SDK is a known telemetry surface — it phones home to Sentry's hosted SaaS when crashes occur. The SDK can include the Sentry DSN URL (a public-but-leaky identifier) and the SDK's HTTP traffic is unencrypted telemetry.

## Detection

- `re-lief.categorize_strings` populates the `network` bucket with Sentry hostnames + DSN patterns
- `re-leak-scan.find_secrets` scans for Sentry DSN URLs (the v2.9.0 NEEDLES expansion)
- `re-pcap.correlate_endpoints` correlates the binary's network calls with the Sentry SaaS endpoint

## Empirical cases

- Representative IL2CPP target — Sentry SDK in `Resources/`
  - See `publishers/sunblink/hello-kitty-island-adventure/`

## Cross-references

- RE-AI `ANTI-TAMPER-TAXONOMY.md` Pattern D
- RE-AI `tests/test_no_vendor_leakage.py` (Sentry DSN needles)
- RE-AI `servers/re-leak-scan/` (the secret-detection tool)
- RE-UNLEASHED `publishers/sunblink/hello-kitty-island-adventure/`
