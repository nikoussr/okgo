# telegram_bot/service.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

from database.models import Trip, TripType, User, CarClass
import asyncio
from telegram_bot.callback_data import AcceptTripCallback, create_accept_trip_keyboard
import logging
from sqlalchemy import select
from database.session import async_session_maker
from sqlalchemy.orm import selectinload



logger = logging.getLogger(__name__)


class TelegramService:
    def __init__(self, bot, channel_id):
        self.bot = bot
        self.channel_id = channel_id
        # Кэш текущих цен для поездок
        self.price_cache = {}

    async def send_trip_to_channel(self, trip: Trip, creator: User):
        """Отправляет поездку в канал с кнопками изменения цены"""
        try:
            message_text = self._format_trip_message(trip, creator)

            # Начальная цена (если есть фиксированная, иначе 0)
            if not trip.price:
                current_price = trip.total_seats * 2000.0
            else:
                current_price = trip.price

            # Сохраняем в кэше
            self.price_cache[trip.id] = current_price

            keyboard = create_accept_trip_keyboard(trip, current_price)

            message = await self.bot.send_message(
                chat_id=self.channel_id,
                text=message_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )

            logger.info(f"Trip {trip.id} sent to channel, message_id: {message.message_id}")
            return message.message_id

        except Exception as e:
            logger.error(f"Error sending trip to channel: {e}")
            raise

    def _format_trip_message(self, trip: Trip, creator: User, current_price: float = None) -> str:
        """Форматирует сообщение о поездке с текущей ценой"""
        formatted_date = trip.departure_datetime.strftime("%d.%m.%Y %H:%M")

        car_class = None
        if trip.car_class and trip.car_class.value == CarClass.PASSENGER_CAR.value:
            car_class = "Легковой авто"
        elif trip.car_class and trip.car_class.value == CarClass.BUSINESS.value:
            car_class = "Бизнес"
        elif trip.car_class and trip.car_class.value == CarClass.MICROBUS.value:
            car_class = "Микроавтобус"
        elif trip.car_class and trip.car_class.value == CarClass.BUS.value:
            car_class = "Автобус"

        car_class_text = f"🚘 <b>Класс авто:</b> {car_class}\n" if car_class else ""
        description_text = f"📝 <b>Описание:</b> {trip.description}\n" if trip.description else ""

        # Отображаем текущую цену или фиксированную
        if current_price is not None and current_price > 0:
            price_text = f"💰 <b>Текущая цена:</b> {current_price} ₽\n"
        elif trip.price:
            price_text = f"💰 <b>Цена:</b> {trip.price} ₽\n"
        else:
            price_text = "💰 <b>Цена:</b> Договорная\n"

        delegation_commission_text = f"💸 <b>Комиссия агенту:</b> {trip.delegation_commission} ₽" if trip.delegation_commission else ""

        creator_info = f"👤 <b>Создатель:</b> {creator.first_name or 'Пользователь'}"
        if creator.username or creator.username != 'None':
            creator_info += f" (@{creator.username})"

        message = (
            f"<b>НОВАЯ ПОЕЗДКА #{trip.id}</b>\n"
            f"<i>Требуется водитель</i>\n\n"
            f"📍 <b>Откуда:</b> {trip.from_address}\n"
            f"🎯 <b>Куда:</b> {trip.to_address}\n"
            f"🕐 <b>Дата и время выезда:</b> {formatted_date}\n"
            f"👥 <b>Количество мест:</b> {trip.total_seats}\n"
            f"{car_class_text}"
            f"{description_text}"
            f"{price_text}"
            f"{delegation_commission_text}\n\n"
            f"{creator_info}\n"
        )

        message += f"⚡ <i>Измените цену и откликнитесь</i>"

        return message

    async def update_trip_price(self, message_id: int, trip: Trip, creator: User, new_price: float):
        """Обновляет цену в сообщении канала"""
        try:
            # Обновляем кэш
            self.price_cache[trip.id] = new_price

            # Форматируем сообщение с новой ценой
            message_text = self._format_trip_message(trip, creator, new_price)

            # Создаем клавиатуру с новой ценой
            keyboard = create_accept_trip_keyboard(trip, new_price)

            # Обновляем сообщение
            await self.bot.edit_message_text(
                chat_id=self.channel_id,
                message_id=message_id,
                text=message_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )

            logger.info(f"Price updated to {new_price}₽ for trip {trip.id}")

        except Exception as e:
            logger.error(f"Error updating trip price: {e}")
            raise

    async def update_trip_message(self, message_id: int, trip: Trip, accepted_by_user: User):
        """Обновляет сообщение в канале после принятия заказа"""
        try:
            # Всегда выполняем в текущем event loop
            await self._perform_message_update(message_id, trip, accepted_by_user)

        except Exception as e:
            logger.error(f"Error updating trip message: {e}")
            raise

    async def _perform_message_update(self, message_id: int, trip: Trip, accepted_by_user: User):
        """Выполняет фактическое обновление сообщения"""
        try:
            # Перезагружаем поездку с отношениями в новой сессии
            async with async_session_maker() as db:
                # Получаем поездку с загруженными отношениями
                result = await db.execute(
                    select(Trip)
                    .options(selectinload(Trip.creator))
                    .where(Trip.id == trip.id)
                )
                trip_with_relations = result.scalar_one()

                # Форматируем текст
                original_text = self._format_trip_message(trip_with_relations, trip_with_relations.creator)

                driver_info = f"👤 <b>Принял:</b> {accepted_by_user.first_name or 'Водитель'}"
                if accepted_by_user.username:
                    driver_info += f" (@{accepted_by_user.username})"

                updated_text = (
                    f"{original_text}\n\n"
                    f"✅ <b>Водитель найден</b>\n"
                )

                # Редактируем сообщение
                await self.bot.edit_message_text(
                    chat_id=self.channel_id,
                    message_id=message_id,
                    text=updated_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=None
                )

            logger.info(f"Trip message {message_id} successfully updated")

        except Exception as e:
            logger.error(f"Error in _perform_message_update: {e}")
            raise