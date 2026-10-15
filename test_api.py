#!/usr/bin/env python
"""Тестовый скрипт для проверки работы API."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.api.client import SyncGdeBenzClient
from src.config.settings import CITIES

def test_api():
    print("🔍 Тестирование API gdebenz.ru")
    print("=" * 50)
    
    client = SyncGdeBenzClient()
    
    # Тест для Москвы
    city = CITIES['moscow']
    print(f"\n📍 Город: {city.name} ({city.lat}, {city.lon}), радиус: {city.radius_km} км")
    
    try:
        stations = client.get_stations_for_city(city)
        print(f"✅ Получено заправок: {len(stations)}")
        
        # Показываем первые 10 работающих заправок с топливом
        working_with_fuel = [s for s in stations if s.is_working() and s.fuels_now]
        print(f"🟢 Работающих с топливом: {len(working_with_fuel)}")
        
        print("\n📋 Примеры заправок:")
        for i, station in enumerate(working_with_fuel[:10], 1):
            fuels = station.get_available_fuels()
            prices_info = []
            for fuel in fuels:
                price = station.get_fuel_price(fuel)
                if price:
                    prices_info.append(f"{fuel}: {price.price}₽ ({price.confirmations} подтв.)")
                else:
                    prices_info.append(f"{fuel}: цена неизвестна")
            
            print(f"  {i}. {station.brand} - {station.address}")
            print(f"     Топливо: {', '.join(fuels)}")
            if prices_info:
                print(f"     Цены: {'; '.join(prices_info)}")
            if station.detail:
                print(f"     📝 {station.detail}")
            print()
        
        # Статистика по брендам
        brands = {}
        for s in stations:
            if s.brand:
                brands[s.brand] = brands.get(s.brand, 0) + 1
        
        print("🏷️ Бренды в регионе:")
        for brand, count in sorted(brands.items(), key=lambda x: -x[1]):
            print(f"  {brand}: {count}")
        
        # Статистика по топливу
        fuel_counts = {}
        for s in working_with_fuel:
            for fuel in s.get_available_fuels():
                fuel_counts[fuel] = fuel_counts.get(fuel, 0) + 1
        
        print("\n⛽ Доступность топлива:")
        for fuel, count in sorted(fuel_counts.items(), key=lambda x: -x[1]):
            print(f"  {fuel}: {count} заправок")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_api()