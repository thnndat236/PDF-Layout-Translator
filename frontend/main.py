import os
import time
import requests
import tempfile
import gradio as gr
from gradio_pdf import PDF

from font_config import FONT_CHOICES
from language_config import LANGUAGE_CHOICES

API_BASE_URL = "http://127.0.0.1:30000/api/pdf"
TRANSLATE_ENDPOINT = f"{API_BASE_URL}/translate"
TASK_STATUS_ENDPOINT = f"{API_BASE_URL}/task"


def submit_and_poll(pdf_file, source_lang, target_lang, font_style):
    if pdf_file is None:
        yield None, "Vui lòng upload file PDF!", None, gr.update(visible=False)
        return

    start_time = time.time()
    history = []

    def add(msg):
        ts = time.strftime("%H:%M:%S")
        history.append(f"[{ts}] {msg}")
        return "\n".join(history[-15:])

    with open(pdf_file, "rb") as f:
        files = {"file": ("input.pdf", f, "application/pdf")}
        data = {
            "source_lang": source_lang,
            "target_lang": target_lang,
            "font_style": font_style
        }

        try:
            resp = requests.post(TRANSLATE_ENDPOINT, files=files, data=data, timeout=60)
            resp.raise_for_status()
            task_id = resp.json().get("task_id")
            if not task_id:
                yield None, add("Không nhận được task_id"), None, gr.update(visible=False)
                return

            yield None, add(f"Task đã gửi! ID: {task_id}"), None, gr.update(visible=False)

            while True:
                time.sleep(1.5)
                try:
                    r = requests.get(f"{TASK_STATUS_ENDPOINT}/{task_id}", timeout=30)

                    if "application/json" in r.headers.get("Content-Type", ""):
                        data = r.json()
                        status = data.get("status", "unknown")
                        elapsed = int(time.time() - start_time)

                        if status == "queued":
                            msg = f"Đang xếp hàng... chờ worker ({elapsed}s)"
                        elif status == "start":
                            msg = f"Đang dịch PDF... đã xử lý {elapsed}s"
                        else:
                            msg = f"Trạng thái: {status}"

                        yield None, add(msg), None, gr.update(visible=False)

                    else:
                        temp_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf").name
                        with open(temp_path, "wb") as f:
                            f.write(r.content)

                        total_time = time.time() - start_time
                        final_msg = add(f"Hoàn tất! Đã dịch xong trong {total_time:.1f}s")

                        yield None, final_msg, gr.update(visible=True, value=temp_path), gr.update(visible=True, value=temp_path)

                        return

                except Exception as e:
                    yield None, add(f"Lỗi: {e}"), None, gr.update(visible=False)
                    time.sleep(5)

        except Exception as e:
            yield None, add(f"Lỗi gửi file: {e}"), None, gr.update(visible=False)


with gr.Blocks(title="PDF Layout Translator", theme=gr.themes.Ocean(), css="footer {visibility: hidden}") as demo:
    gr.HTML("""
    <div style="text-align:center; padding: 15px 0; background: linear-gradient(135deg, #3bbff4 0%, #6ee7b7 100%); border-radius: 20px; color: white; margin-bottom: 20px;">
        <h1 style="color:white; margin:0;">PDF Layout Translator</h1>
        <p style="font-size:1.2rem; margin:10px 0 5px;">Dịch tài liệu học thuật giữ nguyên bố cục như bản gốc</p>
        <p style="font-size:1rem; opacity:0.9;">Hỗ trợ dịch đa ngôn ngữ, chọn font đẹp</p>
    </div>
    """)

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 1. Upload PDF & Cài đặt")
            pdf_input = PDF(label="Kéo thả hoặc chọn file PDF")

            with gr.Row():
                source_lang = gr.Dropdown(LANGUAGE_CHOICES, value="English", label="Ngôn ngữ nguồn")
                target_lang = gr.Dropdown(LANGUAGE_CHOICES, value="Vietnamese", label="Ngôn ngữ đích")

            font_style = gr.Dropdown(FONT_CHOICES, value="Noto Sans", label="Kiểu chữ")

            submit_btn = gr.Button("Dịch PDF Ngay", variant="primary", size="lg")

        with gr.Column(scale=1):
            
            gr.Markdown("### 2. Theo dõi tiến trình")
            status_box = gr.Textbox(
                label="Realtime Log",
                lines=12,
                interactive=False,
                container=True,
                elem_classes="monospace"
            )

            gr.Markdown("### 3. Kết quả")
            
            pdf_preview = PDF(
                label="Preview PDF đã dịch",
                visible=False
            )

            download_file = gr.File(
                label="Tải file PDF đã dịch",
                file_types=[".pdf"],
                visible=False
            )

    submit_btn.click(
        fn=submit_and_poll,
        inputs=[pdf_input, source_lang, target_lang, font_style],
        outputs=[status_box, status_box, pdf_preview, download_file]
    )

    with gr.Row():
        gr.HTML("""
        <div style="padding: 5px; border-radius: 20px; text-align: center;">
            <p><a href="https://github.com/thnndat236/PDF-Layout-Translator" target="_blank" style="text-decoration: underline;">GitHub Repository</a></p>
            <p style="margin-top: 5px; font-size: 0.9rem; opacity: 0.9;">
                Made by Le Thanh Dat • 2025
            </p>
        </div>
        """)
            
if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        favicon_path="assets/favicon.ico"
    )