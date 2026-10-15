"""Уведомления в консоль."""
from typing import List
from src.notifications.base import NotificationProvider
from src.services.monitor import FuelChange


class ConsoleNotifier(NotificationProvider):
    """Выводит уведомления в консоль."""
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
    
    async def send(self, changes: List[FuelChange]) -> bool:
        if not changes:
            return True
        
        print("\n" + "=" * 60)
        print(f"🔔 ОБНАРУЖЕНЫ ИЗМЕНЕНИЯ ({len(changes)})")
        print("=" * 60)
        
        for change in changes:
            print(f"\n{change}")
            
            if self.verbose and change.new_price:
                print(f"   Цена: {change.new_price.price} руб.")
                print(f"   Подтверждений: {change.new_price.confirmations}")
                print(f"   Обновлено: {change.new_price.updated_at}")
            
            if self.verbose:
                print(f"   Заправка: {change.station.brand} - {change.station.name}")
                print(f"   Адрес: {change.station.address}")
                print(f"   Координаты: {change.station.lat}, {change.station.lon}")
                if change.station.detail:
                    print(f"   Детали: {change.station.detail}")
        
        print("=" * 60 + "\n")
        return True
    
    def name(self) -> str:
        return "Console"