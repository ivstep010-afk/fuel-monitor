import csv
import os
from datetime import datetime
from src.services.monitor import FuelChange

class CSVLogger:
    """Логгер изменений в CSV файл."""
    def __init__(self, filename: str = "data/history.csv"):
        self.filename = filename
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        self._init_file()

    def _init_file(self):
        if not os.path.exists(self.filename):
            with open(self.filename, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "brand", "address", "fuel_type", 
                    "change_type", "old_price", "new_price"
                ])

    async def log_change(self, changes: list[FuelChange]):
        """Записывает список изменений в CSV."""
        with open(self.filename, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            for change in changes:
                writer.writerow([
                    change.timestamp.isoformat(),
                    change.station.brand,
                    change.station.address,
                    change.fuel_type,
                    change.change_type,
                    change.old_price.price if change.old_price else "",
                    change.new_price.price if change.new_price else ""
                ])
