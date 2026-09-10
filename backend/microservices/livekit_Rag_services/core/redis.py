import logging
import os

import redis.asyncio as redis
from fastapi import HTTPException, status
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class RedisServices:
    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        decode_responses: bool = True,
    ):
        # Host/port come from the env so they do not clash with a
        # local Redis install. The default is the old localhost:6379.
        host = host or os.getenv("REDIS_HOST", "localhost")
        port = int(port or os.getenv("REDIS_PORT", 6379))

        self.redis_client = Redis(
            host=host,
            port=port,
            decode_responses=decode_responses,
        )

    async def set_str_data(self, key: str, value: str, expire: int = 120):
        """Store string data in Redis."""

        try:
            await self.redis_client.set(key, value, ex=expire)

            return {
                "key": key,
                "value": value,
                "expire": expire,
            }

        except redis.RedisError as e:
            logger.error(f"Redis SET Error: {e}")
            return None

    async def get_str_data(self, key: str):
        """Get string data from Redis."""

        try:
            value = await self.redis_client.get(key)

            if value is None:
                return None

            return value

        except redis.RedisError as e:
            logger.error(f"Redis GET Error: {e}")
            return None
    
    async def rate_limit(
        self,
        ip_address: str,
        limit: int = 5,
        window: int = 60,
    ):
        """
        Fixed Window Rate Limiter

        limit  = maximum requests
        window = seconds
        """

        # try:
        key = f"rate_limit:{ip_address}"

        # Increment request count atomically
        count = await self.redis_client.incr(key)

        # Set expiry only when key is created
        if count == 1:
            await self.redis_client.expire(key, window)

        ttl = await self.redis_client.ttl(key)

        # if count > limit:
        #     raise HTTPException(
        #         status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        #         detail=f"Too many requests. Try again in {ttl} seconds.",
        #     )

        return count

        # except redis.RedisError as e:
        #     logger.error(f"Redis Rate Limit Error: {e}")
        #     raise HTTPException(
        #         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        #         detail="Redis server unavailable",
        #     )

    async def close(self):
        """Close Redis connection."""

        await self.redis_client.close()
