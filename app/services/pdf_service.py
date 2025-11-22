# services/pdf_service.py
import io
import re
import json
import time
from PIL import Image
from collections import Counter
import unicodedata
import logging
import pymupdf
import pymupdf.layout
import pymupdf4llm
from utils.translator import batch_translate, BATCH_SIZE, SLEEP_BETWEEN_REQUESTS


logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)

def insert_figure(orig_doc, data, output_pdf_buffer):
    new_doc = pymupdf.open()

    for page_ix, page_data in enumerate(data["pages"]):
        pdf_width, pdf_height = page_data["width"], page_data["height"]
        new_page = new_doc.new_page(width=pdf_width, height=pdf_height)

        orig_page = orig_doc[page_ix]
        
        zoom = 2.0
        mat = pymupdf.Matrix(zoom, zoom)
        pix_full = orig_page.get_pixmap(matrix=mat)

        img = Image.open(io.BytesIO(pix_full.tobytes("png")))
        image_width, image_height = img.size

        for box in page_data["boxes"]:
            boxclass = box["boxclass"]
            if boxclass not in ["picture", "formula", "table"]:
                continue

            pdf_x0, pdf_y0, pdf_x1, pdf_y1 = box["x0"], box["y0"], box["x1"], box["y1"]

            img_x0 = int(image_width  * (pdf_x0 / pdf_width))
            img_y0 = int(image_height * (pdf_y0 / pdf_height))
            img_x1 = int(image_width  * (pdf_x1 / pdf_width))
            img_y1 = int(image_height * (pdf_y1 / pdf_height))

            cropped_img = img.crop((img_x0, img_y0, img_x1, img_y1))

            img_byte_arr = io.BytesIO()
            cropped_img.save(img_byte_arr, format="PNG")

            rect_pdf = pymupdf.Rect(pdf_x0, pdf_y0, pdf_x1, pdf_y1)
            new_page.insert_image(rect_pdf, stream=img_byte_arr.getvalue())

    new_doc.save(output_pdf_buffer)
    new_doc.close()


def padding_box(data, padding_small=2.5, padding_large=3):
    for page_ix, page_data in enumerate(data["pages"]):
        for box_ix, box in enumerate(page_data["boxes"]):
            boxclass = box["boxclass"]
            
            if boxclass in ["title", "section-header", "caption", "page-header", "page-footer"]:
                data["pages"][page_ix]["boxes"][box_ix]["y0"] -= padding_large
                data["pages"][page_ix]["boxes"][box_ix]["y1"] += padding_large
            elif boxclass in ["text", "list-item"]:
                data["pages"][page_ix]["boxes"][box_ix]["y0"] -= padding_small
                data["pages"][page_ix]["boxes"][box_ix]["y1"] += padding_small
    
    return data

def consolidate_box_text(box):
    consolidated_lines = []
    colors = []

    for text_line in box.get("textlines", []):
        line_text_parts = []
        
        for span in text_line.get("spans", []):
            raw_text = span.get("text", "")
            color = span.get("color", 0)
            colors.append(color)

            # 1. Loại bỏ ký tự control, non-printable (trừ space, tab, newline)
            text = ''.join(ch for ch in raw_text if unicodedata.category(ch)[0] != 'C' or ch in ' \t\n\r')

            # 2. Thay thế các ký tự "dấu thanh riêng lẻ" thường gặp do lỗi font
            #    (cực hay gặp: ̂  ́  ̀  ̉  ̃  ̣  ̆  ̛)
            text = text.replace('\u02C6', '')   # ^
            text = text.replace('\u005E', '')   # ^ (ASCII)
            text = text.replace('\u0302', '')   # combining circumflex
            text = text.replace('\u0309', '')   # combining hook above (dấu hỏi)
            text = text.replace('\u0306', '')   # combining breve (dấu trăng)
            text = text.replace('\u0301', '')   # acute
            text = text.replace('\u0300', '')   # grave
            text = text.replace('\u0303', '')   # tilde
            text = text.replace('\u0309', '')   # hook above
            text = text.replace('\u0323', '')   # dot below

            # 3. Xóa các dấu cách thừa liên tiếp (do dấu bị tách thành ký tự riêng)
            text = re.sub(r'\s{2,}', ' ', text)

            # 4. Chuẩn hóa Unicode NFC (kết hợp lại dấu nếu có thể)
            text = unicodedata.normalize('NFC', text)

            # 5. Loại bỏ ký tự vô nghĩa lặp lại quá nhiều lần (ví dụ ̂ ̂ ̂ ̂)
            #    Nếu một ký tự không phải chữ cái/số xuất hiện > 4 lần liên tiếp → xóa
            text = re.sub(r'([^a-zA-Z0-9\u00C0-\u1FFF\u2000-\u206F])\1{3,}', '', text)

            # 6. Cuối cùng strip và thêm vào line
            cleaned = text.strip()
            if cleaned:
                line_text_parts.append(cleaned)

        if line_text_parts:
            consolidated_lines.append(" ".join(line_text_parts))

    # Ghép các dòng lại thành đoạn văn (giữ ngắt dòng hợp lý)
    consolidated_box_text = " ".join(consolidated_lines).strip()

    # Lấy màu chủ đạo
    color = Counter(colors).most_common(1)[0][0] if colors else 0
    r = (color >> 16) & 255
    g = (color >> 8) & 255
    b = color & 255
    color_rgb = (r / 255, g / 255, b / 255)

    return {
        "rect": (box["x0"], box["y0"], box["x1"], box["y1"]),
        "box_text": consolidated_box_text,
        "color": color_rgb
    }

