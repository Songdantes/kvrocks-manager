"""
KVrocks Manager - FastAPI Main Application
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from app.config import settings
from app.database import init_db, async_session
from app.api.auth import router as auth_router
from app.api.users import router as users_router, role_router, permission_router
from app.api.clusters import router as clusters_router, node_router
from app.api.scaling import router as scaling_router
from app.api.controllers import router as controllers_router

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress noisy third-party loggers
logging.getLogger("watchfiles").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting KVrocks Manager...")
    await init_db()
    await init_default_data()
    logger.info("KVrocks Manager started successfully")

    yield

    # Shutdown
    logger.info("Shutting down KVrocks Manager...")


async def init_default_data():
    """Initialize default roles, permissions, and admin user"""
    from app.models import User, Role, Permission
    from app.core.security import get_password_hash
    from app.core.permissions import Permissions, DEFAULT_ROLE_PERMISSIONS
    from sqlalchemy import select

    async with async_session() as db:
        # Check if already initialized
        result = await db.execute(select(User).limit(1))
        if result.scalar_one_or_none():
            return

        logger.info("Initializing default data...")

        # Create permissions
        all_permissions = {}
        for attr in dir(Permissions):
            if not attr.startswith('_'):
                code = getattr(Permissions, attr)
                module = code.split(':')[0]
                perm = Permission(
                    code=code,
                    name=code.replace(':', ' ').title(),
                    module=module
                )
                db.add(perm)
                all_permissions[code] = perm

        await db.flush()

        # Create default roles
        roles = {}
        for role_name, perm_codes in DEFAULT_ROLE_PERMISSIONS.items():
            role = Role(
                name=role_name,
                description=f"Default {role_name.replace('_', ' ').title()} role",
                is_builtin=True
            )
            if perm_codes:
                role.permissions = [all_permissions[code] for code in perm_codes if code in all_permissions]
            db.add(role)
            roles[role_name] = role

        await db.flush()

        # Create admin user
        admin = User(
            username='admin',
            password_hash=get_password_hash('admin123'),
            email='admin@example.com',
            status=True
        )
        admin.roles.append(roles['super_admin'])
        db.add(admin)

        await db.commit()
        logger.info("Default data initialized: admin user created (username: admin, password: admin123)")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="KVrocks Cluster Management Platform",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# Include routers
app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(role_router, prefix="/api")
app.include_router(permission_router, prefix="/api")
app.include_router(clusters_router, prefix="/api")
app.include_router(node_router, prefix="/api")
app.include_router(scaling_router, prefix="/api")
app.include_router(controllers_router, prefix="/api")


# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION}


# Root endpoint
@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
