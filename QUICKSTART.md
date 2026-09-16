# EPIRO Quick Start Guide

## 5-Minute Setup

### Prerequisites

- Docker and Docker Compose
- Git
- A terminal/command line

### Step 1: Clone and Setup

```bash
git clone https://github.com/y2inaction/EPIRO.git
cd EPIRO
cp .env.example .env
```

### Step 2: Start Services

```bash
# Using docker-compose with development overrides
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

Wait for all services to start (about 30 seconds). You should see:
- ✅ postgres healthy
- ✅ redis healthy  
- ✅ api running on port 8000
- ✅ web running on port 3000

### Step 3: Initialize Database

In another terminal:

```bash
docker-compose exec api alembic upgrade head
```

### Step 4: Access Applications

- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **API ReDoc**: http://localhost:8000/redoc
- **pgAdmin**: http://localhost:5050 (admin@epiro.local / admin)

## First Test

### 1. Register a User

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "first_name": "Test",
    "last_name": "User",
    "password": "password123"
  }'
```

### 2. Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123"
  }'
```

Copy the `access_token` from the response. You'll use it for other requests.

### 3. Get Your Profile

```bash
curl -X GET http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Common Tasks

### Create an Organisation

```bash
curl -X POST http://localhost:8000/api/v1/organisations \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "EPIRO Demo",
    "code": "EPIRO-DEMO",
    "country": "NG",
    "timezone": "Africa/Lagos",
    "description": "Demo organisation"
  }'
```

### Create Evidence

```bash
# First, you need an organisation_id and source_id
# Then create evidence:

curl -X POST http://localhost:8000/api/v1/evidence \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Health Initiative Impact",
    "organisation_id": "ORG_UUID",
    "source_id": "SOURCE_UUID",
    "evidence_date": "2024-01-01",
    "beneficiaries": 500,
    "outcome": "500 people received healthcare",
    "confidence_level": 85
  }'
```

### Submit a Question (Public)

```bash
curl -X POST http://localhost:8000/api/v1/questions \
  -H "Content-Type: application/json" \
  -d '{
    "question_text": "What health programs are available?",
    "category": "health",
    "location_state": "Lagos",
    "language": "en",
    "is_anonymous": true
  }'
```

### List Evidence

```bash
curl -X GET "http://localhost:8000/api/v1/evidence?organisation_id=ORG_UUID" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Interactive Testing

Use the built-in Swagger UI at http://localhost:8000/docs to test all endpoints interactively.

## Stopping Services

```bash
docker-compose down
```

To remove volumes and reset the database:

```bash
docker-compose down -v
```

## Troubleshooting

### Services won't start

```bash
# Check logs
docker-compose logs

# Check specific service
docker-compose logs postgres
docker-compose logs api

# Rebuild images
docker-compose build
```

### Database connection error

The database takes a few seconds to start. Wait 10 seconds and try again.

### Port already in use

Change ports in `docker-compose.yml` or stop other services using those ports.

### Permission denied error

Make sure Docker daemon is running:
```bash
sudo systemctl start docker  # Linux
# or restart Docker Desktop app on macOS/Windows
```

## Development

### Backend Development

```bash
cd apps/api

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Run linter
flake8 app/
black --check app/
isort --check-only app/
```

### Frontend Development

```bash
cd apps/web

# Install dependencies
npm install

# Run dev server
npm run dev

# Run tests
npm test

# Run linter
npm run lint
```

## Project Structure

```
EPIRO/
├── apps/
│   ├── api/           # FastAPI backend
│   ├── web/           # Next.js frontend
│   └── worker/        # Celery workers (future)
├── docs/              # Documentation
├── infrastructure/    # Docker & deployment
└── packages/          # Shared code (future)
```

## Next Steps

1. **Read the documentation**
   - [Architecture Guide](./ARCHITECTURE.md)
   - [API Reference](./docs/API.md)
   - [Database Schema](./docs/DATABASE.md)

2. **Explore the code**
   - Backend: `apps/api/app/`
   - Frontend: `apps/web/app/`

3. **Try the workflows**
   - Create evidence and track it through verification
   - Submit a question and respond to it
   - Create stories from evidence

4. **Build features**
   - Follow the [Contributing Guide](./CONTRIBUTING.md)
   - Write tests for new code
   - Submit pull requests

## Getting Help

- **API Issues**: Use the Swagger UI at `/docs`
- **Architecture Questions**: See `ARCHITECTURE.md`
- **Code Questions**: Check inline comments and docstrings
- **Bugs**: Open an issue on GitHub

## Key Concepts

### Evidence Lifecycle
```
DRAFT → SUBMITTED → UNDER_REVIEW → VERIFIED → APPROVED → PUBLISHED
```

### Question Workflow
```
NEW → TRIAGED → RESEARCHING → VERIFIED → RESPONSE_DRAFTED → APPROVED → PUBLISHED → CLOSED
```

### JWT Authentication
All API requests (except registration and login) require a Bearer token:
```
Authorization: Bearer YOUR_ACCESS_TOKEN
```

Tokens expire after 1 hour. Use the refresh endpoint to get a new one.

### Organisations
All evidence, questions, and stories are scoped to organisations. You need an `organisation_id` for most operations.

## Performance Tips

- Limit results with `skip` and `limit` parameters
- Use filters to reduce data returned
- Cache responses on the frontend
- Use background jobs for heavy operations

## Security

- Never commit `.env` files with real credentials
- Use strong passwords (8+ characters)
- Rotate tokens regularly
- Check permissions before sensitive operations
- Report security issues privately

## Support

For detailed information, see:
- [README.md](./README.md)
- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [API.md](./docs/API.md)

Happy coding! 🚀
