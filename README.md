# EPIRO

**Evidence • Public Information • Engagement • Intelligence • Readiness Operating System**

A comprehensive, enterprise-grade platform for evidence management, public information publishing, citizen engagement, operational intelligence, and organizational readiness.

## Overview

EPIRO transforms the relationship between evidence, public information, and operational readiness. It enables organizations to:

1. **Collect & Verify Evidence** - Centralized evidence registry with full provenance tracking
2. **Publish Verified Information** - Transform evidence into multiple public information formats
3. **Engage Citizens** - Receive and respond to questions with full transparency
4. **Monitor Information Integrity** - Detect, verify, and respond to misleading information
5. **Maintain Operational Readiness** - Track scenarios, playbooks, and organizational resilience

## Core Principle

```
EVIDENCE → STORY → ENGAGEMENT → INTELLIGENCE → READINESS
```

Every factual claim is traceable to verified evidence. All outputs link to underlying records. Complete audit trails maintain accountability.

## Technology Stack

### Backend
- Python 3.11+ with FastAPI
- PostgreSQL with PostGIS & pgvector
- Redis for caching and messaging
- Celery for background jobs

### Frontend
- Next.js 14 with TypeScript
- Tailwind CSS for styling
- React Query for state management

### Infrastructure
- Docker & Docker Compose
- Nginx for reverse proxy
- GitHub Actions for CI/CD

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.11+
- Node.js 20+
- Git

### Development

1. **Clone and setup**
   ```bash
   git clone <repository>
   cd EPIRO
   cp .env.example .env
   ```

2. **Start services**
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
   ```

3. **Access applications**
   - Frontend: http://localhost:3000
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - pgAdmin: http://localhost:5050

4. **Initialize database**
   ```bash
   docker-compose exec api alembic upgrade head
   ```

## Project Structure

```
EPIRO/
├── apps/
│   ├── api/           # FastAPI backend
│   ├── web/           # Next.js frontend
│   └── worker/        # Celery workers
├── packages/          # Shared code
├── infrastructure/    # Docker & deployment config
├── docs/              # Documentation
└── scripts/           # Utility scripts
```

## Documentation

- [Architecture](./ARCHITECTURE.md) - System design and components
- [API Reference](./docs/API.md) - REST API documentation
- [Database Schema](./docs/DATABASE.md) - Data model
- [Deployment](./docs/DEPLOYMENT.md) - Production deployment
- [Security](./docs/SECURITY.md) - Security considerations

## Key Features

### Evidence Management
- Centralized evidence registry
- Full lifecycle tracking (draft → published → archived)
- Source provenance and credibility scoring
- Verification workflows
- Evidence linking to outcomes

### Public Information
- Editorial workflow with approvals
- Multiple content formats (stories, explainers, FAQs)
- Multilingual support (English, Hausa, Nupe, Pidgin)
- Asset versioning and publication history

### Citizen Engagement
- Public question submission
- Response tracking and analytics
- Anonymous submission support
- Multilingual questions

### Information Integrity
- Circulating claims logged, assessed and answered publicly
- Every finding cites the evidence it rests on
- Priority classification and impact assessment
- Published corrections on the portal, withdrawable at once

Deliberately absent: anything that profiles the people who repeat a claim. The
record is about information — see
[docs/INFORMATION_INTEGRITY.md](docs/INFORMATION_INTEGRITY.md).

### Intelligence & Analytics
- Evidence dashboard
- Geographic distribution analysis
- Question pattern analysis
- Intelligence reporting

### Organizational Readiness
- Scenarios with ordered playbooks, each step naming who acts
- Drills that record what they found, not just that they happened
- Status indicators (GREEN/AMBER/RED/BLACK) that **cannot be declared better
  than the record supports** — no plan caps a scenario at RED, an untested or
  stale plan caps it at AMBER, and no role overrides that
- Findings confirmed resolved by someone other than whoever raised them

See [docs/READINESS.md](docs/READINESS.md). Readiness is deliberately internal:
publishing where a body is weak tells the public something true and tells
anyone who would exploit it exactly where to look.

## API Endpoints

All endpoints at `/api/v1/`. This list is what exists today; the feature
sections above describe the product as a whole, and
[docs/STATUS.md](docs/STATUS.md) says which parts of it are built.

- `/auth/` - Authentication
- `/users/` - User management
- `/organisations/` - Organisation management
- `/geography/` - Geographic hierarchy
- `/thematic-areas/` - Thematic taxonomy
- `/programmes/` - Programmes
- `/projects/` - Projects, milestones and indicators
- `/sources/` - Source registry
- `/evidence/` - Evidence registry
- `/stories/` - Public information
- `/questions/` - Citizen questions
- `/integrity/` - Information integrity
- `/scenarios/` - Readiness, playbooks and drills
- `/workflows/` - Configurable review stages
- `/search/` - Global search
- `/public/` - The public portal (no authentication)

Not yet built, and so not listed above: field missions and intelligence
reports.

## Development

### Backend Development
```bash
cd apps/api
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend Development
```bash
cd apps/web
npm install
npm run dev
```

### Running Tests
```bash
# Backend
cd apps/api
pytest

# Frontend
cd apps/web
npm test
```

### Code Style
- Backend: Black, isort, flake8
- Frontend: ESLint, Prettier

## Deployment

See [Deployment Guide](./docs/DEPLOYMENT.md) for:
- Docker production build
- Environment configuration
- Database migrations
- Health checks
- Monitoring

## Security

- JWT-based authentication
- Role-based access control (RBAC)
- Encrypted sensitive data
- Audit logging
- CORS configuration
- Rate limiting
- Input validation

See [Security Guide](./docs/SECURITY.md) for detailed security practices.

## Ethical Boundaries

EPIRO is designed for lawful, non-partisan public information and evidence management. It explicitly does NOT support:

- Voter identification for persuasion
- Microtargeted political messaging
- Political preference inference
- Covert influence operations
- Voter suppression

The platform supports:
- Factual public information
- Evidence publication
- Transparent engagement
- Issue monitoring
- Information verification
- Emergency communications

## Contributing

1. Create feature branch from `develop`
2. Follow code style guidelines
3. Write tests for new features
4. Create pull request with clear description
5. Ensure CI/CD pipeline passes

## License

[Specify your license]

## Support

For issues and questions:
- Check [Documentation](./docs)
- Review [API Docs](http://localhost:8000/docs)
- Open GitHub Issue

## Roadmap

- [ ] Advanced geospatial queries
- [ ] Real-time WebSocket notifications
- [ ] Multi-instance deployment
- [ ] Enhanced AI/RAG capabilities
- [ ] Mobile app (iOS/Android)
- [ ] Advanced analytics
