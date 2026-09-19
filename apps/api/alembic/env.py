"""Alembic migration environment configuration."""

from logging.config import fileConfig

from alembic import context
from geoalchemy2 import alembic_helpers
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.models import Base

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set sqlalchemy.url
config.set_main_option("sqlalchemy.url", settings.database_url)

# Model's MetaData object for 'autogenerate' support
target_metadata = Base.metadata

# GeoAlchemy2's helpers keep autogenerate away from PostGIS-managed tables such
# as spatial_ref_sys, which it would otherwise propose dropping, and render
# geometry columns with the right import.
COMMON_OPTIONS = {
    "target_metadata": target_metadata,
    "compare_type": True,
    "include_object": alembic_helpers.include_object,
    "process_revision_directives": alembic_helpers.writer,
    "render_item": alembic_helpers.render_item,
}


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **COMMON_OPTIONS,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, **COMMON_OPTIONS)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