def simulate_text_height(text, rect, font, fontsize):
    """
    Simulate the actual height required for the text by splitting into words and estimating wrapped lines.
    This is more accurate than simple length division as it accounts for word wrapping.
    """
    if not text.strip():
        return 0

    x0, _, x1, _ = rect
    rect_width = abs(x1 - x0)
    if rect_width <= 0:
        return 0

    words = text.split()
    lines = []
    current_line = []
    current_length = 0
    space_length = font.text_length(" ", fontsize=fontsize)

    for word in words:
        word_length = font.text_length(word, fontsize=fontsize)
        if current_length + word_length + (space_length if current_line else 0) <= rect_width:
            current_line.append(word)
            current_length += word_length + (space_length if len(current_line) > 1 else 0)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
            current_length = word_length

    if current_line:
        lines.append(" ".join(current_line))

    line_height = (font.ascender - font.descender) * fontsize * 1.2  # Add some line spacing
    total_height = len(lines) * line_height

    return total_height


def estimate_fontsize_for_box_text(text, rect, font_name, font_file_path, boxclass,
                                  min_fontsize=4, max_fontsize=20, epochs=30,
                                  tolerance=0.01):
    if not text or not text.strip():
        return min_fontsize

    font = pymupdf.Font(fontname=font_name, fontfile=font_file_path)
    x0, y0, x1, y1 = rect
    rect_width = abs(x1 - x0)
    rect_height = abs(y1 - y0) * 1.05

    if rect_width <= 0 or rect_height <= 0:
        return min_fontsize

    low = min_fontsize
    high = max_fontsize
    fit_fontsize = min_fontsize

    # Adjust max_fontsize based on boxclass for better initial range
    if boxclass in ["title", "section-header"]:
        high = max_fontsize * 1.2
    elif boxclass in ["text", "list-item"]:
        high = max_fontsize * 0.8

    for _ in range(epochs):
        mid = (low + high) / 2
        estimated_height = simulate_text_height(text, rect, font, mid)

        if estimated_height <= rect_height:
            fit_fontsize = mid
            low = mid + tolerance
        else:
            high = mid - tolerance

        if abs(high - low) < tolerance:
            break
    
    fit_fontsize = max(min_fontsize, min(max_fontsize, fit_fontsize))
    return fit_fontsize

