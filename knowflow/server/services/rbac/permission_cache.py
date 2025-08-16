#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
权限缓存服务
提供权限计算结果的缓存机制，提高系统性能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from typing import Dict, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import json
import hashlib
import threading
import logging
from models.rbac_models import PermissionType, ResourceType
from .permission_calculator import PermissionResult, PermissionLevel

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    result: PermissionResult
    created_at: datetime
    expires_at: datetime
    access_count: int = 0
    last_accessed: Optional[datetime] = None

class PermissionCache:
    """权限缓存管理器"""
    
    def __init__(self, default_ttl: int = 300, max_size: int = 10000):
        """
        初始化权限缓存
        
        Args:
            default_ttl: 默认缓存时间（秒）
            max_size: 最大缓存条目数
        """
        self.default_ttl = default_ttl
        self.max_size = max_size
        self.cache: Dict[str, CacheEntry] = {}
        self.lock = threading.RLock()
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'total_requests': 0
        }
    
    def _generate_cache_key(self, user_id: str, resource_type: ResourceType, 
                          resource_id: str, permission_type: PermissionType,
                          tenant_id: str = "default") -> str:
        """生成缓存键"""
        key_data = f"{user_id}:{resource_type.name}:{resource_id}:{permission_type.name}:{tenant_id}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, user_id: str, resource_type: ResourceType, 
           resource_id: str, permission_type: PermissionType,
           tenant_id: str = "default") -> Optional[PermissionResult]:
        """从缓存获取权限结果"""
        cache_key = self._generate_cache_key(user_id, resource_type, resource_id, permission_type, tenant_id)
        
        with self.lock:
            self.stats['total_requests'] += 1
            
            entry = self.cache.get(cache_key)
            if entry is None:
                self.stats['misses'] += 1
                return None
            
            # 检查是否过期
            now = datetime.now()
            if now > entry.expires_at:
                del self.cache[cache_key]
                self.stats['misses'] += 1
                return None
            
            # 更新访问统计
            entry.access_count += 1
            entry.last_accessed = now
            self.stats['hits'] += 1
            
            logger.debug(f"缓存命中: {cache_key}")
            return entry.result
    
    def put(self, user_id: str, resource_type: ResourceType, 
           resource_id: str, permission_type: PermissionType,
           result: PermissionResult, tenant_id: str = "default",
           ttl: Optional[int] = None) -> None:
        """将权限结果放入缓存"""
        cache_key = self._generate_cache_key(user_id, resource_type, resource_id, permission_type, tenant_id)
        ttl = ttl or self.default_ttl
        
        with self.lock:
            now = datetime.now()
            expires_at = now + timedelta(seconds=ttl)
            
            entry = CacheEntry(
                key=cache_key,
                result=result,
                created_at=now,
                expires_at=expires_at,
                access_count=0,
                last_accessed=now
            )
            
            # 检查缓存大小限制
            if len(self.cache) >= self.max_size:
                self._evict_entries()
            
            self.cache[cache_key] = entry
            logger.debug(f"缓存存储: {cache_key}, TTL: {ttl}s")
    
    def invalidate_user(self, user_id: str) -> int:
        """使用户相关的所有缓存失效"""
        with self.lock:
            keys_to_remove = []
            for key, entry in self.cache.items():
                # 检查缓存键是否包含用户ID
                if key.startswith(hashlib.md5(user_id.encode()).hexdigest()[:8]):
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self.cache[key]
            
            logger.info(f"用户 {user_id} 相关缓存已失效，共 {len(keys_to_remove)} 条")
            return len(keys_to_remove)
    
    def invalidate_resource(self, resource_type: ResourceType, resource_id: str) -> int:
        """使资源相关的所有缓存失效"""
        with self.lock:
            keys_to_remove = []
            resource_pattern = f":{resource_type.name}:{resource_id}:"
            
            for key, entry in self.cache.items():
                # 重新生成原始键来检查
                if resource_pattern in key:  # 简化的模式匹配
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self.cache[key]
            
            logger.info(f"资源 {resource_type.name}:{resource_id} 相关缓存已失效，共 {len(keys_to_remove)} 条")
            return len(keys_to_remove)
    
    def invalidate_team(self, team_id: str) -> int:
        """使团队相关的所有缓存失效（当团队权限变更时）"""
        # 由于团队权限影响团队成员，需要清除所有相关缓存
        # 这里采用简单策略：清除所有缓存
        with self.lock:
            count = len(self.cache)
            self.cache.clear()
            logger.info(f"团队 {team_id} 权限变更，已清除所有缓存，共 {count} 条")
            return count
    
    def _evict_entries(self, count: int = None) -> None:
        """驱逐缓存条目"""
        if not count:
            count = max(1, len(self.cache) // 10)  # 默认驱逐10%
        
        # 按最少使用和最早创建时间排序
        entries = list(self.cache.items())
        entries.sort(key=lambda x: (x[1].access_count, x[1].created_at))
        
        for i in range(min(count, len(entries))):
            key = entries[i][0]
            del self.cache[key]
            self.stats['evictions'] += 1
        
        logger.debug(f"已驱逐 {count} 个缓存条目")
    
    def clear(self) -> None:
        """清空所有缓存"""
        with self.lock:
            count = len(self.cache)
            self.cache.clear()
            logger.info(f"已清空所有缓存，共 {count} 条")
    
    def get_stats(self) -> Dict[str, any]:
        """获取缓存统计信息"""
        with self.lock:
            total_requests = self.stats['total_requests']
            hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'cache_size': len(self.cache),
                'max_size': self.max_size,
                'hit_rate': f"{hit_rate:.2f}%",
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'evictions': self.stats['evictions'],
                'total_requests': total_requests,
                'default_ttl': self.default_ttl
            }
    
    def cleanup_expired(self) -> int:
        """清理过期的缓存条目"""
        with self.lock:
            now = datetime.now()
            expired_keys = []
            
            for key, entry in self.cache.items():
                if now > entry.expires_at:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.cache[key]
            
            if expired_keys:
                logger.debug(f"已清理 {len(expired_keys)} 个过期缓存条目")
            
            return len(expired_keys)
    
    def get_cache_info(self, limit: int = 10) -> Dict[str, any]:
        """获取缓存详细信息"""
        with self.lock:
            entries_info = []
            
            # 按访问次数排序，获取热点数据
            sorted_entries = sorted(
                self.cache.items(), 
                key=lambda x: x[1].access_count, 
                reverse=True
            )
            
            for key, entry in sorted_entries[:limit]:
                entries_info.append({
                    'key': key,
                    'access_count': entry.access_count,
                    'created_at': entry.created_at.isoformat(),
                    'expires_at': entry.expires_at.isoformat(),
                    'last_accessed': entry.last_accessed.isoformat() if entry.last_accessed else None,
                    'has_permission': entry.result.has_permission,
                    'permission_level': entry.result.permission_level.name
                })
            
            return {
                'stats': self.get_stats(),
                'top_entries': entries_info
            }

