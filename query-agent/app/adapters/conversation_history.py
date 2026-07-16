from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True)
    username = Column(String)
    created_at = Column(DateTime(timezone=True))


class MessageRow(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("sessions.id"))
    sender = Column(String)
    text = Column(Text)
    intent = Column(String)
    citations = Column(JSONB)
    tokens_used = Column(Integer)
    created_at = Column(DateTime(timezone=True))


class ConversationHistoryManager:
    def __init__(self, database_url: str) -> None:
        self._engine = create_engine(database_url)
        self._session_factory = sessionmaker(self._engine, expire_on_commit=False)

    def create_session(self, username: str | None = None) -> str:
        session_id = str(uuid.uuid4())
        with self._session_factory() as session:
            session.add(
                SessionRow(
                    id=session_id,
                    username=username,
                    created_at=datetime.now(timezone.utc),
                )
            )
            session.commit()
        return session_id

    def save_message(
        self,
        session_id: str,
        sender: str,
        text: str,
        intent: str | None = None,
        citations: list | None = None,
        tokens_used: int = 0,
    ) -> None:
        with self._session_factory() as session:
            session.add(
                MessageRow(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    sender=sender,
                    text=text,
                    intent=intent,
                    citations=citations,
                    tokens_used=tokens_used,
                    created_at=datetime.now(timezone.utc),
                )
            )
            session.commit()

    def get_memory_context(self, session_id: str, n: int = 5) -> str:
        with self._session_factory() as session:
            stmt = (
                select(MessageRow)
                .where(MessageRow.session_id == session_id)
                .order_by(MessageRow.created_at.desc())
                .limit(n * 2)
            )
            rows = list(reversed(session.scalars(stmt).all()))
        lines = [f"{r.sender}: {r.text}" for r in rows]
        return "\n".join(lines)