def insert_text(
    data,
    input_pdf_bytes,
    output_pdf_buffer,
    font_metadata,
    source_lang_code: str = "en",
    target_lang_code: str = "vi"
):
    data = padding_box(data, padding_small=2.5, padding_large=3)

    if isinstance(input_pdf_bytes, bytes):
        doc = pymupdf.open(stream=input_pdf_bytes, filetype="pdf")
    elif isinstance(input_pdf_bytes, io.BytesIO):
        doc = pymupdf.open(stream=input_pdf_bytes.getvalue(), filetype="pdf")
    else:
        doc = pymupdf.open(input_pdf_bytes)

    # Gom tất cả box cần dịch
    boxes_to_translate = []

    for page_ix, page_data in enumerate(data["pages"]):
        page = doc[page_ix]
        page.insert_font(fontname=font_metadata["regular_font_name"], fontfile=font_metadata["regular_font_file_path"])
        page.insert_font(fontname=font_metadata["bold_font_name"], fontfile=font_metadata["bold_font_file_path"])

        for box in page_data["boxes"]:
            if box["boxclass"] in ["picture", "formula", "table"]:
                continue

            box_info = consolidate_box_text(box)
            text = box_info["box_text"].strip()
            if not text:
                continue

            boxes_to_translate.append({
                "page": page,
                "rect": pymupdf.Rect(box_info["rect"]),
                "text": text,
                "color": box_info["color"],
                "boxclass": box["boxclass"]
            })

    total_boxes = len(boxes_to_translate)
    if total_boxes == 0:
        doc.save(output_pdf_buffer)
        doc.close()
        return

    logger.info(f"Number of boxes in pdf: {total_boxes} box \n\t→ {((total_boxes - 1) // BATCH_SIZE) + 1} batch")

    all_translated = []

    # Dịch theo batch → truyền ngôn ngữ
    for i in range(0, total_boxes, BATCH_SIZE):
        batch = boxes_to_translate[i:i + BATCH_SIZE]
        batch_texts = [item["text"] for item in batch]

        logger.info(f"  → Translating batch {i // BATCH_SIZE + 1} ({len(batch)} box) | {source_lang_code} → {target_lang_code}...")
        
        batch_translated = batch_translate(
            batch_texts,
            source_lang_code=source_lang_code,
            target_lang_code=target_lang_code
        )
        all_translated.extend(batch_translated)

        if i + BATCH_SIZE < total_boxes:
            logger.info(f"    Sleep {SLEEP_BETWEEN_REQUESTS} seconds...")
            time.sleep(SLEEP_BETWEEN_REQUESTS)

    logger.info("Successfully translate all batch text!")

    # Insert từng text đã dịch
    for item, translated_text in zip(boxes_to_translate, all_translated):
        page = item["page"]
        rect = item["rect"]
        color = item["color"]
        boxclass = item["boxclass"]

        fontname = font_metadata["bold_font_name"] if boxclass in ["title", "section-header"] else font_metadata["regular_font_name"]

        fontsize = estimate_fontsize_for_box_text(
            text=translated_text,
            rect=rect,
            font_name=font_metadata["regular_font_name"],
            font_file_path=font_metadata["regular_font_file_path"],
            boxclass=boxclass,
            min_fontsize=4,
            max_fontsize=28,
            epochs=30,
            tolerance=0.005
        )

        max_attempts = 100
        attempt = 0
        success = False

        while attempt < max_attempts and not success:
            try:
                result = page.insert_textbox(
                    rect=rect,
                    buffer=translated_text,
                    fontsize=fontsize,
                    fontname=fontname,
                    color=color,
                    align=pymupdf.TEXT_ALIGN_JUSTIFY,
                    overlay=True
                )

                if result >= 0:
                    success = True
                else:
                    fontsize *= 0.996
                    attempt += 1

            except Exception as e:
                logger.warning(f"Error inserting textbox at page {page_ix+1}: {e}")
                fontsize *= 0.99
                attempt += 1

    doc.save(output_pdf_buffer)
    doc.close()
    logger.info(f"Successfully translating PDF file!")

def process_pdf_bytes(
    pdf_bytes: bytes,
    font_metadata: dict,
    source_lang_code: str = "en",
    target_lang_code: str = "vi"
) -> bytes:
    # Load PDF gốc
    orig_doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

    # Detect layout with improved quality: higher DPI for better image/formula detection
    json_text = pymupdf4llm.to_json(
        orig_doc,
        image_dpi=300,
        image_format="png",
        image_path=""
    )
    data = json.loads(json_text)

    # Tạo PDF figure-only
    fig_output_buffer = io.BytesIO()
    insert_figure(orig_doc=orig_doc, data=data, output_pdf_buffer=fig_output_buffer)
    fig_pdf_bytes = fig_output_buffer.getvalue()

    # Chèn text vào PDF figure
    final_output_buffer = io.BytesIO()
    insert_text(
        data=data,
        input_pdf_bytes=fig_pdf_bytes,
        output_pdf_buffer=final_output_buffer,
        font_metadata=font_metadata,
        source_lang_code=source_lang_code,
        target_lang_code=target_lang_code
    )

    return final_output_buffer.getvalue()