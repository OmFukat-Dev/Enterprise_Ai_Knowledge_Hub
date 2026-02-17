from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import declarative_base as declarative_base_orm

# Create a base class for all models
Base = declarative_base()

# This is a workaround for SQLAlchemy 2.0 compatibility
# It ensures that all models inherit from the same base class
# and can be discovered by Alembic
metadata = Base.metadata

# This function is used by Alembic to get the metadata
def get_metadata():
    return metadata