class CachedPermissionService:
    """带缓存的权限服务"""
    
    def __init__(self, calculator, cache: PermissionCache = None):
        self.calculator = calculator
        self.cache = cache or PermissionCache()
    
    def check_permission(self, user_id: str, resource_type: ResourceType, 
                        resource_id: str, permission_type: PermissionType,
                        tenant_id: str = "default", use_cache: bool = True) -> PermissionResult:
        """检查权限（带缓存）"""
        # 尝试从缓存获取
        if use_cache:
            cached_result = self.cache.get(user_id, resource_type, resource_id, permission_type, tenant_id)
            if cached_result is not None:
                return cached_result
        
        # 计算权限
        result = self.calculator.calculate_user_permission(
            user_id, resource_type, resource_id, permission_type, tenant_id
        )
        
        # 存入缓存
        if use_cache:
            # 根据权限类型设置不同的TTL
            ttl = 300  # 默认5分钟
            if result.granted_by and 'super_admin' in result.granted_by:
                ttl = 3600  # 超级管理员权限缓存1小时
            elif result.granted_by and 'owner' in result.granted_by:
                ttl = 1800  # 所有者权限缓存30分钟
            
            self.cache.put(user_id, resource_type, resource_id, permission_type, result, tenant_id, ttl)
        
        return result
    
    def invalidate_user_cache(self, user_id: str) -> int:
        """使用户缓存失效"""
        return self.cache.invalidate_user(user_id)
    
    def invalidate_resource_cache(self, resource_type: ResourceType, resource_id: str) -> int:
        """使资源缓存失效"""
        return self.cache.invalidate_resource(resource_type, resource_id)
    
    def invalidate_team_cache(self, team_id: str) -> int:
        """使团队缓存失效"""
        return self.cache.invalidate_team(team_id)
    
    def get_cache_stats(self) -> Dict[str, any]:
        """获取缓存统计"""
        return self.cache.get_stats()
    
    def cleanup_cache(self) -> int:
        """清理过期缓存"""
        return self.cache.cleanup_expired()

# 全局缓存实例
permission_cache = PermissionCache()