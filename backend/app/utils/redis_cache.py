# app/utils/redis_cache.py
import hashlib
import json
import logging
from functools import wraps
from typing import Callable, Any
from redis import Redis
import os
from dotenv import load_dotenv


load_dotenv()

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)


redis_client = Redis.from_url(
    url=os.getenv("REDIS_URL", "redis://localhost:6379/1"),
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5
)

CACHE_TTL = 60 * 60 * 24 * 7  # 7 ngày (có thể config qua env)

def cache_by_checksum(ttl: int = CACHE_TTL, namespace: str = "pdf_layout") -> Callable:
    """
    Decorator để cache kết quả function dựa trên checksum của input bytes (pdf_bytes).
    
    - Áp dụng cho function nhận pdf_bytes làm arg đầu tiên.
    - Cache dict/JSON (như layout data từ pymupdf4llm).
    - Key: f"{namespace}:{checksum}"
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            pdf_bytes = kwargs.get("pdf_bytes")
            if pdf_bytes is None:
                if not args or not isinstance(args[0], bytes):
                    raise ValueError("Function have to receive pdf_bytes as the first argument")
                pdf_bytes = args[0]
            elif not isinstance(pdf_bytes, bytes):
                raise ValueError("pdf_bytes must be bytes")
                
            # Calculate checksum of pdf_bytes
            checksum = hashlib.md5(pdf_bytes).hexdigest() 
            cache_key = f"{namespace}:{checksum}"

            logger.info(f"Checking cache for key: {cache_key}")

            # Cache hit: Get layout data from Redis
            cached_data = redis_client.get(cache_key)
            if cached_data:
                try:
                    result = json.loads(cached_data)
                    logger.info(f"Cache hit for {cache_key} – Skipping expensive computation")
                    return result
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid cached data for {cache_key}: {e}")

            # Cache miss: Run the detect layout function
            logger.info(f"Cache miss for {cache_key} – Running {func.__name__}")
            result = func(*args, **kwargs)

            # Save to cache (if result is dict/JSON serializable)
            if isinstance(result, dict):
                try:
                    redis_client.setex(cache_key, ttl, json.dumps(result, ensure_ascii=False))
                    logger.info(f"Cached result for {cache_key} (TTL: {ttl}s)")
                except Exception as e:
                    logger.warning(f"Failed to cache result: {e}")
            else:
                logger.warning(f"Result not serializable (not dict) – No cache")

            return result

        return wrapper
    return decorator