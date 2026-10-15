"""Конфигурация приложения."""
import os
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class StationFilter:
    """Фильтр для заправок."""
    brands: Optional[List[str]] = None  # Список предпочитаемых брендов
    fuels: Optional[List[str]] = None   # Список нужных типов топлива (92, 95, 98, 100, ДТ)
    min_price: Optional[float] = None   # Минимальная цена
    max_price: Optional[float] = None   # Максимальная цена
    only_working: bool = True           # Только работающие заправки


@dataclass
class CityConfig:
    """Конфигурация города."""
    name: str
    lat: float
    lon: float
    radius_km: float = 20.0


# Предустановленные города
CITIES = {
    "moscow": CityConfig("Москва", 55.75, 37.60, 20.0),
    "spb": CityConfig("Санкт-Петербург", 59.93, 30.31, 20.0),
    "kazan": CityConfig("Казань", 55.79, 49.11, 20.0),
    "ekb": CityConfig("Екатеринбург", 56.84, 60.60, 20.0),
    "nsk": CityConfig("Новосибирск", 55.01, 82.93, 20.0),
    "cheboksary": CityConfig("Чебоксары", 56.13, 47.25, 20.0),
}


@dataclass
class Settings:
    """Основные настройки приложения."""
    # API
    api_base_url: str = "https://gdebenz.ru/api"
    request_timeout: int = 30
    update_interval_seconds: int = 300  # 5 минут
    
    # Город и фильтры (будут заполнены при запуске)
    city: Optional[CityConfig] = None
    station_filter: Optional[StationFilter] = None
    
    # Уведомления
    notify_on_fuel_available: bool = True
    notify_on_price_drop: bool = False
    price_drop_threshold_percent: float = 5.0
    
    # Хранение состояния
    state_file: str = "data/state.json"
    log_file: str = "data/monitor.log"
    
    # User-Agent для запросов
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def load_settings() -> Settings:
    """Загружает настройки из переменных окружения или использует дефолты."""
    settings = Settings()
    
    # Можно расширить загрузку из .env файла
    if os.getenv("GDEBENZ_UPDATE_INTERVAL"):
        settings.update_interval_seconds = int(os.getenv("GDEBENZ_UPDATE_INTERVAL", "300"))
    
    if os.getenv("GDEBENZ_API_URL"):
        settings.api_base_url = os.getenv("GDEBENZ_API_URL", "https://gdebenz.ru/api")
    
    return settings


# Глобальный экземпляр настроек
settings = load_settings()