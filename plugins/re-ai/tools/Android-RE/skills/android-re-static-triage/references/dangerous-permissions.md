# Dangerous Permissions Quick Reference

The full list of Android "dangerous" runtime permissions (API 34). The
static triage skill flags these in the report.

## Calendar
- `android.permission.READ_CALENDAR`
- `android.permission.WRITE_CALENDAR`

## Call log
- `android.permission.READ_CALL_LOG`
- `android.permission.WRITE_CALL_LOG`
- `android.permission.PROCESS_OUTGOING_CALLS`

## Camera
- `android.permission.CAMERA`

## Contacts
- `android.permission.READ_CONTACTS`
- `android.permission.WRITE_CONTACTS`
- `android.permission.GET_ACCOUNTS`

## Location
- `android.permission.ACCESS_FINE_LOCATION`
- `android.permission.ACCESS_COARSE_LOCATION`
- `android.permission.ACCESS_BACKGROUND_LOCATION`

## Microphone
- `android.permission.RECORD_AUDIO`

## Phone
- `android.permission.READ_PHONE_STATE`
- `android.permission.READ_PHONE_NUMBERS`
- `android.permission.CALL_PHONE`
- `android.permission.ANSWER_PHONE_CALLS`
- `android.permission.ADD_VOICEMAIL`
- `android.permission.USE_SIP`
- `android.permission.ACCEPT_HANDOVER`

## Sensors
- `android.permission.BODY_SENSORS`
- `android.permission.ACTIVITY_RECOGNITION`

## SMS
- `android.permission.SEND_SMS`
- `android.permission.RECEIVE_SMS`
- `android.permission.READ_SMS`
- `android.permission.RECEIVE_WAP_PUSH`
- `android.permission.RECEIVE_MMS`
- `android.permission.READ_CELL_BROADCASTS`

## Storage
- `android.permission.READ_EXTERNAL_STORAGE`
- `android.permission.WRITE_EXTERNAL_STORAGE`
- `android.permission.MANAGE_EXTERNAL_STORAGE`
- `android.permission.READ_MEDIA_IMAGES`
- `android.permission.READ_MEDIA_VIDEO`
- `android.permission.READ_MEDIA_AUDIO`

## Nearby devices
- `android.permission.BLUETOOTH_CONNECT`
- `android.permission.BLUETOOTH_SCAN`
- `android.permission.BLUETOOTH_ADVERTISE`
- `android.permission.NEARBY_WIFI_DEVICES`

## Notifications
- `android.permission.POST_NOTIFICATIONS`

## Triage heuristics

A triage report should call out:

- **Camera + Microphone + Location together** — likely a recording /
  tracking app; verify usage.
- **READ_CONTACTS + READ_SMS** — exfiltration risk; verify usage.
- **SYSTEM_ALERT_WINDOW + accessibility services** (latter is not a
  dangerous permission but a special service) — overlay-attack vectors.
- **BIND_ACCESSIBILITY_SERVICE** — extremely high-risk; almost never
  legitimate outside of password managers and automation apps.
- **QUERY_ALL_PACKAGES** — broad app enumeration; required for some
  launchers, suspicious elsewhere.
