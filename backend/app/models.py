from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    courses = relationship("Course", back_populates="user", cascade="all, delete-orphan")


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_user_course_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    term: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user = relationship("User", back_populates="courses")
    documents = relationship("Document", back_populates="course", cascade="all, delete-orphan")
    processing_jobs = relationship("ProcessingJob", back_populates="course", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    material_type: Mapped[str] = mapped_column(String(40), default="other", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="queued", nullable=False, index=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    topic_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    course = relationship("Course", back_populates="documents")
    processing_jobs = relationship("ProcessingJob", back_populates="document", cascade="all, delete-orphan")
    parent_chunks = relationship("ParentChunk", back_populates="document", cascade="all, delete-orphan")
    child_chunks = relationship("ChildChunk", back_populates="document", cascade="all, delete-orphan")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="queued", nullable=False, index=True)
    current_step: Mapped[str] = mapped_column(String(40), default="upload", nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    steps_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    course = relationship("Course", back_populates="processing_jobs")
    document = relationship("Document", back_populates="processing_jobs")


class ParentChunk(Base):
    __tablename__ = "parent_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    material_type: Mapped[str] = mapped_column(String(40), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    root_chunk_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    chunk_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    document = relationship("Document", back_populates="parent_chunks")
    children = relationship("ChildChunk", back_populates="parent_chunk", cascade="all, delete-orphan")


class ChildChunk(Base):
    __tablename__ = "child_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_chunk_id: Mapped[int] = mapped_column(
        ForeignKey("parent_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    material_type: Mapped[str] = mapped_column(String(40), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    chunk_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    root_chunk_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    chunk_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    document = relationship("Document", back_populates="child_chunks")
    parent_chunk = relationship("ParentChunk", back_populates="children")
