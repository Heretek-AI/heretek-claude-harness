# apkleaks rules (reference)

apkleaks (https://github.com/dwisiswant0/apkleaks) ships with a
large rule set that complements the regex engine in
`android_re_core.secrets.rules`. This document describes the
relevant rules and when to use them.

## Built-in regex rules (selection)

apkleaks bundles regex rules for the following categories. Numbers
in parentheses are roughly the count of distinct rules per
category.

- **Payment gateways** (20+): a payment-processor, a peer-to-peer payment app, a merchant-account gateway, a card-acceptance gateway — see apkleaks upstream for the canonical list,
  Alipay, WeChat Pay, Adyen, Razorpay, Paytm.
- **Cloud providers** (15+): AWS access keys + secret keys, GCP,
  Azure, DigitalOcean, Heroku, Cloudflare.
- **Source control** (5+): GitHub PAT, GitLab PAT, Bitbucket.
- **Messaging** (5+): Slack, Twilio, SendGrid, Mailgun, Mailchimp.
- **Social auth** (5+): Facebook, Google, Twitter, LinkedIn.
- **Analytics** (5+): Mixpanel, Amplitude, Segment, Bugsnag.
- **Mobile-specific** (10+): Firebase URLs, OneSignal, AppCenter,
  Branch.io, Adjust.
- **Custom endpoints** (5+): URLs in `https?://` form, AWS
  S3 / CloudFront URLs, Azure Blob URLs.

## When to use apkleaks vs. the regex engine

- **Use the regex engine** (``scan_secrets``) when:
  - You want a fast, dependency-free pass.
  - The APK is small (< 50 MB).
  - You have specific rules in mind.
- **Use apkleaks** (``run_apkleaks`` via subprocess) when:
  - The APK is large or has many third-party SDKs.
  - You want a wider net of payment / mobile-specific rules.
  - You can install the tool (``pipx install apkleaks``).

## When to use quark / androwarn

- **quark** (https://quark-engine.net) is a behavior-focused static
  analyzer. It looks for combinations of Android API calls that
  indicate risky behavior (e.g. crypto misuse, insecure file
  storage). Use it for behavioral risk, not for secret strings.
- **androwarn** (https://github.com/maaaaz/AndroWarn) is a
  vulnerability scanner that flags potentially dangerous API
  usage. Use it for "is this app doing something sketchy" rather
  than "where is the secret".

## Composing a secrets scan

For a comprehensive secrets scan, run all three:

1. `scan_secrets` (regex engine, fast, covers most cases).
2. `run_apkleaks` (broader rule set, slower).
3. `scan_with_quark` (behavioral correlation).

Correlate the results by line number / FQCN to remove duplicates.

## False-positive handling

apkleaks generates many false positives. The best mitigations:

- **Verify usage**: only flag secrets that are *used* in code, not
  just present as constants.
- **Check encoding**: base64-encoded secrets may be missed.
- **Look for entropy**: a high-entropy string in code that is
  *also* a constant string literal is a stronger signal than a
  regex match alone.
