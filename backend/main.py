import os
import sys
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from dotenv import load_dotenv
from pydantic import ValidationError

load_dotenv()

# fix package context when running from backend/ directory
# (e.g. `uvicorn main:app` instead of `uvicorn backend.main:app`).
# We also handle script mode by importing every symbol via importlib so that
# modules are always loaded as `backend.xxx`.  Detection starts by checking
# whether the module is executed as __main__ or has no package name.
if __name__ == "__main__" or __package__ in (None, ""):
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(pkg_dir)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    # import everything explicitly from backend so module name is correct
    import importlib
    backend_pkg = importlib.import_module("backend")
    models = importlib.import_module("backend.models")
    dbmod = importlib.import_module("backend.database")
    configmod = importlib.import_module("backend.core.config")
    secmod = importlib.import_module("backend.core.security")
    logging_config = importlib.import_module("backend.logging_config")
    # load routers package and each submodule explicitly
    routers_pkg = importlib.import_module("backend.routers")
    # the package itself may not yet have attributes for each router, so import
    # them individually and bind to names below
    admin = importlib.import_module("backend.routers.admin")
    admin_nfl = importlib.import_module("backend.routers.admin_nfl")
    admin_live_scoring = importlib.import_module("backend.routers.admin_live_scoring")
    admin_drafts = importlib.import_module("backend.routers.admin_drafts")
    admin_config = importlib.import_module("backend.routers.admin_config")
    team = importlib.import_module("backend.routers.team")
    matchups = importlib.import_module("backend.routers.matchups")
    league = importlib.import_module("backend.routers.league")
    advisor = importlib.import_module("backend.routers.advisor")
    dashboard = importlib.import_module("backend.routers.dashboard")
    players = importlib.import_module("backend.routers.players")
    waivers = importlib.import_module("backend.routers.waivers")
    draft = importlib.import_module("backend.routers.draft")
    auth = importlib.import_module("backend.routers.auth")
    feedback = importlib.import_module("backend.routers.feedback")
    trades = importlib.import_module("backend.routers.trades")
    platform_tools = importlib.import_module("backend.routers.platform_tools")
    etl = importlib.import_module("backend.routers.etl")
    nfl = importlib.import_module("backend.routers.nfl")
    playoffs = importlib.import_module("backend.routers.playoffs")
    analytics = importlib.import_module("backend.routers.analytics")
    news = importlib.import_module("backend.routers.news")
    keepers = importlib.import_module("backend.routers.keepers")
    divisions = importlib.import_module("backend.routers.divisions")
    scoring = importlib.import_module("backend.routers.scoring")
    analytics = importlib.import_module("backend.routers.analytics")

    engine = dbmod.engine
    SessionLocal = dbmod.SessionLocal
    probe_database = dbmod.probe_database
    RuntimeSettings = configmod.RuntimeSettings
    get_settings = configmod.get_settings
    get_password_hash = secmod.get_password_hash
    check_is_commissioner = secmod.check_is_commissioner
    configure_logging = logging_config.configure_logging
    watchdog_service = importlib.import_module("backend.services.live_scoring_watchdog_service")
    polling_service = importlib.import_module("backend.services.live_scoring_polling_service")
    player_news_scheduler_service = importlib.import_module("backend.services.player_news_scheduler_service")
    runtime_scheduler_service = importlib.import_module("backend.services.runtime_scheduler_service")
    schema_readiness_service = importlib.import_module("backend.services.schema_readiness_service")
    live_scoring_event_bus = importlib.import_module("backend.services.live_scoring_event_bus")
    live_scoring_sse = importlib.import_module("backend.routers.live_scoring_sse")
    run_seeder = importlib.import_module("backend.scripts.seed").run_seeder
else:
    # normal package imports
    from . import models
    from .database import engine, SessionLocal, probe_database
    from .core.config import RuntimeSettings, get_settings
    from .core.security import get_password_hash, check_is_commissioner
    from .logging_config import configure_logging
    from .services import live_scoring_watchdog_service as watchdog_service
    from .services import live_scoring_polling_service as polling_service
    from .services import player_news_scheduler_service
    from .services import runtime_scheduler_service
    from .services import schema_readiness_service
    from .services import live_scoring_event_bus
    from .routers import live_scoring_sse
    from .scripts.seed import run_seeder
    from .routers import (
        admin,
        admin_nfl,
        admin_live_scoring,
        admin_drafts,
        admin_config,
        team,
        matchups,
        league,
        advisor,
        dashboard, players, waivers, draft, auth, feedback, trades, platform_tools, etl, nfl, playoffs, analytics, news, keepers, divisions, scoring
    )

configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()


