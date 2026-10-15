"""Базовые классы для уведомлений."""
from abc import ABC, abstractmethod
from typing import List
from src.services.monitor import FuelChange


class NotificationProvider(ABC):
    """Базовый класс провайдера уведомлений."""
    
    @abstractmethod
    async def send(self, changes: List[FuelChange]) -> bool:
        """
        Отправляет уведомления об изменениях.
        
        Args:
            changes: Список изменений
            
        Returns:
            True если успешно отправлено
        """
        pass
    
    @abstractmethod
    def name(self) -> str:
        """Возвращает имя провайдера."""
        pass


class CompositeNotificationProvider(NotificationProvider):
    """Композитный провайдер - отправляет через несколько каналов."""
    
    def __init__(self, providers: List[NotificationProvider]):
        self.providers = providers
    
    async def send(self, changes: List[FuelChange]) -> bool:
        results = []
        for provider in self.providers:
            try:
                result = await provider.send(changes)
                results.append(result)
            except Exception as e:
                print(f"Ошибка в провайдере {provider.name()}: {e}")
                results.append(False)
        return any(results)  # Успех, если хотя бы один сработал
    
    def name(self) -> str:
        return f"Composite({', '.join(p.name() for p in self.providers)})"