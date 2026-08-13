---
name: re-api-reverse
description: Reverse engineer a REST API from captured HTTP traffic. Use when the user says "reconstruct the API", "what endpoints does this app call", "generate OpenAPI from this capture", "document this API". Starts a live mitmproxy capture, parses flow files, derives an OpenAPI/Swagger spec, extracts secrets.
---

# REST API Reverse Engineering

## When to use

Use this skill when you have HTTP traffic (live capture, HAR file, or mitmproxy flow file) and you want to derive an OpenAPI/Swagger specification for the API.

Common prompts:

- "Reverse the API at api.example.com"
- "Document this API from a HAR file"
- "I have a mitmproxy flow file — turn it into OpenAPI"
- "What endpoints does this mobile app call?"

## Workflow (two tracks)

### Track A — Live capture

1. Confirm the user has set `https_proxy=http://localhost:8080` (or wants you to start a transparent capture).
2. `re-mitm2swagger.start_capture(port=8080, output_path="/tmp/capture.flow", mode="regular")`.
3. Tell the user to perform the actions they want captured. Wait for them to confirm.
4. `re-mitm2swagger.stop_capture(pid=<pid from start>)`.
5. Run Track B on the resulting flow file.

### Track B — Existing capture (HAR or mitmproxy flow)

1. Detect the format:
   - If the file is JSON and starts with `{"log": "..."`, it's a HAR file.
   - If it's a mitmproxy flow, use `parse_flows`.
2. `re-mitm2swagger.parse_flows(path)` to get a summary list.
3. `re-mitm2swagger.filter_flows(...)` to apply user-supplied filters.
4. `re-mitm2swagger.har_to_swagger(path, output_path="/tmp/openapi.json")` (HAR) OR `re-mitm2swagger.flow_to_swagger(path, output_path="/tmp/openapi.json")` (mitmproxy).
5. `re-mitm2swagger.extract_secrets(path)` for token/JWT/API-key detection.
6. **Cleanup pass** (you do this, not the tool):
   - Dedupe paths (e.g. `/users/123` and `/users/456` → `/users/{id}`)
   - Detect auth scheme (Authorization: Bearer, cookies, custom headers)
   - Identify the base URL (host) — strip it from the path
   - Note: this is where the LLM shines — tools produce raw output, you produce the cleaned spec.

## Cleanup recipe (the LLM does this)

1. Group flows by `(method, host, path_template)`. The path template is what `har_to_swagger` does automatically (digits → `{id}`, UUIDs → `{uuid}`).
2. Detect auth:
   - Look for `Authorization: Bearer` headers → OAuth 2.0 / JWT
   - Look for `Cookie:` headers → session cookies
   - Look for `X-API-Key` or `api_key` query params → API key auth
3. For each path, synthesize:
   - Parameters (path, query, header)
   - Request body schema (from observed Content-Type and body)
   - Response schema (from observed responses — but mark these as "observed" not "complete")
4. Add tags from URL prefixes (`/api/v1/users` → tag "users", `/api/v1/orders` → tag "orders")
5. Add server URL from the most common host

## Path templating rules

Apply these in order:

1. `/<digits>` → `/{id}`
2. `/<uuid>` (8-4-4-4-12 hex pattern) → `/{uuid}`
3. `/<base64-looking-32+-chars>` → `/{token}`
4. `/<sha1/256 hex>` → `/{hash}`
5. `/<email-like>` → `/{email}`

If two templated paths collide (e.g. `/users/{id}` and `/users/me` should be the same), prefer the more specific path (`/users/me`) and keep both.

## What to extract

- **Endpoints**: every distinct `(method, path)` pair
- **Auth scheme**: the dominant auth header
- **Tags**: usually derived from path prefixes
- **Schemas**: request and response bodies (best-effort)
- **Servers**: the most common host
- **Examples**: at least one example request per endpoint

## Limitations

- Captured traffic may miss error paths (4xx, 5xx) if the app rarely errors. Note this in the report.
- Query parameters with binary or non-ASCII values may be URL-encoded strangely. The LLM should normalize.
- GraphQL/gRPC traffic will look like a single endpoint. Use `re-rizin` on the mobile app binary instead.

## Output

Produce a final OpenAPI 3.0 spec at `openapi.json` plus a Markdown report that:

1. Lists every endpoint discovered (with auth-required flag)
2. Highlights any unusual headers, cookies, or auth schemes
3. Notes any IOCs (hardcoded API keys in headers, JWTs in query strings, etc.)
4. Suggests next steps (auth flow analysis, parameter fuzzing, etc.)