def _initialize_database() -> None:
    logger.info("Database startup phase: connectivity check")
    try:
        probe_database(engine)
    except Exception as exc:
        logger.exception("Database connectivity check failed during startup")
        raise RuntimeError("Database connectivity check failed during startup") from exc

    logger.info("Database startup phase: schema readiness check")
    try:
        schema_readiness_service.assert_schema_ready(engine, models.Base.metadata)
    except Exception as exc:
        logger.exception("Database schema readiness check failed during startup")
        raise RuntimeError("Database schema readiness check failed during startup") from exc

    logger.info("Database startup phases completed")


def _advisor_runtime_status() -> dict[str, bool | str]:
    has_gemini_key = bool(os.getenv("GEMINI_API_KEY"))
    has_google_key = bool(os.getenv("GOOGLE_API_KEY"))
    has_api_key = has_gemini_key or has_google_key
    has_genai_sdk = bool(getattr(advisor, "genai", None))

    key_source = "none"
    if has_google_key:
        key_source = "GOOGLE_API_KEY"
    elif has_gemini_key:
        key_source = "GEMINI_API_KEY"

    return {
        "enabled": has_api_key and has_genai_sdk,
        "has_api_key": has_api_key,
        "has_genai_sdk": has_genai_sdk,
        "key_source": key_source,
    }


