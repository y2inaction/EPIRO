#!/usr/bin/env bash
#
# Drive the whole chain the specification draws, through the API, as the
# people who would really do each step:
#
#   Evidence → Signal → Assessment → Finding → Action / owner → Status
#
# Nothing here is a fixture. Every step is a real request, so the audit trail
# and the change feed show what actually happened — including the refusal
# when the owner of an action tries to close it themselves.
#
#   python scripts/demo_seed.py > demo_ids.txt   # reference data
#   IDS=demo_ids.txt bash scripts/demo.sh        # the chain
#
# Sign-in is rate limited to five a minute. That is the limiter working, not
# a problem to route around, so the sixth login waits its turn.
set -euo pipefail
source "${IDS:-./demo_ids.txt}"
API=http://localhost:8000/api/v1

tok() { curl -s -X POST $API/auth/login -H 'Content-Type: application/json' \
  -d "{\"email\":\"$1@example.com\",\"password\":\"final-test-password\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])"; }

# Sign-in is rate limited to five a minute, which is the limiter doing its
# job rather than a problem to route around, so the sixth waits its turn.
RESEARCHER=$(tok researcher); VERIFIER=$(tok verifier); APPROVER=$(tok approver)
EDITOR=$(tok editor); EXEC=$(tok executive)
sleep 62
ANALYST=$(tok analyst)

# Quiet on empty input: when req has already failed and printed why, a
# JSON traceback on top of it buries the message that matters.
jid() { python3 -c "
import sys, json
raw = sys.stdin.read().strip()
if raw:
    print(json.loads(raw)['id'])
"; }

# Every call is checked. An earlier version of this script sent each request
# with -o /dev/null and no status check; curl exits 0 on an HTTP error unless
# told otherwise, so `set -e` never fired and four failed requests were
# reported as a working chain. A demo that cannot fail proves nothing.
req() {
  local method=$1 path=$2 token=$3 body=${4:-}
  local out code
  if [ -n "$body" ]; then
    out=$(curl -s -w '\n%{http_code}' -X "$method" "$API$path" \
      -H "Authorization: Bearer $token" -H 'Content-Type: application/json' -d "$body")
  else
    out=$(curl -s -w '\n%{http_code}' -X "$method" "$API$path" -H "Authorization: Bearer $token")
  fi
  code=${out##*$'\n'}
  body=${out%$'\n'*}
  if [ "$code" -lt 200 ] || [ "$code" -ge 300 ]; then
    echo "FAILED $method $path -> $code" >&2
    echo "$body" >&2
    exit 1
  fi
  printf '%s' "$body"
}

# The status a call is expected to be refused with, asserted rather than
# ignored: the refusals are the point.
refused() {
  local method=$1 path=$2 token=$3 body=$4 want=$5 code
  code=$(curl -s -o /dev/null -w '%{http_code}' -X "$method" "$API$path" \
    -H "Authorization: Bearer $token" -H 'Content-Type: application/json' -d "$body")
  if [ "$code" != "$want" ]; then
    echo "EXPECTED $want from $method $path, got $code" >&2
    exit 1
  fi
  echo "   refused with $code, as it should be"
}

echo "1. Evidence recorded, verified, approved and published — four different people"
EV=$(req POST /evidence/ "$RESEARCHER" \
  "{\"organisation_id\":\"$ORG\",\"source_id\":\"$SOURCE\",\"title\":\"Twelve boreholes rehabilitated in Kano\",\"geography_id\":\"$KANO\",\"thematic_area_id\":\"$WATER\",\"outcome\":\"Twelve boreholes returned to service.\"}" | jid)
req POST /evidence/$EV/verify "$VERIFIER" '{"notes":"Checked against the LGA works register."}' > /dev/null
echo "   the verifier cannot also approve it:"
refused POST /evidence/$EV/approve "$VERIFIER" '{"comments":"Mine to approve."}' 403
req POST /evidence/$EV/approve "$APPROVER" '{"comments":"Source checks out."}' > /dev/null
req POST /evidence/$EV/publish "$EDITOR" > /dev/null
echo "   evidence=$EV"

echo "2. A claim is logged, assessed against that evidence, approved, answered publicly"
# Two different role sets, which is the point rather than an inconvenience:
# logging a claim is for the people who watch (analyst, researcher, field
# officer), and assessing one is for the people who check (verifier,
# evidence manager, integrity analyst). An earlier version of this script
# used the analyst for both and the 403 went unnoticed, because every call
# was sent with -o /dev/null.
SIG=$(req POST /integrity/ "$ANALYST" \
  "{\"organisation_id\":\"$ORG\",\"claim\":\"The borehole programme was cancelled and the money returned.\",\"source\":\"Voice notes forwarded on WhatsApp\",\"geography_id\":\"$KANO\",\"thematic_area_id\":\"$WATER\"}" | jid)
echo "   a finding citing nothing cannot be signed off:"
req POST /integrity/$SIG/assess "$VERIFIER" \
  '{"finding":"false","assessment":"Nothing cited yet."}' > /dev/null
refused POST /integrity/$SIG/approve "$APPROVER" "{}" 400
req POST /integrity/$SIG/assess "$VERIFIER" \
  "{\"finding\":\"false\",\"assessment\":\"The works register and the published handover record both show twelve boreholes back in service.\",\"evidence_id\":\"$EV\"}" > /dev/null
req POST /integrity/$SIG/approve "$APPROVER" '{}' > /dev/null
req POST /integrity/$SIG/respond "$VERIFIER" \
  '{"response":"The programme is running. Twelve boreholes were completed in June."}' > /dev/null
echo "   the approver cannot also publish it:"
refused POST /integrity/$SIG/publish "$APPROVER" '{}' 403
req POST /integrity/$SIG/publish "$EDITOR" > /dev/null
echo "   signal=$SIG"

echo "3. A decision is raised against that finding, and closed by a second person"
ACT=$(req POST /actions/ "$EXEC" \
  "{\"organisation_id\":\"$ORG\",\"title\":\"Publish the correction in Hausa\",\"rationale\":\"The claim is circulating on voice notes, which the English correction does not reach.\",\"origin_type\":\"integrity_signal\",\"origin_id\":\"$SIG\",\"owner_id\":\"$USER_EXECUTIVE\",\"geography_id\":\"$KANO\",\"thematic_area_id\":\"$WATER\"}" | jid)
req POST /actions/$ACT/accept "$EXEC" > /dev/null
req POST /actions/$ACT/start "$EXEC" > /dev/null
echo "   the owner cannot record their own action as done:"
refused POST /actions/$ACT/complete "$EXEC" '{"outcome":"I did it."}' 403
req POST /actions/$ACT/complete "$APPROVER" \
  '{"outcome":"Hausa correction published on the portal on 14 September."}' > /dev/null
echo "   action=$ACT"

echo
echo "4. What the intelligence layer says about all of it"
curl -s -H "Authorization: Bearer $ANALYST" "$API/intelligence/overview" | python3 -c "
import sys,json
for f in json.load(sys.stdin)['figures']:
    print('   %-34s %s' % (f['label'], 'withheld' if f['suppressed'] else f['value']))"
echo
echo "5. The decision trail"
curl -s -H "Authorization: Bearer $ANALYST" "$API/intelligence/changes?measure=actions" | python3 -c "
import sys,json
for e in reversed(json.load(sys.stdin)['data']):
    moved = ', '.join('%s: %s -> %s' % (c['field'], c['from'], c['to']) for c in e['changed'])
    print('   %-10s %-14s %s' % (e['action'], e['actor'], moved))"
