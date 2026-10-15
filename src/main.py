"""Интерактивная настройка и запуск монитора."""
import asyncio
import os
import sys
from typing import List, Optional

from src.config.settings import settings, CITIES, CityConfig, StationFilter
from src.models.station import Station
from src.api.client import SyncGdeBenzClient
from src.services.monitor import SyncStationMonitor, FuelChange
from src.notifications.console import ConsoleNotifier
from src.notifications.telegram import TelegramNotifier
from src.notifications.base import CompositeNotificationProvider
from src.services.raw_collector import RawCSVCollector
import time


def read_input(prompt: str, default: str = "") -> str:
    """Read input only from an interactive terminal, with a safe fallback."""
    if not sys.stdin.isatty():
        return default
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return default

def select_city() -> CityConfig:
    """Интерактивный выбор города."""
    city_name = os.getenv("APP_CITY", "").strip().lower()
    if not sys.stdin.isatty():
        for key, city in CITIES.items():
            if city_name in (key.lower(), city.name.lower()):
                return city
        return next(iter(CITIES.values()))

    print("\n📍 Выберите город:")
    print("-" * 40)
    
    city_list = list(CITIES.items())
    for i, (key, city) in enumerate(city_list, 1):
        print(f"  {i}. {city.name} (радиус: {city.radius_km} км)")
    
    print(f"  {len(city_list) + 1}. Другой город (ввести координаты вручную)")
    
    while True:
        try:
            choice = read_input(f"\nВаш выбор (1-{len(city_list) + 1}): ", "1")
            idx = int(choice) - 1
            
            if 0 <= idx < len(city_list):
                return city_list[idx][1]
            elif idx == len(city_list):
                return input_custom_city()
            else:
                print("❌ Неверный номер, попробуйте снова")
        except ValueError:
            print("❌ Введите число")
        except KeyboardInterrupt:
            print("\n👋 Отмена")
            sys.exit(0)


def input_custom_city() -> CityConfig:
    """Ручной ввод города."""
    print("\n📍 Ввод пользовательского города:")
    print("-" * 40)
    
    name = read_input("Название города: ", "Пользовательский") or "Пользовательский"
    
    while True:
        try:
            lat = float(read_input("Широта (lat): ", "0"))
            lon = float(read_input("Долгота (lon): ", "0"))
            radius = float(read_input("Радиус поиска (км, по умолчанию 20): ", "20") or "20")
            break
        except ValueError:
            print("❌ Введите корректные числа")
    
    return CityConfig(name=name, lat=lat, lon=lon, radius_km=radius)


def select_brands(available_brands: List[str]) -> List[str]:
    """Интерактивный выбор предпочитаемых брендов."""
    if not sys.stdin.isatty():
        return []
    print("\n⛽ Выберите предпочитаемые бренды заправок:")
    print("-" * 40)
    print("  Доступные бренды:")
    
    for i, brand in enumerate(sorted(available_brands), 1):
        print(f"    {i}. {brand}")
    
    print(f"\n  {len(available_brands) + 1}. Все бренды (пропустить фильтр)")
    print("  Введите номера через запятую (например: 1,3,5)")
    
    while True:
        try:
            choice = read_input("\nВаш выбор: ", "")
            
            if not choice:
                return []
            
            if choice == str(len(available_brands) + 1):
                return []
            
            indices = [int(x.strip()) - 1 for x in choice.split(",")]
            selected = [sorted(available_brands)[i] for i in indices if 0 <= i < len(available_brands)]
            
            if selected:
                print(f"✅ Выбрано: {', '.join(selected)}")
                return selected
            else:
                print("❌ Ничего не выбрано, попробуйте снова")
        except ValueError:
            print("❌ Неверный формат, используйте числа через запятую")
        except KeyboardInterrupt:
            print("\n👋 Отмена")
            sys.exit(0)


def select_fuels() -> List[str]:
    """Интерактивный выбор типов топлива."""
    if not sys.stdin.isatty():
        return []
    fuel_types = ["92", "95", "95+", "98", "100", "ДТ"]
    
    print("\n⛽ Выберите типы топлива для отслеживания:")
    print("-" * 40)
    
    for i, fuel in enumerate(fuel_types, 1):
        print(f"  {i}. {fuel}")
    
    print(f"\n  {len(fuel_types) + 1}. Все типы (пропустить фильтр)")
    print("  Введите номера через запятую (например: 1,2,4)")
    
    while True:
        try:
            choice = read_input("\nВаш выбор: ", "")
            
            if not choice:
                return []
            
            if choice == str(len(fuel_types) + 1):
                return []
            
            indices = [int(x.strip()) - 1 for x in choice.split(",")]
            selected = [fuel_types[i] for i in indices if 0 <= i < len(fuel_types)]
            
            if selected:
                print(f"✅ Выбрано: {', '.join(selected)}")
                return selected
            else:
                print("❌ Ничего не выбрано, попробуйте снова")
        except ValueError:
            print("❌ Неверный формат, используйте числа через запятую")
        except KeyboardInterrupt:
            print("\n👋 Отмена")
            sys.exit(0)


def setup_notifications() -> CompositeNotificationProvider:
    """Настройка провайдеров уведомлений."""
    providers = []
    
    # RawCSVCollector is used by the raw-data mode; no history logger is needed.
    providers.append(ConsoleNotifier(verbose=True))
    
    # Проверяем настройки Telegram
    if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
        print("\n📱 Найдены настройки Telegram, добавляю уведомления...")
        providers.append(TelegramNotifier())
    else:
        print("\n📱 Для уведомлений в Telegram задайте переменные окружения:")
        print("   TELEGRAM_BOT_TOKEN - токен бота")
        print("   TELEGRAM_CHAT_ID - ID чата")
        print("   (можно добавить в .env файл)")
    
    return CompositeNotificationProvider(providers)


