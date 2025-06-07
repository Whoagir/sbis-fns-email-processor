from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from app.database import Base


class MailDocument(Base):
    __tablename__ = "mail_documents"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String, unique=True, index=True)  # ID из СБИС
    date = Column(DateTime, nullable=False)
    subject = Column(Text, nullable=False)
    sender_inn = Column(String(12), nullable=True, index=True)
    sender_name = Column(String(500), nullable=True)
    filename = Column(String(255), nullable=True)
    has_attachment = Column(Boolean, default=False)
    is_from_fns = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ProcessingLog(Base):
    __tablename__ = "processing_logs"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, nullable=True)
    total_documents = Column(Integer, default=0)
    fns_documents = Column(Integer, default=0)
    status = Column(String(50), default="success")  # success, error
    error_message = Column(Text, nullable=True)
    processed_at = Column(DateTime, server_default=func.now())