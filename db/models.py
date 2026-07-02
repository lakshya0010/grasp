from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class Node(Base):
    __tablename__="nodes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    file_path = Column(String, nullable=True)
    is_external = Column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("name","file_path"),)


class Edge(Base):
    __tablename__="edges"
    id = Column(Integer, primary_key=True, autoincrement=True)
    caller_id = Column(Integer, ForeignKey("nodes.id"), nullable=False)
    callee_id = Column(Integer, ForeignKey("nodes.id"), nullable=False)
    resolved = Column(Boolean, default=True)
    is_external = Column(Boolean, default=False)

    