def _create_runtime_scheduler_manager():
    registrations = (
        runtime_scheduler_service.SchedulerRegistration(
            "live_scoring_watchdog",
            watchdog_service.start_live_scoring_watchdog_scheduler,
            watchdog_service.stop_live_scoring_watchdog_scheduler,
        ),
        runtime_scheduler_service.SchedulerRegistration(
            "live_scoring_polling",
            polling_service.start_live_scoring_polling_scheduler,
            polling_service.stop_live_scoring_polling_scheduler,
        ),
        runtime_scheduler_service.SchedulerRegistration(
            "player_news_ingest",
            player_news_scheduler_service.start_player_news_ingest_scheduler,
            player_news_scheduler_service.stop_player_news_ingest_scheduler,
        ),
    )
    return runtime_scheduler_service.RuntimeSchedulerManager(registrations, logger)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager takes the place of startup/shutdown events.

    Migrations and schema readiness checks complete before the application
    starts accepting requests.
    """
    # --- startup portion ---
    _initialize_database()

    try:
        if settings.auto_seed_on_startup:
            run_seeder(SessionLocal, get_password_hash)
    except Exception:
        logger.exception("Could not run startup seeder")

    advisor_status = _advisor_runtime_status()
    logger.info(
        "Advisor runtime status enabled=%s has_api_key=%s has_genai_sdk=%s key_source=%s",
        advisor_status["enabled"],
        advisor_status["has_api_key"],
        advisor_status["has_genai_sdk"],
        advisor_status["key_source"],
    )
    if not advisor_status["has_api_key"]:
        logger.warning(
            "League Chatbot advisor is DISABLED: neither GEMINI_API_KEY nor GOOGLE_API_KEY is set. "
            "Set one of these in your backend.env file to enable the chatbot."
        )

    try:
        import asyncio as _asyncio
        live_scoring_event_bus.set_event_loop(_asyncio.get_event_loop())
    except Exception:
        logger.exception("Could not register event loop with live scoring event bus")

    scheduler_manager = _create_runtime_scheduler_manager()
    try:
        scheduler_manager.start()
        yield
    finally:
        scheduler_manager.stop()


def _validate_production_secrets() -> None:
    """Validate a fresh environment snapshot for CLI checks and tests."""
    try:
        RuntimeSettings()
    except ValidationError as exc:
        raise RuntimeError("Runtime configuration validation failed") from exc


# Validate secrets before app creation
_validate_production_secrets()

app = FastAPI(title="Fantasy Football War Room API", lifespan=lifespan)
app.state.started_at = datetime.now(timezone.utc)


def _is_production_env() -> bool:
    return settings.is_production


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    if exc.status_code >= 500 and _is_production_env():
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": "Internal server error"},
            headers=exc.headers,
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception):
    logger.exception("Unhandled server exception")
    if _is_production_env():
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
    return JSONResponse(status_code=500, content={"detail": str(exc)})

ACCESS_TOKEN_COOKIE_NAME = settings.access_token_cookie_name
CSRF_COOKIE_NAME = settings.csrf_cookie_name
CSRF_HEADER_NAME = settings.csrf_header_name
CSRF_EXEMPT_PATHS = {
    "/auth/token",
    "/analytics/visit",
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
}


# --- 1. DATABASE SETUP ---
# The database initialization logic has been moved into the lifespan
# manager above.  We no longer use an `@app.on_event("startup")` handler
# because lifespan provides a more reliable ordering and allows tests to
# bypass the routine when desired.
# --- 2. SECURITY: CORS ---
# Allow development origins; when running locally we accept any origin to
# simplify front-end testing.  In production this should be locked down.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

cors_csrf_header = settings.csrf_header_name
cors_allow_headers = [
    "Authorization",
    "Content-Type",
    "Accept",
    "Origin",
    "X-Requested-With",
    cors_csrf_header,
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=cors_allow_headers,
)


@app.middleware("http")
async def add_security_headers(request, call_next):
    is_unsafe_method = request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}
    is_exempt_path = request.url.path in CSRF_EXEMPT_PATHS or request.url.path.startswith("/docs")

    if is_unsafe_method and not is_exempt_path:
        cookie_access_token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
        auth_header = request.headers.get("Authorization", "")
        uses_cookie_auth = bool(cookie_access_token) and not auth_header.lower().startswith("bearer ")

        if uses_cookie_auth:
            csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
            csrf_header = request.headers.get(CSRF_HEADER_NAME)
            if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF token validation failed"},
                )

    response = await call_next(request)

    security_headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Content-Security-Policy": os.getenv(
            "CONTENT_SECURITY_POLICY",
            "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; object-src 'none'; "
            "script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; "
            "connect-src 'self' http://localhost:5173 http://127.0.0.1:5173 https:; font-src 'self' data:",
        ),
    }

    for header_name, header_value in security_headers.items():
        if header_name not in response.headers:
            response.headers[header_name] = header_value

    if request.url.scheme == "https" and "Strict-Transport-Security" not in response.headers:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response

# --- 3. CONNECT ROUTERS ---
# We remove 'prefix' here because your individual router files 
# (e.g., auth.py, team.py) should define them internally.

# PROTECTED: Admin requires Commissioner status
app.include_router(
    admin.router, 
    dependencies=[Depends(check_is_commissioner)] 
)
# analytics endpoints are public to league members (authorization can be added later)
app.include_router(analytics.router)
app.include_router(news.router)
# Domain-scoped admin maintenance routers.
app.include_router(admin_nfl.router)
app.include_router(admin_live_scoring.router)
app.include_router(live_scoring_sse.router)
app.include_router(admin_drafts.router)
app.include_router(admin_config.router)

# PLATFORM TOOLS: superuser endpoints such as commissioner management
# (must match prefix set in routers/platform_tools.py)
# 404 errors seen in CI tests were due to forgetting this include or
# using a mismatched path.  If you add routes here, double‑check the
# decorator paths and prefix.
app.include_router(platform_tools.router)

# STANDARD: Included without redundant prefixes
app.include_router(auth.router)
app.include_router(draft.router)
app.include_router(team.router)
app.include_router(matchups.router)
app.include_router(league.router)
app.include_router(divisions.router)
app.include_router(playoffs.router)  # new playoff endpoints
app.include_router(advisor.router)
app.include_router(dashboard.router)
app.include_router(players.router) 
app.include_router(waivers.router)
app.include_router(trades.router)
app.include_router(feedback.router)
app.include_router(etl.router)
app.include_router(nfl.router)
app.include_router(keepers.router)
app.include_router(scoring.router)

# --- 4. SEEDER (moved) ---
# The automatic seeding logic used to live here but caused every test that
# imported ``app`` to execute the full seeder.  It has been extracted into
# a standalone command-line helper; run ``python -m backend.manage seed``
# when you want to populate a new database.  This keeps TestClient from
# unintentionally hitting the seeder and avoids mysterious ``db``
# NameErrors.

@app.get("/")
def read_root():
    return {"message": "Fantasy Football API is Running!"}


@app.get("/health", operation_id="health_check_get")
@app.head("/health", operation_id="health_check_head")
def health_check(request: Request):
    db_ok = False
    schema_status = "unknown"
    try:
        probe_database(engine)
        db_ok = True
    except Exception:
        # Keep full exception details in server logs only.
        logger.exception("Health check DB probe failed")

    if db_ok:
        try:
            schema_readiness_service.assert_schema_ready(engine, models.Base.metadata)
            schema_status = "ok"
        except Exception:
            logger.exception("Health check schema readiness failed")
            schema_status = "error"

    payload = {
        "status": "ok" if db_ok else "degraded",
        "service": "fantasy-football-backend",
        "database": "ok" if db_ok else "error",
        "schema": schema_status,
        "version": os.getenv("APP_VERSION", "unknown"),
        "uptime_seconds": round(
            max(0.0, (datetime.now(timezone.utc) - app.state.started_at).total_seconds()),
            2,
        ),
        "checks": {
            "database": "ok" if db_ok else "error",
            "schema": schema_status,
        },
    }
    if request.method == "HEAD":
        return Response(status_code=200 if db_ok else 503)
    if db_ok:
        return payload
    return JSONResponse(status_code=503, content=payload)