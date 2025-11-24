# utils/translator.py
import os
import json
import time
import re
import logging
from deep_translator import GoogleTranslator
from openai import OpenAI
from dotenv import load_dotenv
from configs.language_config import CODE_TO_NAME


logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = OpenAI(
    api_key=GROQ_API_KEY, 
    base_url="https://api.groq.com/openai/v1",
)

BATCH_SIZE = 8
SLEEP_BETWEEN_REQUESTS = 5

BATCH_PROMPT = """You are an expert technical translator and text reconstructor for academic PDFs. You translate content from {source_language} into {target_language} with strict structure and formatting rules. Your task is to process multiple input segments and output a SINGLE JSON object.

CRITICAL RULES - FOLLOW EXACTLY:

1. OUTPUT FORMAT (CRITICAL)
    - Output ONLY a valid JSON object.
    - The JSON MUST HAVE EXACTLY:
        {{
          "translations": ["...", "...", ...]
        }}
    - The array MUST contain exactly {count} translated strings.
    - Keep the order exactly identical to the input.
    - NO explanations, NO comments, NO markdown, NO code blocks, NO introductory text.

2. TEXT RECONSTRUCTION (Mandatory BEFORE translation)
    - Fix broken words from PDF extraction.
        Examples:
            "A ttention" → "Attention"
            "Trans former" → "Transformer"
            "sim ilar ity" → "similarity"
            "d _ k" → "d_k"
    - Remove PDF artifacts like random characters, mis-extracted spacing, page numbers.
    - Merge fragmented math expressions while preserving meaning.

3. TERMINOLOGY & TECHNICAL NO-TRANSLATE RULES
    - DO NOT translate technical terms, proper nouns, model names, library names, function names, method names, or section headers representing a concept.
    - If a word is capitalized in the middle of a sentence and looks like a concept or name, KEEP IT IN ORIGINAL ENGLISH.
    - Strictly avoid formats like “Term (Translated)” or “Translated (Term)”.
        WRONG:  "Biến đổi (Transformers)"
        RIGHT:  "Transformers"
    - Never add explanations for terms.

4. MATH CLEANING (Extremely Strict)
    - Convert garbled PDF math into clean linear text.
    - NO LaTeX, NO $...$, NO \frac, \sqrt.
    - Allowed formatting:
        - "/" for division
        - "^" for exponent
        - "_" for subscripts
        - Remove spaces inside variables: | t 1 | → |t1|
    - Example:
        Input: "sim ilar ity = (t 1 . t 2) / | t 1 | | t2|"
        Output: "similarity = (t1 . t2) / |t1||t2|"

5. TRANSLATION RULES
    - Translate to {target_language} with natural, concise, professional academic style.
    - Preserve math exactly.
    - Preserve technical terms exactly.
    - Preserve URLs, emails, bullet structure if present.
    - No rewriting style; keep structure but improve clarity.

INPUT FORMAT

The input consists of multiple text segments, separated by ===SEGMENT===:

{texts}

OUTPUT FORMAT (MANDATORY)

Output ONLY this JSON object and nothing else:

{{
  "translations": ["translated text 1", "translated text 2", ...]
}}
Ensure the array has exactly {count} items in the same order.
"""

def batch_translate(texts: list[str], source_lang_code: str, target_lang_code: str) -> list[str]:
    if not texts:
        return []

    count = len(texts)
    separator = "\n===SEGMENT===\n"
    combined = separator.join(texts)

    source_language = CODE_TO_NAME[source_lang_code]
    target_language = CODE_TO_NAME[target_lang_code]

    final_prompt = BATCH_PROMPT.format(
        count=count,
        texts=combined,
        source_language=source_language,
        target_language=target_language  
    )

    try:
        response = groq_client.chat.completions.create(
            model="qwen/qwen3-32b",
            messages=[{"role": "user", "content": final_prompt}],
            temperature=0.3,
            max_tokens=8192,
            reasoning_effort="none",
            response_format={"type": "json_object"},
            stream=False
        )

        content = response.choices[0].message.content.strip()

        # Parse JSON to get translated batch
        try:
            data = json.loads(content)
            translations = data.get("translations", [])
            if len(translations) == count:
                return translations
        except:
            pass

        # Fallback parse
        try:
            start = content.find('{')
            end = content.rfind('}')

            if start != -1 and end != -1 and start < end:
                json_string = content[start:end+1]
                data = json.loads(s=json_string)
                translations = data.get("translations", [])
                
                if len(translations) == count:
                    return translations

            logger.warning(f"[GROQ] Failed to parse clean JSON. Raw content: {content[:100]}...\t. Fallback Google")
            return [GoogleTranslator(source=source_lang_code, target=target_lang_code).translate(t) for t in texts]
        except Exception as e:
            logger.warning(f"[GROQ] JSON loading failed: {e}. Raw content: {content[:100]}...")
            pass

    except Exception as e:
        logger.warning(f"[GROQ] {e}\t. Fallback Google")
        return [GoogleTranslator(source=source_lang_code, target=target_lang_code).translate(t) for t in texts]
