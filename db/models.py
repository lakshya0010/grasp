from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime, timezone


class Base(DeclarativeBase):
    pass


class Repository(Base):
    __tablename__="repositories"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    created_at = Column(String, default= datetime.now(timezone.utc))


class Node(Base):
    __tablename__="nodes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    name = Column(String, nullable=False)
    file_path = Column(String, nullable=True)
    is_external = Column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("name","file_path"),)


class Edge(Base):
    __tablename__="edges"
    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    caller_id = Column(Integer, ForeignKey("nodes.id"), nullable=False)
    callee_id = Column(Integer, ForeignKey("nodes.id"), nullable=False)
    resolved = Column(Boolean, default=True)
    is_external = Column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("caller_id", "callee_id", "repo_id"),)

    