import csv
import os
from datetime import datetime
from typing import List
from src.config.settings import CityConfig, StationFilter
from src.api.client import SyncGdeBenzClient
from src.models.station import Station

class RawCSVCollector:
    """Сборщик сырых данных по заправкам в CSV файл."""
    def __init__(self, filename: str = "data/stations_raw.csv"):
        self.filename = filename
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        self._init_file()

    def _init_file(self):
        if not os.path.exists(self.filename):
            with open(self.filename, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "collection_timestamp",
                    "city",
                    "osm_id",
                    "name",
                    "brand",
                    "lat",
                    "lon",
                    "address",
                    "status",
                    "fuels_now",
                    "dt_only",
                    "confirmations",
                    "last_at",
                    "prices_json"
                ])

    def collect_and_save(self, city: CityConfig, station_filter: StationFilter = None):
        """Запрашивает данные по городу и сохраняет все заправки в CSV."""
        client = SyncGdeBenzClient()
        stations = client.get_stations_for_city(city)
        
        if station_filter:
            stations = [s for s in stations if s.matches_filter(station_filter)]
            
        timestamp = datetime.now().isoformat()
        
        with open(self.filename, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            for station in stations:
                prices_dict = {k: v.to_dict() for k, v in station.prices.items()}
                import json
                writer.writerow([
                    timestamp,
                    city.name,
                    station.osm_id,
                    station.name,
                    station.brand,
                    station.lat,
                    station.lon,
                    station.address,
                    station.status,
                    station.fuels_now,
                    station.dt_only,
                    station.confirmations,
                    station.last_at,
                    json.dumps(prices_dict, ensure_ascii=False)
                ])
        
        print(f"📥 [{timestamp}] Собрано и записано заправок: {len(stations)} для г. {city.name}")
