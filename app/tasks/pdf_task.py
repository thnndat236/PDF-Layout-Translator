# app/tasks/pdf_task.py
import base64
from celery_app import celery_app
from services.pdf_service import process_pdf_bytes


@celery_app.task(bind=True, name="pdf.translate")
def translate_pdf_task(
    self,
    pdf_bytes_base64: str,
    font_metadata: dict,
    source_code: str,
    target_code: str,
):
    pdf_bytes = base64.b64decode(pdf_bytes_base64)

    result_bytes = process_pdf_bytes(
        pdf_bytes=pdf_bytes,
        font_metadata=font_metadata,
        source_lang_code=source_code,
        target_lang_code=target_code,
    )
    return base64.b64encode(result_bytes).decode()