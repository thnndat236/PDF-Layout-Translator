# routers/pdf_router.py
import io
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from services.pdf_service import process_pdf_bytes
from configs.font_config import FONT_PRESETS
from configs.language_config import NAME_TO_CODE


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

    # Call service with font and languages to get translated-pdf
    output_pdf_bytes = process_pdf_bytes(
        pdf_bytes=pdf_bytes,
        font_metadata=font_metadata,
        source_lang_code=source_code,
        target_lang_code=target_code
    )

    return StreamingResponse(
        io.BytesIO(output_pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=translated_{source_code}2{target_code}.pdf"
        }
    )