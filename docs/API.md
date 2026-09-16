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
  "total": 5
}
```

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
