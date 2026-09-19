# EPIRO API Documentation

## Overview

The EPIRO API is a RESTful API for managing evidence, public information, citizen questions, and organizational readiness. All endpoints follow REST conventions and return JSON responses.

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

All endpoints except `/auth/register`, `/auth/login`, and `/questions` (for submission) require Bearer token authentication.

### Getting Started

1. **Register a new account**
   ```bash
   POST /auth/register
   ```

2. **Login**
   ```bash
   POST /auth/login
   ```

3. **Use the token**
   ```bash
   Authorization: Bearer <access_token>
   ```

## Response Format

### Success Response (200, 201)
```json
{
  "id": "uuid",
  "field1": "value1",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### List Response (200)
```json
{
  "total": 100,
  "page": 1,
  "page_size": 10,
  "total_pages": 10,
  "data": [...]
}
```

### Error Response (4xx, 5xx)
```json
{
  "detail": "Error message"
}
```

## Endpoints

### Authentication (`/auth`)

#### Register User
```
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "password": "securepassword123"
}

Response: 200 OK
{
  "id": "uuid",
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "is_active": true,
  "is_verified": false,
  "language": "en",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

#### Login
```
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123"
}

Response: 200 OK
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    ...
  }
}
```

#### Refresh Token
```
POST /auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}

Response: 200 OK
{
  "access_token": "new_token",
  "refresh_token": "new_refresh_token",
  "token_type": "bearer",
  "user": {...}
}
```

#### Change Password
```
POST /auth/change-password
Authorization: Bearer <token>
Content-Type: application/json

{
  "current_password": "oldpassword",
  "new_password": "newpassword123",
  "confirm_password": "newpassword123"
}

Response: 200 OK
{
  "message": "Password changed successfully"
}
```

### Users (`/users`)

#### Get Current User Profile
```
GET /users/me
Authorization: Bearer <token>

Response: 200 OK
{
  "id": "uuid",
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "is_active": true,
  "language": "en",
  ...
}
```

#### Update Current User Profile
```
PUT /users/me
Authorization: Bearer <token>
Content-Type: application/json

{
  "first_name": "Jane",
  "timezone": "Africa/Lagos",
  "language": "ha"
}

Response: 200 OK
{...updated user...}
```

#### List Users (Admin)
```
GET /users?skip=0&limit=100&search=john
Authorization: Bearer <admin_token>

Response: 200 OK
{
  "total": 50,
  "page": 1,
  "page_size": 100,
  "total_pages": 1,
  "data": [{...}, {...}]
}
```

#### Get User
```
GET /users/{user_id}
Authorization: Bearer <token>

Response: 200 OK
{...user details...}
```

#### Update User
```
PUT /users/{user_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "first_name": "Jane",
  "timezone": "Africa/Lagos"
}

Response: 200 OK
{...updated user...}
```

#### Deactivate User (Admin)
```
POST /users/{user_id}/deactivate
Authorization: Bearer <admin_token>

Response: 200 OK
{
  "message": "User deactivated successfully"
}
```

#### Activate User (Admin)
```
POST /users/{user_id}/activate
Authorization: Bearer <admin_token>

Response: 200 OK
{
  "message": "User activated successfully"
}
```

### Organisations (`/organisations`)

#### List Organisations
```
GET /organisations?skip=0&limit=100
Authorization: Bearer <token>

Response: 200 OK
{
  "total": 10,
  "page": 1,
  "page_size": 100,
  "total_pages": 1,
  "data": [
    {
      "id": "uuid",
      "name": "EPIRO",
      "code": "EPIRO",
      "country": "NG",
      "timezone": "Africa/Lagos",
      "is_active": true,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    },
    ...
  ]
}
```

#### Get Organisation
```
GET /organisations/{org_id}
Authorization: Bearer <token>

Response: 200 OK
{...organisation details...}
```

#### Create Organisation (Admin)
```
POST /organisations
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "name": "EPIRO",
  "code": "EPIRO",
  "country": "NG",
  "timezone": "Africa/Lagos",
  "description": "Evidence Management System"
}

Response: 201 Created
{...created organisation...}
```

#### Update Organisation (Admin)
```
PUT /organisations/{org_id}
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "description": "Updated description"
}

Response: 200 OK
{...updated organisation...}
```

#### Delete Organisation (Admin)
```
DELETE /organisations/{org_id}
Authorization: Bearer <admin_token>

Response: 200 OK
{
  "message": "Organisation deleted successfully"
}
```

### Evidence (`/evidence`)

#### List Evidence
```
GET /evidence?organisation_id=uuid&skip=0&limit=100&status=draft
Authorization: Bearer <token>

Response: 200 OK
{
  "total": 150,
  "page": 1,
  "page_size": 100,
  "total_pages": 2,
  "data": [
    {
      "id": "uuid",
      "title": "Community Health Initiative Impact",
      "description": "Evidence of improved healthcare access",
      "organisation_id": "uuid",
      "source_id": "uuid",
      "status": "draft",
      "verification_status": "unverified",
      "approval_status": "pending",
      "evidence_date": "2024-01-01",
      "beneficiaries": 500,
      "confidence_level": 85,
      "version": 1,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    },
    ...
  ]
}
```

#### Get Evidence
```
GET /evidence/{evidence_id}
Authorization: Bearer <token>

Response: 200 OK
{...evidence details...}
```

#### Create Evidence
```
POST /evidence
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Community Health Initiative Impact",
  "description": "Evidence description",
  "organisation_id": "uuid",
  "source_id": "uuid",
  "project_id": "uuid",
  "evidence_date": "2024-01-01",
  "beneficiaries": 500,
  "outcome": "500 people received healthcare services",
  "confidence_level": 85
}

Response: 201 Created
{...created evidence...}
```

#### Update Evidence
```
PUT /evidence/{evidence_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Updated Title",
  "confidence_level": 90
}

Response: 200 OK
{...updated evidence...}
```

#### Verify Evidence
```
POST /evidence/{evidence_id}/verify?notes=Verified+by+field+team
Authorization: Bearer <verifier_token>

Response: 200 OK
{
  ...evidence with status = "verified"...
}
```

#### Approve Evidence
```
POST /evidence/{evidence_id}/approve
Authorization: Bearer <approver_token>

Response: 200 OK
{
  ...evidence with status = "approved"...
}
```

#### Publish Evidence
```
POST /evidence/{evidence_id}/publish
Authorization: Bearer <editor_token>

Response: 200 OK
{
  ...evidence with status = "published"...
}
```

#### Delete Evidence
```
DELETE /evidence/{evidence_id}
Authorization: Bearer <token>

Response: 200 OK
{
  "message": "Evidence deleted successfully"
}
```

### Stories (`/stories`)

#### List Stories
```
GET /stories?skip=0&limit=100&language=en&featured_only=false
Authorization: Bearer <token>

Response: 200 OK
{
  "total": 25,
  "page": 1,
  "page_size": 100,
  "total_pages": 1,
  "data": [
    {
      "id": "uuid",
      "evidence_id": "uuid",
      "title": "Success Story: Community Health",
      "headline": "How 500 people accessed healthcare",
      "body": "Long form story content...",
      "summary": "Short summary...",
      "language": "en",
      "status": "draft",
      "featured": false,
      "version": 1,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    },
    ...
  ]
}
```

#### Get Story
```
GET /stories/{story_id}
Authorization: Bearer <token>

Response: 200 OK
{...story details...}
```

#### Create Story
```
POST /stories
Authorization: Bearer <editor_token>
Content-Type: application/json

{
  "evidence_id": "uuid",
  "title": "Success Story: Community Health",
  "headline": "How 500 people accessed healthcare",
  "body": "Long form story content...",
  "summary": "Short summary",
  "language": "en"
}

Response: 201 Created
{...created story...}
```

#### Update Story
```
PUT /stories/{story_id}
Authorization: Bearer <editor_token>
Content-Type: application/json

{
  "title": "Updated Title",
  "body": "Updated content"
}

Response: 200 OK
{...updated story...}
```

#### Publish Story
```
POST /stories/{story_id}/publish
Authorization: Bearer <editor_token>

Response: 200 OK
{
  ...story with status = "published"...
}
```

#### Feature Story
```
POST /stories/{story_id}/feature
Authorization: Bearer <editor_token>

Response: 200 OK
{
  ...story with featured = true...
}
```

#### Delete Story
```
DELETE /stories/{story_id}
Authorization: Bearer <editor_token>

Response: 200 OK
{
  "message": "Story deleted successfully"
}
```

### Questions (`/questions`)

#### List Questions
```
GET /questions?skip=0&limit=100&status=new&organisation_id=uuid
Authorization: Bearer <token>

Response: 200 OK
{
  "total": 45,
  "page": 1,
  "page_size": 100,
  "total_pages": 1,
  "data": [
    {
      "id": "uuid",
      "question_text": "What programs are available in my area?",
      "category": "programmes",
      "language": "en",
      "location_state": "Lagos",
      "is_anonymous": true,
      "status": "new",
      "response": null,
      "is_published": false,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:00:00Z"
    },
    ...
  ]
}
```

#### Get Question
```
GET /questions/{question_id}
Authorization: Bearer <token>

Response: 200 OK
{...question details...}
```

#### Submit Question (Public)
```
POST /questions
Content-Type: application/json

{
  "question_text": "What programs are available in my area?",
  "category": "programmes",
  "language": "en",
  "location_state": "Lagos",
  "is_anonymous": true,
  "submitter_email": "user@example.com"
}

Response: 201 Created
{...created question...}
```

#### Respond to Question
```
POST /questions/{question_id}/respond?response_text=Here+is+the+response...
Authorization: Bearer <staff_token>

Response: 200 OK
{
  ...question with response and status = "response_drafted"...
}
```

#### Approve Response
```
POST /questions/{question_id}/approve
Authorization: Bearer <approver_token>

Response: 200 OK
{
  ...question with status = "approved"...
}
```

#### Publish Question & Response
```
POST /questions/{question_id}/publish
Authorization: Bearer <editor_token>

Response: 200 OK
{
  ...question with is_published = true, status = "published"...
}
```

#### Close Question
```
POST /questions/{question_id}/close
Authorization: Bearer <staff_token>

Response: 200 OK
{
  ...question with status = "closed"...
}
```

### Information integrity (`/integrity`)

Spec sections 25-26. A claim circulating in public, what was found out about it,
and the correction that answers it. See
[INFORMATION_INTEGRITY.md](INFORMATION_INTEGRITY.md) for the rules.

The record describes information, never the people carrying it: `source` and
`circulation` are channels, and there is no field for who spread anything.

#### Log a circulating claim
```
POST /integrity/
Authorization: Bearer <monitor_token>
{
  "organisation_id": "uuid",
  "claim": "The borehole programme in Bida was cancelled and the money returned.",
  "source": "Voice notes forwarded on WhatsApp",
  "circulation": "Forwarded in community groups across three LGAs.",
  "first_observed": "2026-08-02",
  "priority": "material"
}

Response: 201 Created
{ ...signal with status = "new", finding = null... }
```

#### Record a finding
```
POST /integrity/{signal_id}/assess
Authorization: Bearer <assessor_token>
{
  "finding": "false",
  "assessment": "The programme's milestone records show 14 boreholes completed in August.",
  "evidence_id": "uuid"
}

Response: 200 OK
{ ...signal with status = "assessed"... }
```

The finding and the reasoning are one request: a verdict with no reasoning
cannot be expressed. `finding` is one of `accurate`, `misleading`,
`out_of_context`, `false`, `unsubstantiated` or `unresolved`.

#### Draft the correction
```
POST /integrity/{signal_id}/respond
Authorization: Bearer <assessor_token>
{ "response": "The programme is running. Fourteen boreholes were completed in August." }

Response: 200 OK
```

#### Approve the finding
```
POST /integrity/{signal_id}/approve
Authorization: Bearer <approver_token>
{ "comments": "Checked against the register." }

Response: 200 OK
{ ...signal with status = "approved"... }

400 — the finding names a determination but cites no evidence
409 — the cited evidence has not itself been approved
403 — the person who wrote the assessment may not approve it
```

#### Reject
```
POST /integrity/{signal_id}/reject
Authorization: Bearer <approver_token>
{ "comments": "The milestone records cited do not cover August." }

Response: 200 OK
{ ...signal back at status = "assessing", approval cleared... }
```

#### Publish the correction
```
POST /integrity/{signal_id}/publish
Authorization: Bearer <publisher_token>

Response: 200 OK
{ ...signal with status = "published"... }

403 — the person who approved the finding may not publish it
409 — the cited evidence was withdrawn since approval
```

#### Withdraw a published correction
```
POST /integrity/{signal_id}/withdraw
Authorization: Bearer <publisher_token>
{ "reason": "The milestone records were misread." }

Response: 200 OK
```

It leaves the public portal at once. A correction that turns out to be wrong is
the worst thing on the platform to leave standing.

#### Other operations

- `GET /integrity/` — list, filtered by status, priority or organisation.
- `GET /integrity/{signal_id}` — one signal.
- `PUT /integrity/{signal_id}` — revise. Rewording the claim raises the version
  and clears the finding; re-prioritising does not.
- `POST /integrity/{signal_id}/close` — no further work. Refused once
  published; withdraw instead.
- `GET /integrity/{signal_id}/approvals` — the approval trail.

### Intelligence (`/intelligence`)

Spec sections 21-22. Read-only. Every figure carries the basis that produced
it, and that basis resolves back to the records. See
[INTELLIGENCE.md](INTELLIGENCE.md).

#### Headline figures
```
GET /intelligence/overview?geography_id=<optional>
Authorization: Bearer <token>

Response: 200 OK
{
  "figures": [
    {
      "label": "Published evidence",
      "value": 4,
      "suppressed": false,
      "basis": {"measure": "evidence", "dimension": "status", "value": "published"}
    },
    ...
  ],
  "minimum_cell_size": 5,
  "suppression_note": "Counts of records submitted by members of the public are withheld where ..."
}
```

#### The records behind a figure
```
GET /intelligence/records?measure=evidence&dimension=status&value=published

Response: 200 OK
{"total": 4, "basis": {...}, "data": [ ...the four records... ]}
```

Hand a figure's own `basis` straight back as query parameters. This is what
makes the dashboard explainable rather than asserted: any number can be
checked against the rows it counted.

#### Breakdowns
```
GET /intelligence/breakdown?measure=questions&dimension=category

Response: 200 OK
{
  "measure": "questions",
  "dimension": "category",
  "figures": [
    {"label": "water", "value": 8, "suppressed": false, "basis": {...}},
    {"label": "roads", "value": null, "suppressed": true, "basis": {...}},
    {"label": "sanitation", "value": null, "suppressed": true, "basis": {...}}
  ],
  "minimum_cell_size": 5,
  "suppressed_buckets": 2
}

400 \u2014 unknown measure, or a dimension the measure does not offer
```

Buckets of **citizen-submitted** records below the minimum cell size are
withheld, **and so is the smallest reported bucket**, so the residual cannot be
recovered by subtracting from the total. Evidence, projects, missions,
integrity signals and scenarios are never suppressed: they record public works,
not people.

The 400 names the dimensions that would have worked. Dimensions are a closed
set per measure — there is no way to group by a column that identifies a
person.

#### What can be counted
```
GET /intelligence/measures

Response: 200 OK
{
  "minimum_cell_size": 5,
  "measures": [
    {"name": "questions", "label": "Questions from the public",
     "dimensions": ["category", "geography_id", "language", "status"],
     "suppressed_below_minimum": true},
    ...
  ]
}
```

Served rather than documented, so a client does not hard-code a list that
would drift from the one the server enforces.

### Field operations (`/missions`)

Spec section 18. See [FIELD_OPERATIONS.md](FIELD_OPERATIONS.md), which is
mostly about what this deliberately does not collect.

#### Plan a mission
```
POST /missions/
Authorization: Bearer <coordinator_token>
{
  "organisation_id": "uuid",
  "title": "Borehole verification \u2014 Lemu ward",
  "purpose": "Confirm the boreholes recorded as completed in August exist and run.",
  "planned_start": "2026-10-01",
  "planned_end": "2026-10-03",
  "check_in_interval_hours": 12,
  "risk_assessment": "The road past the bridge floods after rain...",
  "members": [{"user_id": "uuid", "role_on_mission": "Lead enumerator"}]
}

Response: 201 Created  (status = "planned")
```

There is no position field, here or anywhere else in this router. The mission
records the area and the window; it does not track individuals.

#### Approve it
```
POST /missions/{mission_id}/approve
Authorization: Bearer <a_different_coordinator_token>

Response: 200 OK
400 \u2014 no written risk assessment
403 \u2014 the planner may not approve their own mission
```

These two refusals are what the endpoint exists for.

#### Run it
```
POST /missions/{mission_id}/start        (team sets out; the mission is now watched)
POST /missions/{mission_id}/check-in     {"state": "safe" | "delayed" | "assistance_required",
                                          "note": "optional free text"}
POST /missions/{mission_id}/complete     {"report": "What the mission found."}
POST /missions/{mission_id}/cancel       {"reason": "Team recalled."}
```

A check-in carries a **state**, not a coordinate. `GET /missions/{id}` returns
a derived `safety` block:

```json
{"state": "assistance_required", "last_reported_at": "...",
 "overdue": false, "hours_since_report": 0.4, "needs_attention": true}
```

`GET /missions/?needs_attention=true` lists the missions that are overdue or
have asked for help.

#### Capture evidence in the field
```
POST /missions/{mission_id}/evidence
{
  "capture_key": "<client-generated, unique per organisation>",
  "title": "Borehole 4 at Lemu \u2014 running",
  "description": "Pump running, handle intact.",
  "source_id": "uuid"
}

201 Created \u2014 first time
200 OK      \u2014 this key was already used; here is the record it made
409         \u2014 the mission has not started
```

**Idempotent.** A retry returns the original record unchanged, including when
two retries arrive at once and one loses the insert race. The record starts as
an unverified draft and goes through normal verification.

- `GET /missions/{id}/evidence` \u2014 everything the mission brought back.
- `GET /missions/{id}/check-ins` \u2014 every safety report, oldest first.

### Readiness (`/scenarios`)

Spec sections 28-31. One rule governs the whole thing: **a readiness status may
be declared as bad as you like, and no better than the record supports.** See
[READINESS.md](READINESS.md).

Readiness is internal. There is no public endpoint, deliberately.

#### Register a scenario
```
POST /scenarios/
Authorization: Bearer <manager_token>
{
  "organisation_id": "uuid",
  "name": "Flood response \u2014 Bida flood plain",
  "description": "What we do when the river rises.",
  "trigger": "River level above 6 metres at the Bida gauge.",
  "drill_interval_days": 180
}

Response: 201 Created
{
  ...scenario with status = "red",
  "floor": {
    "status": "red",
    "reasons": [
      "The scenario has no playbook steps, so there is no plan",
      "The scenario has never been rehearsed, so the plan is untested"
    ]
  }
}
```

There is no status field on the request. A scenario starts RED because at
creation there is by definition nothing to support anything better.

#### Write the playbook
```
PUT /scenarios/{scenario_id}/playbook
Authorization: Bearer <manager_token>
{
  "steps": [
    {"position": 1, "title": "Confirm the gauge reading",
     "action": "Call the gauge station and confirm the level directly.",
     "responsible_role": "field_officer", "within_hours": 1},
    {"position": 2, "title": "Notify the ward heads",
     "action": "Contact every ward head in the flood plain.",
     "responsible_role": "content_manager", "within_hours": 2}
  ]
}

Response: 200 OK
400 \u2014 steps are not numbered 1..n with no gaps or repeats
422 \u2014 a step names no responsible_role
```

Sent whole rather than step by step, because the steps are ordered.

#### Rehearse it
```
POST /scenarios/{scenario_id}/drills
{"scheduled_for": "2026-10-01"}
Response: 201 Created

POST /scenarios/drills/{drill_id}/complete
Authorization: Bearer <conductor_token>
{
  "summary": "Rehearsed the call-down. Two ward heads could not be reached.",
  "findings": [
    {"description": "The ward head contact list is two years out of date.",
     "severity": "critical"}
  ]
}
Response: 200 OK

POST /scenarios/drills/{drill_id}/cancel
{"reason": "The venue was unavailable."}
Response: 200 OK
```

A completed drill requires a summary. Cancelled drills stay on the record: a
scenario whose rehearsals keep being called off is one a review should see.

#### Close a finding
```
POST /scenarios/findings/{finding_id}/resolve
Authorization: Bearer <someone_else_token>
{"resolution": "Rebuilt from the ward register and checked against the roll."}

Response: 200 OK
403 \u2014 the person who raised the finding may not confirm it resolved
409 \u2014 already resolved
```

#### Declare readiness
```
POST /scenarios/{scenario_id}/declare
Authorization: Bearer <manager_token>
{"status": "green", "rationale": "Rehearsed in March; contact list rebuilt."}

Response: 200 OK
409 \u2014 better than the record supports; the message names the gap
```

The rationale is required. Declaring *worse* than the floor always succeeds \u2014
an owner may know something the database does not.

**No role is exempt from the floor, a platform administrator included.**

#### Other operations

- `GET /scenarios/` \u2014 the readiness matrix, filtered by status or organisation.
- `GET /scenarios/{id}` \u2014 one scenario, its playbook, and its floor.
- `PUT /scenarios/{id}` \u2014 revise description, owner or drill cadence.
- `GET /scenarios/{id}/drills` \u2014 every rehearsal, cancellations included.

### Search (`/search`)

#### Global Search
```
GET /search?q=health+program&content_type=evidence&skip=0&limit=50
Authorization: Bearer <token>

Response: 200 OK
{
  "evidence": [
    {
      "id": "uuid",
      "title": "Health Program Impact",
      ...
    },
    ...
  ],
  "stories": [],
  "questions": [],
  "projects": [],
  "scenarios": [],
  "integrity_signals": [],
  "field_missions": [],
  "unsearchable_types": ["documents", "stakeholders", "intelligence", "media", "tasks"],
  "total": 5
}
```

`unsearchable_types` names the spec section 35 content types that have no
entity yet, so an incomplete result is visible rather than implied.

## Status Codes

- **200 OK** - Successful GET, PUT
- **201 Created** - Successful POST
- **204 No Content** - Successful DELETE
- **400 Bad Request** - Invalid input
- **401 Unauthorized** - Missing or invalid token
- **403 Forbidden** - Insufficient permissions
- **404 Not Found** - Resource not found
- **500 Internal Server Error** - Server error

## Rate Limiting

The API is rate-limited to 100 requests per minute per user. Rate limit headers are included in responses.

## Pagination

All list endpoints support pagination:
- `skip` - Number of records to skip (default: 0)
- `limit` - Number of records to return (default: 100, max: 1000)

## Filtering

List endpoints support filtering by various fields:
- `status` - Filter by status
- `language` - Filter by language
- `organisation_id` - Filter by organisation
- `search` - Full-text search

## Error Handling

All errors return a JSON response with a `detail` field:

```json
{
  "detail": "Invalid credentials"
}
```

## Interactive Documentation

Access the interactive API documentation at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Examples

### Create Evidence Workflow
```bash
# 1. Create evidence
curl -X POST http://localhost:8000/api/v1/evidence \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Health Initiative",
    "organisation_id": "org_uuid",
    "source_id": "source_uuid",
    "beneficiaries": 100,
    "confidence_level": 85
  }'

# 2. Verify evidence
curl -X POST http://localhost:8000/api/v1/evidence/{id}/verify \
  -H "Authorization: Bearer $VERIFIER_TOKEN" \
  -H "Content-Type: application/json"

# 3. Approve evidence
curl -X POST http://localhost:8000/api/v1/evidence/{id}/approve \
  -H "Authorization: Bearer $APPROVER_TOKEN" \
  -H "Content-Type: application/json"

# 4. Create story from evidence
curl -X POST http://localhost:8000/api/v1/stories \
  -H "Authorization: Bearer $EDITOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "evidence_id": "evidence_uuid",
    "title": "Success Story",
    "body": "Story content..."
  }'

# 5. Publish story
curl -X POST http://localhost:8000/api/v1/stories/{id}/publish \
  -H "Authorization: Bearer $EDITOR_TOKEN"
```

## Support

For API issues or questions, refer to the [Architecture Guide](../ARCHITECTURE.md) or submit an issue on GitHub.
