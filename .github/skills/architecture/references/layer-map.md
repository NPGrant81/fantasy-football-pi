# Layer Map Reference

This is a derived quick reference for the architecture skill. The canonical
authority is [`docs/ARCHITECTURE.md`](../../../../docs/ARCHITECTURE.md); if this
summary conflicts with that document, the canonical authority takes precedence.

Dependency direction is one way:

1. The React frontend calls the FastAPI API through shared API clients.
2. FastAPI routers validate transport input and delegate business behavior.
3. Services own domain logic and coordinate persistence.
4. SQLAlchemy models and database modules own persistence mapping and access.
5. PostgreSQL stores application state.

Placement summary:

| Concern | Location |
| --- | --- |
| Route handlers | `backend/routers/` |
| Business logic | `backend/services/` |
| Request and response schemas | `backend/schemas/` |
| Persistence models | `backend/models.py` or `backend/models/` |
| Page-level UI | `frontend/src/pages/` |
| Shared UI | `frontend/src/components/` |
| API clients | `frontend/src/api/` |

The topology authority is [`docs/architecture/overview.md`](../../../../docs/architecture/overview.md).