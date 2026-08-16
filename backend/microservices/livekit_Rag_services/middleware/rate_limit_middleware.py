from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from backend.microservices.livekit_Rag_services.core.redis import RedisServices


redis_service = RedisServices()
import logging

logger = logging.getLogger(__name__)



class RateLimitMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):

        ip_address = request.client.host

        count = await redis_service.rate_limit(ip_address)
       
        logger.info(f"counts = {count}")
        response = await call_next(request)

        return response