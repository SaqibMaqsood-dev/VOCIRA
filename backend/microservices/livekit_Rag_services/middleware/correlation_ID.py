from starlette.middleware.base import BaseHTTPMiddleware
import uuid
from fastapi import Request
import logging
import asyncio
logger = logging.getLogger(__name__)


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request : Request, call_next):   
        
        _cid =request.headers.get("X-Correlation-ID") or  str(uuid.uuid4())
        
        logger.info(f"generated_cid = {_cid}")
        
        request.state.correlation_id = _cid
        
        response = await call_next(request)
        
        response.headers["X-Correlation-ID"] = _cid
        
        return response

