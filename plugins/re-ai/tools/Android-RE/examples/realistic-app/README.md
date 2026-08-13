# Realistic app triage — example

An example of running the full Android-RE triage on a real
Android app. This directory does not ship the target APK
(none is bundled in the repo for licensing reasons); it
contains the **expected output structure** and a runbook.

## Expected output

After running the full triage orchestrator on a realistic
chat app, the `./.triage/` directory should look like:

```
.triage/
├── triage-abc123.md            # Final MASVS report
├── triage-abc123.sarif         # SARIF document
├── triage-abc123.json          # Raw findings
├── network-abc123/             # Network capture artifacts
│   ├── screenshot-001.png
│   ├── screenshot-002.png
│   ├── proxy-log.txt
│   └── findings.json
├── dynamic-abc123/             # Dynamic session reports
│   ├── session-001.json
│   └── session-002.json
└── native-abc123/              # Native binary reports
    └── libfoo.json
```

## Runbook

```text
# 1. Open the static project
> /android-re-static-triage
> Triage /path/to/app.apk

# 2. Run the full orchestrator
> /android-re-triage-orchestrator
> Run a MASVS audit of /path/to/app.apk.

# 3. Add native audit
> /android-re-native-triage
> Audit the .so files in /path/to/app.apk.

# 4. Add dynamic (if a device is available)
> /android-re-dynamic-hook
> Hook the auth flow on the running app.

# 5. Network capture (if a proxy is available)
> /android-re-network-intercept
> Capture traffic through mitmproxy at 10.0.2.2:8080.

# 6. Finalize
> /android-re-masvs-report
> Produce the full MASVS report.
```

The final report includes:
- Package metadata
- Component inventory
- Permission usage
- Exported-component analysis
- Native-library hardening
- Cross-source correlations
- MASVS coverage table
- Prioritized findings list
