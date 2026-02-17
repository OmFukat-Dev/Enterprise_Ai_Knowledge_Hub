# This file makes the models directory a Python package
# Import models to ensure they are registered with SQLAlchemy
from .base import Base
from .user import User, Role
from .document import Document, DocumentChunk

# This makes the models available when importing from src.models
__all__ = ['Base', 'User', 'Role', 'Document', 'DocumentChunk']