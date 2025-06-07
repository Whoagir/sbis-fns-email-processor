from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class MailDocumentBase(BaseModel):
    external_id: str
    date: datetime
    subject: str
    sender_inn: Optional[str] = None
    sender_name: Optional[str] = None
    filename: Optional[str] = None
    has_attachment: bool = False


class MailDocumentCreate(MailDocumentBase):
    pass


class MailDocument(MailDocumentBase):
    id: int
    is_from_fns: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProcessingResult(BaseModel):
    total_documents: int
    fns_documents: int
    new_documents: int
    processed_at: datetime
    status: str


class ProcessingLogResponse(BaseModel):
    id: int
    task_id: Optional[str]
    total_documents: int
    fns_documents: int
    status: str
    error_message: Optional[str]
    processed_at: datetime

    class Config:
        from_attributes = True