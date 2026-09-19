# EPIRO Architecture

## System Overview

EPIRO is an Evidence-first Operational Intelligence Platform implementing:
```
EVIDENCE → STORY → ENGAGEMENT → INTELLIGENCE → READINESS
```

## Core Principles

1. **Source-First**: Every factual claim traces back to evidence
2. **Citation-Backed**: All outputs link to underlying records
3. **Auditable**: Complete audit trail for consequential actions
4. **Multilingual**: Designed for i18n from day one
5. **Privacy-First**: Minimum necessary data collection
6. **Verifiable**: Evidence lifecycle tracking

## Technology Stack

### Backend
- **Language**: Python 3.11+
- **Framework**: FastAPI
- **ORM**: SQLAlchemy
- **Migrations**: Alembic
- **Validation**: Pydantic
- **Database**: PostgreSQL with PostGIS + pgvector

### Frontend
- **Framework**: Next.js 14+
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **State**: React hooks + Context API
- **UI Components**: Custom design system

### Infrastructure
- **Containerization**: Docker
- **Orchestration**: Docker Compose
- **Jobs**: Redis + Celery
- **Search**: PostgreSQL FTS + pgvector
- **Storage**: Filesystem (scalable to S3)
- **Observability**: Structured logging

## Project Structure

```
EPIRO/
├── apps/
│   ├── web/              # Next.js frontend
│   ├── api/              # FastAPI backend
│   └── worker/           # Celery workers
├── packages/
│   ├── ui/               # Shared components
│   ├── types/            # TypeScript types
│   ├── config/           # Configuration
│   └── utils/            # Shared utilities
├── infrastructure/
│   ├── docker/
│   ├── nginx/
│   └── postgres/
├── docs/
├── scripts/
└── tests/
```

## Database Architecture

### Core Entities
- **Organizations**: Institutional context
- **Users**: People with roles
- **Programmes**: High-level initiatives
- **Projects**: Specific interventions
- **Evidence**: Verified factual records
- **Sources**: Evidence origins
- **Stories**: Public information assets
- **Questions**: Citizen inquiries
- **Issues**: Information integrity cases
- **Scenarios**: Readiness situations

### Key Features
- UUID primary keys
- Temporal columns (created_at, updated_at, deleted_at)
- Audit tracking (created_by, updated_by)
- Status enums for workflows
- Versioning for published assets

## API Architecture

RESTful API with OpenAPI documentation:
- `/api/v1/auth/` - Authentication
- `/api/v1/users/` - User management
- `/api/v1/organisations/` - Organizations
- `/api/v1/programmes/` - Programmes
- `/api/v1/projects/` - Projects
- `/api/v1/evidence/` - Evidence
- `/api/v1/sources/` - Sources
- `/api/v1/stories/` - Stories
- `/api/v1/questions/` - Questions
- `/api/v1/missions/` - Field work
- `/api/v1/integrity/` - Information integrity
- `/api/v1/intelligence/` - Dashboard figures, breakdowns and drill-downs
- `/api/v1/scenarios/` - Readiness scenarios, playbooks and drills
- `/api/v1/search/` - Global search

## Implementation Phases

### Phase 1: Foundation (This Sprint)
- [x] Repository setup
- [ ] Database schema
- [ ] Authentication system
- [ ] RBAC implementation

### Phase 2: Evidence System
- Core evidence workflow
- Source registry
- Project management
- Geographic hierarchy

### Phase 3: Editorial System
- Story creation
- Media management
- Translations
- Public information

### Phase 4: Public Portal
- Search
- Maps
- Questions
- Citizen engagement

### Phase 5: Field Operations
- Mission management
- Offline PWA
- Synchronization
- Evidence capture

### Phase 6: Information Integrity
- Verification workflows
- Rapid response
- Signal tracking
- Response management

### Phase 7: Intelligence
- Analytics
- Executive dashboards
- Signal aggregation
- Readiness tracking

### Phase 8: AI/RAG
- RAG implementation
- Semantic search
- Executive briefing
- Citation handling

### Phase 9: Operations
- Testing
- Security hardening
- Observability
- Deployment

## Security Architecture

1. **Authentication**: JWT + refresh tokens
2. **Authorization**: RBAC with organization scope
3. **Data Protection**: Encryption at rest and in transit
4. **Secrets**: Environment variables with rotation
5. **Audit**: Immutable audit logs
6. **Access Control**: Least privilege principle
7. **Monitoring**: Security event logging

## Quality Gates

Before production deployment:
- [ ] All services start correctly
- [ ] Database migrations run successfully
- [ ] All API endpoints tested
- [ ] RBAC enforced
- [ ] Evidence workflows functional
- [ ] Public portal live
- [ ] Search operational
- [ ] Offline PWA working
- [ ] AI/RAG citations correct
- [ ] Audit logs immutable
- [ ] Docker deployment successful
- [ ] CI/CD pipeline green
- [ ] Security scan clear

## Development Workflow

1. Create feature branch from main
2. Implement feature with tests
3. Run linting and type checks
4. Create PR with clear description
5. Code review and CI approval
6. Merge to main
7. Deploy to staging
8. Verify in production

## Future Enhancements

- Graph database layer for relationship queries
- Real-time WebSocket notifications
- Advanced geospatial queries with PostGIS
- Vector embeddings for semantic search
- Multi-instance deployment patterns
- Rate limiting and throttling
- Content delivery network integration
