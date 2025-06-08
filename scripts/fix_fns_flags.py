import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.models import MailDocument
from app.services.fns_filter import FNSFilterService


def recalculate_fns_flags():
    db = SessionLocal()
    try:
        documents = db.query(MailDocument).all()
        for doc in documents:
            doc_data = {
                "sender_inn": doc.sender_inn,
                "subject": doc.subject
            }
            new_flag = FNSFilterService.is_from_fns(doc_data)
            if doc.is_from_fns != new_flag:
                print(f"Updating {doc.id}: {doc.is_from_fns} -> {new_flag}")
                doc.is_from_fns = new_flag

        db.commit()
        print("Flags updated successfully!")
    finally:
        db.close()


if __name__ == "__main__":
    recalculate_fns_flags()