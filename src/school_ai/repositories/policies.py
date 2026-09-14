"""Queries for current document versions and bounded lexical candidates."""
from sqlalchemy import case, func, literal_column, or_, select
from sqlalchemy.orm import Session

from school_ai.database.models import PolicyChunk, PolicyDocument


class PolicyRepository:
    def __init__(self, session: Session):
        self.session = session

    def document(self, source: str) -> PolicyDocument | None:
        return self.session.scalar(select(PolicyDocument).where(PolicyDocument.source == source))

    def version_exists(self, document_id: int, version: str) -> bool:
        return self.session.scalar(select(PolicyChunk.id).where(
            PolicyChunk.document_id == document_id, PolicyChunk.version == version).limit(1)) is not None

    def candidates(self, terms: list[str]) -> list[tuple[PolicyChunk, str]]:
        text = PolicyChunk.title + " " + PolicyChunk.section + " " + PolicyChunk.content
        query = select(PolicyChunk, PolicyDocument.source).join(PolicyDocument).where(
            PolicyChunk.version == PolicyDocument.current_version)
        if self.session.get_bind().dialect.name == "postgresql":
            config = literal_column("'simple'")
            vector = func.to_tsvector(config, text)
            search = func.to_tsquery(config, " | ".join(terms))
            query = query.where(vector.op("@@")(search)).order_by(func.ts_rank(vector, search).desc())
        else:
            matches = [func.lower(text).contains(term, autoescape=True) for term in terms]
            query = query.where(or_(*matches)).order_by(sum(case((match, 1), else_=0) for match in matches).desc())
        return list(self.session.execute(query.order_by(PolicyChunk.id).limit(100)))
