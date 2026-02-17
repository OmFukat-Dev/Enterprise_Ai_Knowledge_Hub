"""Initial migration

Revision ID: 0001_initial_migration
Revises: 
Create Date: 2025-12-18 19:46:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision = '0001_initial_migration'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create enum types
    document_status = sa.Enum('uploaded', 'processing', 'processed', 'error', name='documentstatus')
    document_status.create(op.get_bind(), checkfirst=True)
    
    document_type = sa.Enum('pdf', 'docx', 'txt', 'markdown', 'html', 'unknown', name='documenttype')
    document_type.create(op.get_bind(), checkfirst=True)

    # Create roles table
    op.create_table('roles',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True, index=True),
        sa.Column('name', sa.String(length=50), nullable=False, unique=True, index=True),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True, index=True),
        sa.Column('email', sa.String(length=255), nullable=False, unique=True, index=True),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('is_verified', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create user_roles association table
    op.create_table('user_roles',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
        sa.PrimaryKeyConstraint('user_id', 'role_id')
    )

    # Create documents table
    op.create_table('documents',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True, index=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('file_path', sa.String(length=512), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('file_type', sa.Enum('pdf', 'docx', 'txt', 'markdown', 'html', 'unknown', name='documenttype'), nullable=True),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('status', sa.Enum('uploaded', 'processing', 'processed', 'error', name='documentstatus'), nullable=True),
        sa.Column('is_public', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=func.now(), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create document_chunks table
    op.create_table('document_chunks',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True, index=True),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('embedding_id', sa.String(length=255), nullable=True),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('document_chunks')
    op.drop_table('documents')
    op.drop_table('user_roles')
    op.drop_table('users')
    op.drop_table('roles')
    
    # Drop enum types
    op.execute('DROP TYPE IF EXISTS documentstatus')
    op.execute('DROP TYPE IF EXISTS documenttype')
