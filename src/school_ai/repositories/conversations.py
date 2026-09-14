"""Conversation persistence; transaction ownership belongs to the service."""
from datetime import datetime

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from school_ai.database.models import AIConversation, AIConversationTurn


class ConversationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, identifier: str) -> AIConversation | None:
        return self.session.get(AIConversation, identifier)

    def add(self, conversation: AIConversation) -> None:
        self.session.add(conversation)

    def acquire(self, identifier: str, lease: str, now: datetime, until: datetime) -> bool:
        result = self.session.execute(update(AIConversation).where(
            AIConversation.id == identifier,
            or_(AIConversation.lease_id.is_(None), AIConversation.lease_until < now),
        ).values(lease_id=lease, lease_until=until))
        return result.rowcount == 1

    def release(self, identifier: str, lease: str) -> None:
        self.session.execute(update(AIConversation).where(
            AIConversation.id == identifier, AIConversation.lease_id == lease,
        ).values(lease_id=None, lease_until=None))

    def refresh_lease(self, identifier: str, lease: str, now: datetime, until: datetime) -> bool:
        result = self.session.execute(update(AIConversation).where(
            AIConversation.id == identifier, AIConversation.lease_id == lease,
            AIConversation.lease_until >= now,
        ).values(lease_until=until))
        return result.rowcount == 1

    def turns(self, identifier: str, *, after: int = 0, limit: int = 50,
              newest: bool = False) -> list[AIConversationTurn]:
        order = AIConversationTurn.sequence.desc() if newest else AIConversationTurn.sequence
        return list(self.session.scalars(select(AIConversationTurn).where(
            AIConversationTurn.conversation_id == identifier,
            AIConversationTurn.sequence > after,
        ).order_by(order).limit(limit)))

    def finish(self, identifier: str, lease: str, revision: int, now: datetime,
               user_text: str, response: dict, summary: str, through: int) -> bool:
        result = self.session.execute(update(AIConversation).where(
            AIConversation.id == identifier, AIConversation.lease_id == lease,
            AIConversation.revision == revision, AIConversation.lease_until >= now,
        ).values(revision=revision + 1, summary=summary, summary_through=through,
                 lease_id=None, lease_until=None))
        if result.rowcount != 1:
            return False
        self.session.add(AIConversationTurn(
            conversation_id=identifier, sequence=revision + 1,
            user_text=user_text, response=response,
        ))
        return True

    def clear(self, identifier: str) -> None:
        self.session.execute(delete(AIConversationTurn).where(
            AIConversationTurn.conversation_id == identifier
        ))
        self.session.execute(update(AIConversation).where(AIConversation.id == identifier).values(
            summary="", summary_through=0, revision=0,
        ))
