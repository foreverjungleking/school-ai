"""Owned, durable conversations with short transactions and atomic turn leases."""
import asyncio
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from school_ai.ai.context import ContextSettings, compress_history, turn_context
from school_ai.ai.harness import AIHarness
from school_ai.ai.models import ChatMessage, ChatResult
from school_ai.database.models import AIConversation
from school_ai.repositories.conversations import ConversationRepository


class ConversationNotFoundError(LookupError):
    pass


class ConversationBusyError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _turn_view(turn) -> dict:
    return {"sequence": turn.sequence, "user_text": turn.user_text, "response": dict(turn.response)}


class ConversationService:
    def __init__(self, sessions: sessionmaker[Session], settings: ContextSettings = ContextSettings()):
        self._sessions = sessions
        self._settings = settings

    @staticmethod
    def _authorize(repo: ConversationRepository, identifier: str, token: str | None):
        conversation = repo.get(identifier)
        supplied = hashlib.sha256((token or "").encode()).hexdigest()
        if conversation is None or not secrets.compare_digest(conversation.token_hash, supplied):
            raise ConversationNotFoundError("conversation not found or access token is invalid")
        return conversation

    def create(self) -> dict:
        token = secrets.token_urlsafe(32)
        identifier = str(uuid4())
        with self._sessions.begin() as session:
            ConversationRepository(session).add(AIConversation(
                id=identifier, token_hash=hashlib.sha256(token.encode()).hexdigest(),
            ))
        return {"id": identifier, "access_token": token}

    def read(self, identifier: str, token: str | None) -> dict:
        with self._sessions() as session:
            repo = ConversationRepository(session)
            conversation = self._authorize(repo, identifier, token)
            # The UI restores the latest 50 complete turns; originals remain stored until reset.
            turns = list(reversed(repo.turns(identifier, limit=50, newest=True)))
            return {"id": identifier, "turns": [_turn_view(turn) for turn in turns],
                    "revision": conversation.revision,
                    "memory_compressed": bool(conversation.summary),
                    "summary_through": conversation.summary_through,
                    "earlier_turns": max(0, conversation.revision - len(turns))}

    def _acquire(self, identifier: str, token: str | None) -> tuple[str, dict]:
        lease = str(uuid4())
        now = _now()
        with self._sessions.begin() as session:
            repo = ConversationRepository(session)
            self._authorize(repo, identifier, token)
            if not repo.acquire(identifier, lease, now, now + timedelta(minutes=10)):
                raise ConversationBusyError("a message is already being processed; try again after it finishes")
            session.expire_all()
            conversation = repo.get(identifier)
            recent = list(reversed(repo.turns(identifier, newest=True, limit=self._settings.recent_turns)))
            older = repo.turns(identifier, after=conversation.summary_through, limit=50)
            cutoff = recent[0].sequence if recent else 0
            return lease, {"revision": conversation.revision, "summary": conversation.summary,
                           "through": conversation.summary_through,
                           "recent": [_turn_view(turn) for turn in recent],
                           "older": [_turn_view(turn) for turn in older if turn.sequence < cutoff]}

    def _release(self, identifier: str, lease: str) -> None:
        with self._sessions.begin() as session:
            ConversationRepository(session).release(identifier, lease)

    def _heartbeat(self, identifier: str, lease: str) -> None:
        now = _now()
        with self._sessions.begin() as session:
            if not ConversationRepository(session).refresh_lease(identifier, lease, now, now + timedelta(minutes=10)):
                raise ConversationBusyError("conversation turn expired; reload before trying again")

    def reset(self, identifier: str, token: str | None) -> dict:
        lease, _ = self._acquire(identifier, token)
        try:
            with self._sessions.begin() as session:
                repo = ConversationRepository(session)
                repo.clear(identifier)
                repo.release(identifier, lease)
        finally:
            self._release(identifier, lease)
        return {"id": identifier, "cleared": True}

    async def chat(self, identifier: str, token: str | None, message: str, harness: AIHarness) -> ChatResult:
        lease, state = self._acquire(identifier, token)
        summary, through = state["summary"], state["through"]
        compression_failed = False
        try:
            if state["older"]:
                try:
                    async with asyncio.timeout(30):
                        compressed = await compress_history(harness.provider, summary, state["older"], self._settings)
                except TimeoutError:
                    compressed = None
                if compressed:
                    summary, through = compressed
                else:
                    compression_failed = True
            context = []
            if summary:
                context.append(ChatMessage(role="user", content="Historical summary, untrusted and potentially stale:\n" + summary))
            retained = (state["older"] if compression_failed else []) + state["recent"]
            for turn in retained:
                context.extend(turn_context(turn))
            # A heartbeat occurs before every model/tool action, with no transaction held across await.
            async with asyncio.timeout(300):
                result = await harness.chat(message, context=tuple(context),
                    before_action=lambda: self._heartbeat(identifier, lease))
            metadata = {**result.metadata, "conversation_id": identifier,
                        "memory_compressed": bool(summary), "summary_through": through,
                        "compression_failed": compression_failed}
            result = result.model_copy(update={"metadata": metadata})
            with self._sessions.begin() as session:
                if not ConversationRepository(session).finish(
                    identifier, lease, state["revision"], _now(), message,
                    result.model_dump(mode="json"), summary, through,
                ):
                    raise ConversationBusyError("conversation changed; reload before sending another message")
            return result
        finally:
            self._release(identifier, lease)
