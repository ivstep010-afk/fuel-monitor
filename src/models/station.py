"""Модели данных для заправок и топлива."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import json


@dataclass
class FuelPrice:
    """Цена топлива."""
    price: float          # Цена
    confirmations: int    # Количество подтверждений
    updated_at: str       # Время обновления в формате "YYYY-MM-DD HH:MM:SS"
    
    @classmethod
    def from_dict(cls, data: dict) -> 'FuelPrice':
        return cls(
            price=data.get('p', 0.0),
            confirmations=data.get('n', 0),
            updated_at=data.get('t', '')
        )
    
    def to_dict(self) -> dict:
        return {
            'p': self.price,
            'n': self.confirmations,
            't': self.updated_at
        }
    
    def is_recent(self, max_age_hours: int = 24) -> bool:
        """Проверяет, что цена актуальна (не старше max_age_hours часов)."""
        if not self.updated_at:
            return False
        try:
            updated = datetime.strptime(self.updated_at, "%Y-%m-%d %H:%M:%S")
            age = datetime.now() - updated
            return age.total_seconds() < max_age_hours * 3600
        except ValueError:
            return False


@dataclass
class Station:
    """Модель заправки."""
    osm_id: str
    name: str
    brand: str
    lat: float
    lon: float
    address: str
    status: str           # "yes", "no", null
    fuels_now: str        # Строка с доступным топливом "92,95,ДТ"
    dt_only: int          # 0 или 1
    conflict: Optional[str]
    prices: Dict[str, FuelPrice] = field(default_factory=dict)
    meta: Dict = field(default_factory=dict)
    distance_km: Optional[float] = None
    detail: str = ""
    confirmations: int = 0
    last_at: str = ""
    confidence_base: float = 0.0
    svc: Optional[str] = None
    
    @classmethod
    def from_api_nearby(cls, data: dict) -> 'Station':
        """Создает станцию из ответа API /nearby."""
        prices = {}
        if data.get('prices_now'):
            for fuel_type, price_data in data['prices_now'].items():
                prices[fuel_type] = FuelPrice.from_dict(price_data)
        
        return cls(
            osm_id=str(data.get('osm_id', '')),
            name=data.get('name', ''),
            brand=data.get('brand', ''),
            lat=data.get('lat', 0.0),
            lon=data.get('lon', 0.0),
            address=data.get('addr', ''),
            status=data.get('status', ''),
            fuels_now=data.get('fuels_now', ''),
            dt_only=data.get('dt_only', 0),
            conflict=data.get('conflict'),
            prices=prices,
            meta=data.get('meta', {}),
            distance_km=data.get('distance_km'),
            detail=data.get('detail', ''),
            confirmations=data.get('confirmations', 0),
            last_at=data.get('last_at', ''),
            confidence_base=data.get('confidence_base', 0.0),
            svc=data.get('svc')
        )
    
    @classmethod
    def from_api_stations(cls, data: dict) -> 'Station':
        """Создает станцию из ответа API /stations."""
        prices = {}
        if data.get('prices_now'):
            for fuel_type, price_data in data['prices_now'].items():
                prices[fuel_type] = FuelPrice.from_dict(price_data)
        
        return cls(
            osm_id=str(data.get('osm_id', '')),
            name=data.get('name', ''),
            brand=data.get('brand', ''),
            lat=data.get('lat', 0.0),
            lon=data.get('lon', 0.0),
            address=data.get('addr', ''),
            status=data.get('status', ''),
            fuels_now=data.get('fuels_now', ''),
            dt_only=data.get('dt_only', 0),
            conflict=data.get('conflict'),
            prices=prices,
            meta=data.get('meta', {}),
        )
    
    def is_working(self) -> bool:
        """Проверяет, работает ли заправка."""
        return self.status == 'yes'
    
    def has_fuel(self, fuel_type: str) -> bool:
        """Проверяет, есть ли конкретный тип топлива."""
        if not self.fuels_now:
            return False
        return fuel_type.lower() in self.fuels_now.lower()
    
    def get_available_fuels(self) -> List[str]:
        """Возвращает список доступных типов топлива."""
        if not self.fuels_now:
            return []
        return [f.strip() for f in self.fuels_now.split(',') if f.strip()]
    
    def get_fuel_price(self, fuel_type: str) -> Optional[FuelPrice]:
        """Получает цену для типа топлива."""
        return self.prices.get(fuel_type)
    
    def matches_filter(self, filter_config) -> bool:
        """Проверяет, соответствует ли заправка фильтру."""
        if filter_config.only_working and not self.is_working():
            return False
        
        if filter_config.brands and self.brand not in filter_config.brands:
            return False
        
        if filter_config.fuels:
            available = self.get_available_fuels()
            if not any(f in available for f in filter_config.fuels):
                return False
        
        # Проверка цен
        if filter_config.min_price is not None or filter_config.max_price is not None:
            has_price_in_range = False
            for fuel_type in filter_config.fuels or self.get_available_fuels():
                price = self.get_fuel_price(fuel_type)
                if price:
                    if filter_config.min_price is not None and price.price < filter_config.min_price:
                        continue
                    if filter_config.max_price is not None and price.price > filter_config.max_price:
                        continue
                    has_price_in_range = True
                    break
            if not has_price_in_range:
                return False
        
        return True
    
    def to_dict(self) -> dict:
        """Сериализация в словарь."""
        return {
            'osm_id': self.osm_id,
            'name': self.name,
            'brand': self.brand,
            'lat': self.lat,
            'lon': self.lon,
            'address': self.address,
            'status': self.status,
            'fuels_now': self.fuels_now,
            'dt_only': self.dt_only,
            'conflict': self.conflict,
            'prices': {k: v.to_dict() for k, v in self.prices.items()},
            'meta': self.meta,
            'distance_km': self.distance_km,
            'detail': self.detail,
            'confirmations': self.confirmations,
            'last_at': self.last_at,
            'confidence_base': self.confidence_base,
            'svc': self.svc
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Station':
        """Десериализация из словаря."""
        prices = {}
        if data.get('prices'):
            for fuel_type, price_data in data['prices'].items():
                prices[fuel_type] = FuelPrice.from_dict(price_data)
        
        station = cls(
            osm_id=data.get('osm_id', ''),
            name=data.get('name', ''),
            brand=data.get('brand', ''),
            lat=data.get('lat', 0.0),
            lon=data.get('lon', 0.0),
            address=data.get('address', ''),
            status=data.get('status', ''),
            fuels_now=data.get('fuels_now', ''),
            dt_only=data.get('dt_only', 0),
            conflict=data.get('conflict'),
            prices=prices,
            meta=data.get('meta', {}),
            distance_km=data.get('distance_km'),
            detail=data.get('detail', ''),
            confirmations=data.get('confirmations', 0),
            last_at=data.get('last_at', ''),
            confidence_base=data.get('confidence_base', 0.0),
            svc=data.get('svc')
        )
        return station


@dataclass
class StationSnapshot:
    """Снимок состояния заправки для отслеживания изменений."""
    station: Station
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            'station': self.station.to_dict(),
            'timestamp': self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'StationSnapshot':
        return cls(
            station=Station.from_dict(data['station']),
            timestamp=datetime.fromisoformat(data['timestamp'])
        )