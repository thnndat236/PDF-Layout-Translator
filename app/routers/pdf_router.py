# app/routers/pdf_router.py
import io
import base64
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from services.pdf_service import process_pdf_bytes
from configs.font_config import FONT_PRESETS
from configs.language_config import NAME_TO_CODE
from tasks.pdf_task import translate_pdf_task


router = APIRouter()

@router.post("/translate")
async def translate_pdf(
    file: UploadFile = File(...),
    source_lang: str = Form("English"),
    target_lang: str = Form("Vietnamese"),
    font_style: str = Form("Noto Sans")
):
    if file.content_type != "application/pdf":
        return {"error": "File must be a PDF"}

    # Validate language
    source_code = NAME_TO_CODE.get(source_lang)
    target_code = NAME_TO_CODE.get(target_lang)
    if not source_code or not target_code:
        return {"error": f"Unsupported language: {source_lang} to {target_lang}"}

    # Validate font
    font_metadata = FONT_PRESETS.get(font_style)
    if not font_metadata:
        return {"error": f"Font not found: {font_style}"}

    pdf_bytes = await file.read()
    pdf_b64 = base64.b64encode(pdf_bytes).decode()

    task = translate_pdf_task.delay(
        pdf_b64, font_metadata, source_code, target_code
    )
    return {"task_id": task.id, "status": "queued"}


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    task_result = translate_pdf_task.AsyncResult(task_id)
    if task_result.state == "PENDING":
        response = {"task_id": task_id, "status": "queued"}
    elif task_result.state == "PROGRESS":
        response = {"task_id": task_id, "status": "processing", "info": task_result.info}
    elif task_result.state == "SUCCESS":
        b64_result = task_result.result
        pdf_bytes = base64.b64decode(b64_result)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=translated.pdf"}
        )
    else:  # FAILED, RETRY, etc.
        response = {
            "task_id": task_id,
            "status": task_result.state,
            "error": str(task_result.info)
        }
    return response