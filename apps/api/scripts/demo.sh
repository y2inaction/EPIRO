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

jid() { python3 -c "import sys,json; print(json.load(sys.stdin)['id'])"; }

echo "1. Evidence recorded, verified, approved and published — four different people"
EV=$(curl -s -X POST $API/evidence/ -H "Authorization: Bearer $RESEARCHER" -H 'Content-Type: application/json' \
  -d "{\"organisation_id\":\"$ORG\",\"source_id\":\"$SOURCE\",\"title\":\"Twelve boreholes rehabilitated in Kano\",\"geography_id\":\"$KANO\",\"thematic_area_id\":\"$WATER\",\"outcome\":\"Twelve boreholes returned to service.\"}" | jid)
curl -s -X POST $API/evidence/$EV/verify -H "Authorization: Bearer $VERIFIER" -H 'Content-Type: application/json' -d '{"notes":"Checked against the LGA works register."}' -o /dev/null
curl -s -X POST $API/evidence/$EV/approve -H "Authorization: Bearer $APPROVER" -H 'Content-Type: application/json' -d '{"comments":"Source checks out."}' -o /dev/null
curl -s -X POST $API/evidence/$EV/publish -H "Authorization: Bearer $EDITOR" -o /dev/null
echo "   evidence=$EV"

echo "2. A claim is logged, assessed against that evidence, approved, answered publicly"
SIG=$(curl -s -X POST $API/integrity/ -H "Authorization: Bearer $ANALYST" -H 'Content-Type: application/json' \
  -d "{\"organisation_id\":\"$ORG\",\"claim\":\"The borehole programme was cancelled and the money returned.\",\"source\":\"Voice notes forwarded on WhatsApp\",\"geography_id\":\"$KANO\",\"thematic_area_id\":\"$WATER\"}" | jid)
curl -s -X POST $API/integrity/$SIG/assess -H "Authorization: Bearer $ANALYST" -H 'Content-Type: application/json' \
  -d "{\"finding\":\"false\",\"assessment\":\"The works register and the published handover record both show twelve boreholes back in service.\",\"evidence_id\":\"$EV\"}" -o /dev/null
curl -s -X POST $API/integrity/$SIG/approve -H "Authorization: Bearer $APPROVER" -o /dev/null
curl -s -X POST $API/integrity/$SIG/respond -H "Authorization: Bearer $ANALYST" -H 'Content-Type: application/json' \
  -d '{"response":"The programme is running. Twelve boreholes were completed in June."}' -o /dev/null
curl -s -X POST $API/integrity/$SIG/publish -H "Authorization: Bearer $EDITOR" -o /dev/null
echo "   signal=$SIG"

echo "3. A decision is raised against that finding, and closed by a second person"
ACT=$(curl -s -X POST $API/actions/ -H "Authorization: Bearer $EXEC" -H 'Content-Type: application/json' \
  -d "{\"organisation_id\":\"$ORG\",\"title\":\"Publish the correction in Hausa\",\"rationale\":\"The claim is circulating on voice notes, which the English correction does not reach.\",\"origin_type\":\"integrity_signal\",\"origin_id\":\"$SIG\",\"owner_id\":\"$USER_EXECUTIVE\",\"geography_id\":\"$KANO\",\"thematic_area_id\":\"$WATER\"}" | jid)
curl -s -X POST $API/actions/$ACT/accept -H "Authorization: Bearer $EXEC" -o /dev/null
curl -s -X POST $API/actions/$ACT/start -H "Authorization: Bearer $EXEC" -o /dev/null
SELF=$(curl -s -o /dev/null -w "%{http_code}" -X POST $API/actions/$ACT/complete -H "Authorization: Bearer $EXEC" -H 'Content-Type: application/json' -d '{"outcome":"I did it."}')
echo "   owner closing their own: HTTP $SELF (expected 403)"
curl -s -X POST $API/actions/$ACT/complete -H "Authorization: Bearer $APPROVER" -H 'Content-Type: application/json' \
  -d '{"outcome":"Hausa correction published on the portal on 14 September."}' -o /dev/null
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
