"""Owned AI conversations and versioned policy documents.

Revision ID: c81e4b297a10
Revises: fb5af881ec98
"""
from alembic import op
import sqlalchemy as sa

revision = "c81e4b297a10"
down_revision = "fb5af881ec98"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("ai_conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("summary_through", sa.Integer(), nullable=False),
        sa.Column("lease_id", sa.String(36)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table("ai_conversation_turns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("user_text", sa.Text(), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("conversation_id", "sequence", name="uq_ai_conversation_sequence"),
    )
    op.create_index("ix_ai_conversation_turns_conversation_id", "ai_conversation_turns", ["conversation_id"])
    op.create_table("policy_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(200), nullable=False, unique=True),
        sa.Column("current_version", sa.String(64), nullable=False),
    )
    op.create_table("policy_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("policy_documents.id"), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("section", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.UniqueConstraint("document_id", "version", "ordinal", name="uq_policy_chunk_version"),
    )
    op.create_index("ix_policy_chunks_document_id", "policy_chunks", ["document_id"])


def downgrade() -> None:
    op.drop_table("policy_chunks")
    op.drop_table("policy_documents")
    op.drop_table("ai_conversation_turns")
    op.drop_table("ai_conversations")
