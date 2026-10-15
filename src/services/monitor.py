"""Сервис мониторинга заправок."""
import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Set, Callable, Awaitable
from dataclasses import dataclass, field

from src.config.settings import settings, StationFilter, CityConfig, CITIES
from src.models.station import Station, StationSnapshot, FuelPrice
from src.api.client import GdeBenzClient, SyncGdeBenzClient, GdeBenzAPIError

logger = logging.getLogger(__name__)


@dataclass
class FuelChange:
    """Изменение в доступности топлива."""
    station: Station
    fuel_type: str
    change_type: str  # "appeared", "disappeared", "price_changed"
    old_price: Optional[FuelPrice] = None
    new_price: Optional[FuelPrice] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __str__(self) -> str:
        if self.change_type == "appeared":
            return f"⛽ Появилось {self.fuel_type} на {self.station.brand} ({self.station.address})"
        elif self.change_type == "disappeared":
            return f"❌ Закончилось {self.fuel_type} на {self.station.brand} ({self.station.address})"
        elif self.change_type == "price_changed":
            old = self.old_price.price if self.old_price else "?"
            new = self.new_price.price if self.new_price else "?"
            return f"💰 Цена {self.fuel_type} на {self.station.brand}: {old} → {new} руб."
        return ""


class StationMonitor:
    """Мониторинг заправок с отслеживанием изменений."""
    
    def __init__(
        self,
        city: CityConfig,
        station_filter: StationFilter = None,
        update_interval: int = None,
        on_change: Callable[[List[FuelChange]], Awaitable[None]] = None
    ):
        self.city = city
        self.station_filter = station_filter or StationFilter()
        self.update_interval = update_interval or settings.update_interval_seconds
        self.on_change = on_change
        
        self._previous_stations: Dict[str, Station] = {}  # osm_id -> Station
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._client: Optional[GdeBenzClient] = None
        
        # Загружаем сохраненное состояние
        self._load_state()
    
    def _load_state(self):
        """Загружает предыдущее состояние из файла."""
        state_file = settings.state_file
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for osm_id, station_data in data.get('stations', {}).items():
                    self._previous_stations[osm_id] = Station.from_dict(station_data)
                
                logger.info(f"Загружено состояние {len(self._previous_stations)} заправок")
            except Exception as e:
                logger.warning(f"Не удалось загрузить состояние: {e}")
    
    def _save_state(self):
        """Сохраняет текущее состояние в файл."""
        state_file = settings.state_file
        os.makedirs(os.path.dirname(state_file), exist_ok=True)
        
        try:
            data = {
                'city': self.city.name,
                'timestamp': datetime.now().isoformat(),
                'stations': {
                    osm_id: station.to_dict() 
                    for osm_id, station in self._previous_stations.items()
                }
            }
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Не удалось сохранить состояние: {e}")
    
    async def start(self):
        """Запускает мониторинг."""
        if self._running:
            return
        
        self._running = True
        self._client = GdeBenzClient()
        await self._client.__aenter__()
        
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Мониторинг запущен для {self.city.name} (интервал: {self.update_interval}с)")
    
    async def stop(self):
        """Останавливает мониторинг."""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        if self._client:
            await self._client.__aexit__(None, None, None)
        
        self._save_state()
        logger.info("Мониторинг остановлен")
    
    async def _monitor_loop(self):
        """Основной цикл мониторинга."""
        while self._running:
            try:
                await self._check_stations()
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}")
            
            try:
                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
    
    async def _check_stations(self):
        """Проверяет заправки и ищет изменения."""
        if not self._client:
            return
        
        # Получаем актуальные данные
        current_stations = await self._client.get_stations_for_city(self.city)
        
        # Фильтруем
        filtered_stations = [
            s for s in current_stations 
            if s.matches_filter(self.station_filter)
        ]
        
        # Ищем изменения
        changes = self._detect_changes(filtered_stations)
        
        if changes:
            logger.info(f"Обнаружено {len(changes)} изменений")
            if self.on_change:
                await self.on_change(changes)
        
        # Обновляем состояние
        self._previous_stations = {s.osm_id: s for s in filtered_stations}
        self._save_state()
    
    def _detect_changes(self, current_stations: List[Station]) -> List[FuelChange]:
        """Сравнивает текущие заправки с предыдущими и находит изменения."""
        changes = []
        current_by_id = {s.osm_id: s for s in current_stations}
        previous_by_id = self._previous_stations
        
        all_ids = set(current_by_id.keys()) | set(previous_by_id.keys())
        
        for osm_id in all_ids:
            current = current_by_id.get(osm_id)
            previous = previous_by_id.get(osm_id)
            
            if not previous and current:
                # Новая заправка
                for fuel in current.get_available_fuels():
                    changes.append(FuelChange(
                        station=current,
                        fuel_type=fuel,
                        change_type="appeared",
                        new_price=current.get_fuel_price(fuel)
                    ))
            
            elif previous and not current:
                # Заправка исчезла (или перестала проходить фильтр)
                for fuel in previous.get_available_fuels():
                    changes.append(FuelChange(
                        station=previous,
                        fuel_type=fuel,
                        change_type="disappeared",
                        old_price=previous.get_fuel_price(fuel)
                    ))
            
            elif previous and current:
                # Сравниваем доступное топливо
                prev_fuels = set(previous.get_available_fuels())
                curr_fuels = set(current.get_available_fuels())
                
                # Появилось топливо
                for fuel in curr_fuels - prev_fuels:
                    changes.append(FuelChange(
                        station=current,
                        fuel_type=fuel,
                        change_type="appeared",
                        new_price=current.get_fuel_price(fuel)
                    ))
                
                # Исчезло топливо
                for fuel in prev_fuels - curr_fuels:
                    changes.append(FuelChange(
                        station=previous,
                        fuel_type=fuel,
                        change_type="disappeared",
                        old_price=previous.get_fuel_price(fuel)
                    ))
                
                # Проверяем изменение цен
                for fuel in prev_fuels & curr_fuels:
                    old_price = previous.get_fuel_price(fuel)
                    new_price = current.get_fuel_price(fuel)
                    
                    if old_price and new_price and old_price.price != new_price.price:
                        changes.append(FuelChange(
                            station=current,
                            fuel_type=fuel,
                            change_type="price_changed",
                            old_price=old_price,
                            new_price=new_price
                        ))
        
        return changes
    
    async def check_once(self) -> List[FuelChange]:
        """Однократная проверка (для тестов или ручного запуска)."""
        if not self._client:
            self._client = GdeBenzClient()
            await self._client.__aenter__()
        
        current_stations = await self._client.get_stations_for_city(self.city)
        filtered_stations = [
            s for s in current_stations 
            if s.matches_filter(self.station_filter)
        ]
        
        changes = self._detect_changes(filtered_stations)
        self._previous_stations = {s.osm_id: s for s in filtered_stations}
        self._save_state()
        
        return changes


