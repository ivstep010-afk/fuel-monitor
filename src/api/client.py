"""Клиент для работы с API gdebenz.ru."""
import asyncio
import aiohttp
import logging
from typing import List, Optional, Dict, Any
from src.config.settings import settings
from src.models.station import Station

logger = logging.getLogger(__name__)


class GdeBenzAPIError(Exception):
    """Исключение при ошибке API."""
    pass


class GdeBenzClient:
    """Асинхронный клиент для API gdebenz.ru."""
    
    def __init__(self, base_url: str = None, timeout: int = None):
        self.base_url = base_url or settings.api_base_url
        self.timeout = aiohttp.ClientTimeout(total=timeout or settings.request_timeout)
        self.session: Optional[aiohttp.ClientSession] = None
        self.headers = {
            'User-Agent': settings.user_agent,
            'Accept': 'application/json',
            'Referer': 'https://gdebenz.ru/',
        }
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=self.timeout,
            headers=self.headers
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Выполняет HTTP запрос к API."""
        if not self.session:
            raise GdeBenzAPIError("Клиент не инициализирован. Используйте async with.")
        
        url = f"{self.base_url}{endpoint}"
        # Добавляем timestamp для обхода кэша
        if params is None:
            params = {}
        params['_'] = int(asyncio.get_event_loop().time() * 1000)
        
        try:
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    raise GdeBenzAPIError(f"HTTP {response.status}: {await response.text()}")
                
                data = await response.json()
                return data
        except aiohttp.ClientError as e:
            raise GdeBenzAPIError(f"Ошибка сети: {e}")
        except Exception as e:
            raise GdeBenzAPIError(f"Неожиданная ошибка: {e}")
    
    async def get_nearby_stations(
        self, 
        lat: float, 
        lon: float, 
        radius_km: float = 20.0
    ) -> List[Station]:
        """
        Получает заправки рядом с точкой.
        Использует endpoint /api/nearby
        """
        params = {
            'lat': lat,
            'lon': lon,
            'radius_km': radius_km,
        }
        
        data = await self._request('/nearby', params)
        
        stations = []
        for station_data in data.get('stations', []):
            try:
                station = Station.from_api_nearby(station_data)
                stations.append(station)
            except Exception as e:
                logger.warning(f"Ошибка парсинга станции: {e}, данные: {station_data}")
        
        logger.info(f"Получено {len(stations)} заправок рядом с ({lat}, {lon})")
        return stations
    
    async def get_stations_in_bbox(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> List[Station]:
        """
        Получает заправки в прямоугольной области.
        Использует endpoint /api/stations
        """
        params = {
            'lat1': lat1,
            'lon1': lon1,
            'lat2': lat2,
            'lon2': lon2,
        }
        
        data = await self._request('/stations', params)
        
        stations = []
        for station_data in data:
            try:
                station = Station.from_api_stations(station_data)
                stations.append(station)
            except Exception as e:
                logger.warning(f"Ошибка парсинга станции: {e}, данные: {station_data}")
        
        logger.info(f"Получено {len(stations)} заправок в области ({lat1},{lon1}) - ({lat2},{lon2})")
        return stations
    
    async def get_stations_for_city(self, city_config) -> List[Station]:
        """
        Получает заправки для города, используя nearby endpoint.
        """
        return await self.get_nearby_stations(
            city_config.lat,
            city_config.lon,
            city_config.radius_km
        )


# Синхронная обертка для простого использования
class SyncGdeBenzClient:
    """Синхронная обертка над асинхронным клиентом."""
    
    def __init__(self, base_url: str = None, timeout: int = None):
        self.base_url = base_url or settings.api_base_url
        self.timeout = timeout or settings.request_timeout
        self.headers = {
            'User-Agent': settings.user_agent,
            'Accept': 'application/json',
            'Referer': 'https://gdebenz.ru/',
        }
    
    def _request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        import requests
        url = f"{self.base_url}{endpoint}"
        if params is None:
            params = {}
        params['_'] = int(__import__('time').time() * 1000)
        
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise GdeBenzAPIError(f"Ошибка запроса: {e}")
    
    def get_nearby_stations(
        self, 
        lat: float, 
        lon: float, 
        radius_km: float = 20.0
    ) -> List[Station]:
        params = {'lat': lat, 'lon': lon, 'radius_km': radius_km}
        data = self._request('/nearby', params)
        
        stations = []
        for station_data in data.get('stations', []):
            try:
                stations.append(Station.from_api_nearby(station_data))
            except Exception as e:
                logger.warning(f"Ошибка парсинга станции: {e}")
        
        logger.info(f"Получено {len(stations)} заправок рядом с ({lat}, {lon})")
        return stations
    
    def get_stations_in_bbox(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> List[Station]:
        params = {'lat1': lat1, 'lon1': lon1, 'lat2': lat2, 'lon2': lon2}
        data = self._request('/stations', params)
        
        stations = []
        for station_data in data:
            try:
                stations.append(Station.from_api_stations(station_data))
            except Exception as e:
                logger.warning(f"Ошибка парсинга станции: {e}")
        
        logger.info(f"Получено {len(stations)} заправок в области")
        return stations
    
    def get_stations_for_city(self, city_config) -> List[Station]:
        return self.get_nearby_stations(
            city_config.lat,
            city_config.lon,
            city_config.radius_km
        )