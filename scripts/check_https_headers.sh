#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <domain>"
  echo "Example: $0 pplinsighthub.com"
  exit 2
fi

domain="${1#http://}"
domain="${domain#https://}"
domain="${domain%%/*}"

http_url="http://${domain}"
https_url="https://${domain}"

failures=0

check_ok() {
  echo "PASS: $1"
}

check_fail() {
  echo "FAIL: $1"
  failures=$((failures + 1))
}

http_status="$(curl -sS -o /dev/null -w "%{http_code}" "${http_url}/")"
http_headers="$(curl -sSI "${http_url}/")"
location_header="$(echo "$http_headers" | awk -F': ' 'tolower($1)=="location"{print $2}' | tr -d '\r' | head -n 1)"

if [[ "$http_status" == "301" || "$http_status" == "308" ]]; then
  check_ok "HTTP root returns redirect status (${http_status})"
else
  check_fail "HTTP root expected 301/308 but got ${http_status}"
fi

if [[ "$location_header" == https://* ]]; then
  check_ok "HTTP redirect target is HTTPS (${location_header})"
else
  check_fail "HTTP redirect target is not HTTPS (${location_header:-missing})"
fi

https_headers="$(curl -sSI "${https_url}/")"
health_status="$(curl -sS -o /dev/null -w "%{http_code}" "${https_url}/health")"

hsts_header="$(echo "$https_headers" | awk -F': ' 'tolower($1)=="strict-transport-security"{print $2}' | tr -d '\r' | head -n 1)"
xcto_header="$(echo "$https_headers" | awk -F': ' 'tolower($1)=="x-content-type-options"{print $2}' | tr -d '\r' | head -n 1)"
frame_header="$(echo "$https_headers" | awk -F': ' 'tolower($1)=="x-frame-options"{print $2}' | tr -d '\r' | head -n 1)"
referrer_header="$(echo "$https_headers" | awk -F': ' 'tolower($1)=="referrer-policy"{print $2}' | tr -d '\r' | head -n 1)"

if [[ "$hsts_header" == *"max-age=31536000"* && "$hsts_header" == *"includeSubDomains"* ]]; then
  check_ok "Strict-Transport-Security contains max-age and includeSubDomains"
else
  check_fail "Strict-Transport-Security missing expected directives (${hsts_header:-missing})"
fi

if [[ "$hsts_header" == *"preload"* ]]; then
  check_fail "Strict-Transport-Security includes preload, but current decision is to defer preload"
else
  check_ok "Strict-Transport-Security does not include preload (decision: defer)"
fi

if [[ "${xcto_header,,}" == "nosniff" ]]; then
  check_ok "X-Content-Type-Options is nosniff"
else
  check_fail "X-Content-Type-Options expected nosniff (${xcto_header:-missing})"
fi

if [[ "$frame_header" == "DENY" ]]; then
  check_ok "X-Frame-Options is DENY"
else
  check_fail "X-Frame-Options expected DENY (${frame_header:-missing})"
fi

if [[ "$referrer_header" == "strict-origin-when-cross-origin" ]]; then
  check_ok "Referrer-Policy is strict-origin-when-cross-origin"
else
  check_fail "Referrer-Policy expected strict-origin-when-cross-origin (${referrer_header:-missing})"
fi

if [[ "$health_status" == "200" ]]; then
  check_ok "HTTPS /health returns 200"
else
  check_fail "HTTPS /health expected 200 but got ${health_status}"
fi

if [[ "$failures" -gt 0 ]]; then
  echo ""
  echo "HTTPS/header verification failed with ${failures} issue(s)."
  exit 1
fi

echo ""
echo "HTTPS/header verification passed."
