from peewee import Model, DoesNotExist
from typing import Type, TypeVar, Dict, Any, Optional

T = TypeVar('T', bound=Model)

class BaseService:
    model: Type[T]
    
    @classmethod
    def get_by_id(cls, id: str) -> Optional[T]:
        """根据ID获取记录，如果不存在返回None"""
        try:
            return cls.model.get_by_id(id)
        except DoesNotExist:
            return None
    
    @classmethod 
    def insert(cls, data: Dict[str, Any]) -> T:
        return cls.model.create(**data)
    
    @classmethod
    def delete_by_id(cls, id: str) -> int:
        return cls.model.delete().where(cls.model.id == id).execute()
    
    @classmethod
    def query(cls, **kwargs) -> list[T]:
        return list(cls.model.select().where(*[
            getattr(cls.model, k) == v for k, v in kwargs.items()
        ]))