import logging
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request : Request , callnext):
        start_time = time.perf_counter()

        logger.info(f"Incomming request {request.method} , {request.url.path}")

        response = await callnext(request)

        duration = time.perf_counter() - start_time

        logger.info(
            f"Completed {response.status_code} "
            f"in {duration:.4f}s"
        )

        return response
