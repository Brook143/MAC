import redis
import json
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(self, host='127.0.0.1', port=6379, password=None, db=0):
        self._connected = False
        self._connect_error = None
        try:
            self.client = redis.Redis(
                host=host,
                port=port,
                password=password,
                db=db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            self.client.ping()
            self._connected = True
            logger.info(f"Redis 连接成功: {host}:{port}")
        except Exception as e:
            self._connected = False
            self._connect_error = str(e)
            logger.warning(f"Redis 连接失败 ({host}:{port}): {e}，将使用降级模式")
    
    @property
    def connected(self):
        return self._connected
    
    def get(self, key):
        if not self._connected:
            return None
        try:
            data = self.client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.warning(f"Redis GET 失败 [{key}]: {e}")
            return None
    
    def set(self, key, value, ttl=5):
        if not self._connected:
            return False
        if isinstance(ttl, timedelta):
            ttl = int(ttl.total_seconds())
        try:
            self.client.set(key, json.dumps(value), ex=ttl)
            return True
        except Exception as e:
            logger.warning(f"Redis SET 失败 [{key}]: {e}")
            return False
    
    def delete(self, key):
        if not self._connected:
            return 0
        try:
            return self.client.delete(key)
        except Exception as e:
            logger.warning(f"Redis DELETE 失败 [{key}]: {e}")
            return 0
    
    def hset(self, key, mapping=None, **kwargs):
        if not self._connected:
            return 0
        try:
            return self.client.hset(key, mapping=mapping, **kwargs)
        except Exception as e:
            logger.warning(f"Redis HSET 失败 [{key}]: {e}")
            return 0
    
    def hgetall(self, key):
        if not self._connected:
            return {}
        try:
            return self.client.hgetall(key)
        except Exception as e:
            logger.warning(f"Redis HGETALL 失败 [{key}]: {e}")
            return {}
    
    def expire(self, key, time):
        if not self._connected:
            return False
        try:
            return self.client.expire(key, time)
        except Exception as e:
            logger.warning(f"Redis EXPIRE 失败 [{key}]: {e}")
            return False
    
    def pipeline(self, transaction=True):
        if not self._connected:
            return None
        return self.client.pipeline(transaction=transaction)