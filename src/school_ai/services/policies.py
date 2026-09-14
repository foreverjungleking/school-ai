"""Versioned policy ingestion and bounded retrieval, independent of MCP/LLMs."""
import hashlib
import re
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from school_ai.ai.context import clip_text
from school_ai.database.models import PolicyChunk, PolicyDocument
from school_ai.repositories.policies import PolicyRepository

_STOP_WORDS = set("a an and are as at be can do does for from how i in is it me of on or our please school should tell that the their there this to us we what when where which who why with you about policy policies rules say says".split())


def _terms(text: str) -> list[str]:
    return sorted({word for word in re.findall(r"[^\W_]{2,40}", text.lower()) if word not in _STOP_WORDS})


def _chunks(markdown: str) -> list[tuple[str, str, str]]:
    title, section, buffer = "School policy", "Overview", []
    sections = []
    for line in markdown.splitlines():
        if line.startswith("#"):
            if buffer:
                sections.append((title, section, "\n".join(buffer).strip()))
                buffer = []
            heading = line.lstrip("#").strip()[:200]
            if line.startswith("# "):
                title = heading
            section = heading
        else:
            buffer.append(line)
    if buffer:
        sections.append((title, section, "\n".join(buffer).strip()))
    chunks = []
    for title, section, text in sections:
        while text:
            piece = clip_text(text, 1200)
            # Prefer a word boundary without dropping the remainder.
            if len(piece) < len(text) and " " in piece:
                piece = piece.rsplit(" ", 1)[0]
            chunks.append((title, section, piece))
            text = text[len(piece):].lstrip()
    return chunks


class PolicyService:
    def __init__(self, sessions: sessionmaker[Session]):
        self._sessions = sessions

    def ingest(self, source: str, markdown: str) -> dict:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,195}\.md", source):
            raise ValueError("policy source must be a simple Markdown filename")
        if not markdown.strip() or len(markdown.encode()) > 200000:
            raise ValueError("policy documents must contain 1–200000 UTF-8 bytes")
        chunks = _chunks(markdown)
        if not chunks:
            raise ValueError("policy has no body text")
        version = hashlib.sha256(markdown.encode()).hexdigest()
        with self._sessions.begin() as session:
            repo = PolicyRepository(session)
            document = repo.document(source)
            if document is None:
                document = PolicyDocument(source=source, current_version=version)
                session.add(document)
                session.flush()
            elif document.current_version == version:
                return {"source": source, "version": version, "changed": False, "chunks": len(chunks)}
            if not repo.version_exists(document.id, version):
                session.add_all([PolicyChunk(document_id=document.id, version=version, ordinal=index,
                    title=title, section=section, content=content)
                    for index, (title, section, content) in enumerate(chunks, 1)])
            document.current_version = version
        return {"source": source, "version": version, "changed": True, "chunks": len(chunks)}

    def ingest_directory(self, directory: Path) -> list[dict]:
        paths = sorted(directory.glob("*.md"))
        if not paths:
            raise ValueError("no Markdown policy files found")
        # Validate file sizes before reading. No network or arbitrary URL ingestion.
        results = []
        for path in paths:
            if path.is_symlink() or path.stat().st_size > 200000:
                raise ValueError("policy files must be local regular files of at most 200000 bytes")
            results.append(self.ingest(path.name, path.read_text(encoding="utf-8")))
        return results

    def search(self, query: str, limit: int = 4) -> dict:
        if not query.strip() or len(query) > 1000 or not 1 <= limit <= 4:
            raise ValueError("policy query or limit is invalid")
        terms = _terms(query)[:24]
        if not terms:
            return {"matches": [], "message": "No matching policy source was found."}
        with self._sessions() as session:
            candidates = PolicyRepository(session).candidates(terms)
            scored = []
            for chunk, source in candidates:
                words = set(_terms(chunk.title + " " + chunk.section + " " + chunk.content))
                score = len(words.intersection(terms))
                if score:
                    scored.append((score, chunk, source))
            scored.sort(key=lambda item: (-item[0], item[1].id))
            matches = [{"citation_id": f"policy:{chunk.document_id}:{chunk.version[:12]}:{chunk.ordinal}",
                        "source": source, "title": chunk.title, "section": chunk.section,
                        "version": chunk.version, "excerpt": chunk.content}
                       for _, chunk, source in scored[:limit]]
            return {"matches": matches, "message": "Policy excerpts retrieved." if matches else "No matching policy source was found."}
