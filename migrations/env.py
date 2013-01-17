from __future__ import with_statement

import sys
import os

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy import create_engine
from logging.config import fileConfig

sys.path.insert(0, os.path.abspath('./'))

import paasmaker

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

target_metadata = paasmaker.model.Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url)

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    # TODO: Allow loading a configuration file from a different location.
    paasmaker_configuration = paasmaker.common.configuration.Configuration()
    paasmaker_configuration.load_from_file(['paasmaker.yml', '/etc/paasmaker/paasmaker.yml'])
    paasmaker_configuration.setup_database()

    engine = create_engine(paasmaker_configuration.get_flat('pacemaker.dsn'))

    connection = engine.connect()
    context.configure(
                connection=connection,
                target_metadata=target_metadata
                )

    try:
        with context.begin_transaction():
            context.run_migrations()
    finally:
        connection.close()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