class SyncStationMonitor:
    """Синхронная версия монитора для простого использования."""
    
    def __init__(
        self,
        city: CityConfig,
        station_filter: StationFilter = None,
        on_change: Callable[[List[FuelChange]], None] = None
    ):
        self.city = city
        self.station_filter = station_filter or StationFilter()
        self.on_change = on_change
        
        self._previous_stations: Dict[str, Station] = {}
        self._client = SyncGdeBenzClient()
        
        self._load_state()
    
    def _load_state(self):
        state_file = settings.state_file
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for osm_id, station_data in data.get('stations', {}).items():
                    self._previous_stations[osm_id] = Station.from_dict(station_data)
            except Exception as e:
                logger.warning(f"Не удалось загрузить состояние: {e}")
    
    def _save_state(self):
        state_file = settings.state_file
        os.makedirs(os.path.dirname(state_file), exist_ok=True)
        
        try:
            data = {
                'city': self.city.name,
                'timestamp': datetime.now().isoformat(),
                'stations': {
                    osm_id: station.to_dict() 
                    for osm_id, station in self._previous_stations.items()
                }
            }
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Не удалось сохранить состояние: {e}")
    
    def check_once(self) -> List[FuelChange]:
        """Однократная проверка."""
        current_stations = self._client.get_stations_for_city(self.city)
        filtered_stations = [
            s for s in current_stations 
            if s.matches_filter(self.station_filter)
        ]
        
        changes = self._detect_changes(filtered_stations)
        
        if changes and self.on_change:
            self.on_change(changes)
        
        self._previous_stations = {s.osm_id: s for s in filtered_stations}
        self._save_state()
        
        return changes
    
    def _detect_changes(self, current_stations: List[Station]) -> List[FuelChange]:
        changes = []
        current_by_id = {s.osm_id: s for s in current_stations}
        previous_by_id = self._previous_stations
        
        all_ids = set(current_by_id.keys()) | set(previous_by_id.keys())
        
        for osm_id in all_ids:
            current = current_by_id.get(osm_id)
            previous = previous_by_id.get(osm_id)
            
            if not previous and current:
                for fuel in current.get_available_fuels():
                    changes.append(FuelChange(
                        station=current,
                        fuel_type=fuel,
                        change_type="appeared",
                        new_price=current.get_fuel_price(fuel)
                    ))
            
            elif previous and not current:
                for fuel in previous.get_available_fuels():
                    changes.append(FuelChange(
                        station=previous,
                        fuel_type=fuel,
                        change_type="disappeared",
                        old_price=previous.get_fuel_price(fuel)
                    ))
            
            elif previous and current:
                prev_fuels = set(previous.get_available_fuels())
                curr_fuels = set(current.get_available_fuels())
                
                for fuel in curr_fuels - prev_fuels:
                    changes.append(FuelChange(
                        station=current,
                        fuel_type=fuel,
                        change_type="appeared",
                        new_price=current.get_fuel_price(fuel)
                    ))
                
                for fuel in prev_fuels - curr_fuels:
                    changes.append(FuelChange(
                        station=previous,
                        fuel_type=fuel,
                        change_type="disappeared",
                        old_price=previous.get_fuel_price(fuel)
                    ))
                
                for fuel in prev_fuels & curr_fuels:
                    old_price = previous.get_fuel_price(fuel)
                    new_price = current.get_fuel_price(fuel)
                    
                    if old_price and new_price and old_price.price != new_price.price:
                        changes.append(FuelChange(
                            station=current,
                            fuel_type=fuel,
                            change_type="price_changed",
                            old_price=old_price,
                            new_price=new_price
                        ))
        
        return changes