def get_available_brands(client: SyncGdeBenzClient, city: CityConfig) -> List[str]:
    """Получает список доступных брендов в городе."""
    print(f"\n🔍 Получаю список заправок в {city.name}...")
    stations = client.get_stations_for_city(city)
    brands = sorted(set(s.brand for s in stations if s.brand))
    print(f"   Найдено заправок: {len(stations)}")
    print(f"   Брендов: {len(brands)}")
    return brands


async def run_monitor(
    city: CityConfig,
    station_filter: StationFilter,
    notifier: CompositeNotificationProvider,
    interval: int = 300
):
    """Запускает мониторинг в цикле."""
    monitor = SyncStationMonitor(
        city=city,
        station_filter=station_filter,
        on_change=lambda changes: asyncio.create_task(notifier.send(changes))
    )
    
    print(f"\n🚀 Запуск мониторинга для {city.name}")
    print(f"   Интервал проверки: {interval} сек ({interval//60} мин)")
    print(f"   Фильтр брендов: {station_filter.brands or 'все'}")
    print(f"   Фильтр топлива: {station_filter.fuels or 'все'}")
    print(f"   Только работающие: {'да' if station_filter.only_working else 'нет'}")
    print("\n🔄 Начинаю проверку... (Ctrl+C для остановки)\n")
    
    # Первая проверка сразу
    changes = monitor.check_once()
    if changes:
        await notifier.send(changes)
    else:
        print("✅ Первая проверка завершена, изменений нет")
    
    # Цикл проверок
    try:
        while True:
            await asyncio.sleep(interval)
            changes = monitor.check_once()
            if changes:
                await notifier.send(changes)
    except KeyboardInterrupt:
        print("\n👋 Остановка мониторинга...")
    finally:
        # Закрываем Telegram сессию если есть
        for provider in notifier.providers:
            if hasattr(provider, 'close'):
                await provider.close()


def main():
    """Главная функция."""
    print("=" * 60)
    print("  🛢️  GdeBenz Monitor - Мониторинг заправок")
    print("=" * 60)
    
    if sys.stdin.isatty():
        print("\nВыберите режим работы:")
        print("  1. Мониторинг изменений (с уведомлениями)")
        print("  2. Сбор сырых данных в CSV (без уведомлений)")
    
    configured_mode = os.getenv("APP_MODE", os.getenv("MODE", settings.app_mode)).strip()
    mode = configured_mode if configured_mode in {"1", "2"} else "2"
    if sys.stdin.isatty():
        mode = read_input("\nВаш выбор (1-2): ", mode)
        if mode not in {"1", "2"}:
            mode = "2"
    
    # 1. Выбор города (общий для обоих режимов)
    city = select_city()
    
    if mode == "1":
        # Режим мониторинга изменений
        client = SyncGdeBenzClient()
        available_brands = get_available_brands(client, city)
        selected_brands = select_brands(available_brands)
        selected_fuels = select_fuels()
        
        station_filter = StationFilter(
            brands=selected_brands if selected_brands else None,
            fuels=selected_fuels if selected_fuels else None,
            only_working=True
        )
        
        notifier = setup_notifications()
        
        print("\n⏱️ Интервал проверки (секунды, по умолчанию 300 = 5 мин):")
        interval_input = read_input("Интервал: ", str(settings.update_interval_seconds))
        try:
            interval = int(interval_input) if interval_input else 300
        except ValueError:
            interval = 300
        
        print(f"\n🚀 Запуск мониторинга для {city.name}")
        print(f"   Интервал проверки: {interval} сек ({interval//60} мин)")
        print(f"   Фильтр брендов: {station_filter.brands or 'все'}")
        print(f"   Фильтр топлива: {station_filter.fuels or 'все'}")
        print(f"   Только работающие: {'да' if station_filter.only_working else 'нет'}")
        print("\n🔄 Начинаю проверку... (Ctrl+C для остановки)\n")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(run_monitor(city, station_filter, notifier, interval))
        except KeyboardInterrupt:
            print("\n👋 Остановка мониторинга...")
        finally:
            loop.close()
            
    elif mode == "2":
        # Режим сбора сырых данных
        client = SyncGdeBenzClient()
        
        print("\n⏱️ Интервал между сборами (секунды, по умолчанию 300 = 5 мин):")
        interval_input = read_input("Интервал (сек): ", str(settings.update_interval_seconds))
        try:
            interval = int(interval_input) if interval_input else 300
        except ValueError:
            interval = 300
        
        collector = RawCSVCollector()
        print(f"\n🚀 Запуск сбора сырых данных для г. {city.name} каждые {interval} сек.")
        print("📁 Данные сохраняются в data/stations_raw.csv")
        print("🛑 Для остановки нажмите Ctrl+C\n")
        
        try:
            while True:
                try:
                    collector.collect_and_save(city)  # без фильтра, собираем все заправки города
                except Exception as e:
                    print(f"❌ Ошибка при сборе данных: {e}")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n👋 Сбор данных остановлен.")
    else:
        print("❌ Неверный выбор")
        sys.exit(0)


if __name__ == "__main__":
    main()