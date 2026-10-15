"""Уведомления через Telegram Bot."""
import os
import asyncio
from typing import List, Optional
import aiohttp

from src.notifications.base import NotificationProvider
from src.services.monitor import FuelChange


class TelegramNotifier(NotificationProvider):
    """Отправляет уведомления через Telegram Bot API."""
    
    def __init__(
        self,
        bot_token: str = None,
        chat_id: str = None,
        parse_mode: str = "HTML"
    ):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.parse_mode = parse_mode
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def send(self, changes: List[FuelChange]) -> bool:
        if not changes:
            return True
        
        if not self.bot_token or not self.chat_id:
            print("⚠️ Telegram не настроен: отсутствуют TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID")
            return False
        
        message = self._format_message(changes)
        
        try:
            session = await self._get_session()
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": self.parse_mode,
                "disable_web_page_preview": True
            }
            
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ Ошибка Telegram API: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            print(f"❌ Ошибка отправки в Telegram: {e}")
            return False
    
    def _format_message(self, changes: List[FuelChange]) -> str:
        lines = [f"🔔 <b>Обнаружены изменения ({len(changes)})</b>\n"]
        
        for change in changes:
            if change.change_type == "appeared":
                emoji = "⛽"
                action = "появилось"
            elif change.change_type == "disappeared":
                emoji = "❌"
                action = "закончилось"
            elif change.change_type == "price_changed":
                emoji = "💰"
                action = "изменилась цена"
            else:
                emoji = "ℹ️"
                action = "изменилось"
            
            lines.append(
                f"{emoji} <b>{change.fuel_type}</b> {action} на "
                f"<b>{change.station.brand}</b> ({change.station.address})"
            )
            
            if change.new_price:
                lines.append(f"   💵 Цена: <b>{change.new_price.price} руб.</b>")
                lines.append(f"   ✅ Подтверждений: {change.new_price.confirmations}")
                lines.append(f"   🕐 Обновлено: {change.new_price.updated_at}")
            
            if change.station.detail:
                lines.append(f"   📝 {change.station.detail}")
            
            lines.append("")  # Пустая строка между уведомлениями
        
        return "\n".join(lines)
    
    def name(self) -> str:
        return "Telegram"
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()