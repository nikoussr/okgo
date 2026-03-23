from aiogram import types, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from sqlalchemy import select, update
import logging

from config import settings
from database.session import async_session_maker
from telegram_bot.core import bot, CHANNEL_ID
from database.models import Trip, User, Vehicle, TripResponse, TripStatus, TripResponseStatus, UserRole, CarClass
from .callback_data import create_share_contacts_keyboard, PriceActionCallback, create_vehicle_selection_keyboard, \
    SelectVehicleCallback
from aiogram.enums import ParseMode
from aiogram import Router
from telegram_bot.service import TelegramService
from aiogram.types import LabeledPrice, PreCheckoutQuery, SuccessfulPayment
from aiogram.filters import CommandObject
from datetime import datetime, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import json


logger = logging.getLogger(__name__)

router = Router()

from aiogram import Router, types
from aiogram.filters import Command


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """
    Обработчик команды /start
    """
    try:
        user = message.from_user
        logger.info(f"Новый пользователь: {user.id} - {user.username}")

        welcome_text = f"""
Привет, {user.first_name}!

Это бот для помощи в организации трансфера OkGo!

Основной функционал доступен в нашем мини-приложении, где вы можете:
- Сохранять поездку в свой календарь
- Опубликовать свою поездку в телеграм канал
- Общаться с другими участниками сообщетва
- Управлять своими поездками

Для доступа к расширенным возможностям используйте команду
/buy для оформления подписки.

Подписка позволяет откликаться на поездки и отправлять сообщения в канал.

P.S. Введите реферальный код друга в мини-приложении и получите 7 дней пробного периода!

Если у вас есть вопросы - пишите @dinozavrik_22.
        """

        keyboard = [
            [
                InlineKeyboardButton(text="Купить подписку", callback_data="buy_subscription"),
                InlineKeyboardButton(text="Канал", url="https://t.me/+NSeQFTbF6jRlODli")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

        await message.answer(text=welcome_text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка в команде /start: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")


@router.callback_query(F.data.startswith("share_contacts:"))
async def handle_share_contacts(callback: CallbackQuery):
    """Обработчик кнопки отправки контактов"""
    async with async_session_maker() as db:
        try:
            # Парсим данные из callback_data
            parts = callback.data.split(":")
            trip_id = int(parts[1])
            driver_id = int(parts[2])
            vehicle_id = int(parts[3])

            logger.info(f"Processing share_contacts for trip {trip_id} with driver {driver_id}")

            # Получаем информацию о поездке
            trip_result = await db.execute(
                select(Trip).where(Trip.id == trip_id)
            )
            trip = trip_result.scalar_one_or_none()

            if not trip:
                await callback.answer("❌ Поездка не найдена", show_alert=True)
                return

            if trip.driver_id is not None:
                await callback.answer(
                    "❌ Водитель для этой поездки уже выбран. Контакты уже отправлены.",
                    show_alert=True
                )
                return

            # Проверяем что пользователь является создателем поездки
            creator_result = await db.execute(
                select(User).where(User.id == trip.creator_id)
            )
            creator: User = creator_result.scalar_one_or_none()

            if creator.telegram_id != callback.from_user.id:
                await callback.answer("❌ Вы не можете отправлять контакты для этой поездки", show_alert=True)
                return

            # Получаем информацию о водителе
            driver_result = await db.execute(
                select(User).where(User.id == driver_id)
            )
            driver = driver_result.scalar_one_or_none()

            if not driver:
                await callback.answer("❌ Водитель не найден", show_alert=True)
                return

            # Получаем информацию об автомобиле водителя
            vehicle_result = await db.execute(
                select(Vehicle)
                .where(Vehicle.driver_id == driver_id)
                .where(Vehicle.is_active == True)
                .where(Vehicle.id == vehicle_id)
            )
            vehicle = vehicle_result.scalar_one_or_none()

            if not vehicle:
                await callback.answer("❌ У водителя нет активного автомобиля", show_alert=True)
                return

            # Получаем предложенную цену из отклика водителя
            trip_response_result = await db.execute(
                select(TripResponse)
                .where(TripResponse.trip_id == trip_id)
                .where(TripResponse.driver_id == driver_id)
            )
            trip_response = trip_response_result.scalar_one_or_none()

            # ✅ ДОБАВЛЕНО: Сохраняем цену и автомобиль в поездку
            if trip_response and trip_response.proposed_price:
                # Если была договорная цена, сохраняем предложенную цену
                trip.price = trip_response.proposed_price
                logger.info(f"Saved negotiated price {trip_response.proposed_price} for trip {trip_id}")

            # ✅ ДОБАВЛЕНО: Сохраняем информацию об автомобиле в поездку
            trip.vehicle_id = vehicle.id
            trip.car_class = vehicle.car_class  # Сохраняем класс авто из автомобиля водителя

            # Обновляем статусы в базе данных
            # Обновляем поездку - назначаем водителя
            trip.driver_id = driver_id
            trip.status = TripStatus.CONFIRMED
            trip.is_delegation_active = False

            # Обновляем отклик - помечаем как принятый
            if trip_response:
                trip_response.status = TripResponseStatus.ACCEPTED

            # Отклоняем все остальные отклики на эту поездку
            await db.execute(
                update(TripResponse)
                .where(TripResponse.trip_id == trip_id)
                .where(TripResponse.driver_id != driver_id)
                .values(status=TripResponseStatus.REJECTED)
            )

            await db.commit()
            if trip.car_class and trip.car_class.value == CarClass.PASSENGER_CAR.value:
                car_class = "легковой авто"
            elif trip.car_class and trip.car_class.value == CarClass.BUSINESS.value:
                car_class = "бизнес"
            elif trip.car_class and trip.car_class.value == CarClass.MICROBUS.value:
                car_class = "микроавтобус"
            elif trip.car_class and trip.car_class.value == CarClass.BUS.value:
                car_class = "автобус"

            # Формируем сообщеине для водителя
            trip_info = f"📍 <b>Маршрут:</b> {trip.from_address} → {trip.to_address}"
            trip_info += f"\n🕐 <b>Отправление:</b> {trip.departure_datetime.strftime('%d.%m.%Y %H:%M')}"
            trip_info += f"\n👥 <b>Мест:</b> {trip.total_seats}"
            if trip.description:
                trip_info += f"\n📝 <b>Описание:</b> {trip.description}"

            passenger_info = ""
            if trip.passenger_phone_number:
                passenger_info = f"\n📱 <b>Контакт пассажира:</b> {trip.passenger_phone_number}"

            vehicle_info = f"🚗 <b>Авто:</b> {vehicle.color} {vehicle.brand} {vehicle.model} ({car_class}) {vehicle.license_plate}"

            creator_info = f"👤 <b>Агент:</b> {creator.first_name or 'Пользователь'}"
            if creator.username:
                creator_info += f" (@{creator.username})"
            if creator.sbp_bank and creator.phone_number:
                creator_info += f"\n📞 <b>Телефон:</b> {creator.phone_number} {creator.sbp_bank}\n"
            elif creator.sbp_phone_number:
                creator_info += f"\n📞 <b>Телефон:</b> {creator.phone_number}\n"

            financial_info = ""
            if trip.delegation_commission:
                financial_info += f"💸 <b>Комиссия агенту:</b> {trip.delegation_commission} ₽\n"
            if trip.price:
                financial_info += f"💰 <b>Цена:</b> {trip.price} ₽\n"

            message_to_driver = (
                f"✅ <b>ВАС ВЫБРАЛИ ДЛЯ ЗАКАЗА #{trip.id}</b>\n\n"
                f"{trip_info}\n"
                f"{passenger_info}\n\n"
                f"{vehicle_info}\n"
                f"{creator_info}\n"
                f"{financial_info}\n"
                f"⚠️ <i>Поездка сохранена в календарь. Не забудьте перевести комиссию агенту!</i>"

            )

            await bot.send_message(
                chat_id=driver.telegram_id,
                text=message_to_driver,
                parse_mode=ParseMode.HTML
            )

            # Обновляем сообщение создателю
            await callback.message.edit_text(
                text=callback.message.text + f"\n\n✅ <b>Контакты отправлены водителю</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=None
            )

            await callback.answer("✅ Контакты отправлены водителю")

            logger.info(
                f"Contacts shared for trip {trip_id} with driver {driver_id}, price: {trip.price}, vehicle: {vehicle.id}")

            telegram_service = TelegramService(bot, CHANNEL_ID)

            await telegram_service.update_trip_message(
                message_id=trip.channel_message_id,
                trip=trip,
                accepted_by_user=driver
            )

        except Exception as e:
            logger.error(f"Error sharing contacts: {e}")
            await callback.answer("❌ Произошла ошибка при отправке контактов", show_alert=True)
            await db.rollback()


@router.callback_query(PriceActionCallback.filter())
async def handle_price_action(callback: CallbackQuery, callback_data: PriceActionCallback):
    """Обработчик действий с ценой"""
    trip_id = callback_data.trip_id
    action = callback_data.action
    current_price = callback_data.current_price

    async with async_session_maker() as db:
        try:
            # Получаем информацию о поездке
            trip_result = await db.execute(
                select(Trip).where(Trip.id == trip_id)
            )
            trip = trip_result.scalar_one_or_none()

            user_id = callback.from_user.id
            user_result = await db.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = user_result.scalar_one_or_none()
            if not user.is_verified:
                await callback.answer("❌ Подписка PRO неактивна. Чтобы приобрести подписку, отправьте в бот /buy",
                                      show_alert=True)
                return

            if not trip:
                await callback.answer("❌ Поездка не найдена", show_alert=True)
                return

            # Получаем создателя поездки
            creator_result = await db.execute(
                select(User).where(User.id == trip.creator_id)
            )
            creator = creator_result.scalar_one_or_none()

            # Вычисляем новую цену
            new_price = current_price
            if action == "increase":
                new_price = current_price + 500
            elif action == "decrease":
                new_price = max(0, current_price - 500)  # Не ниже 0
            elif action == "accept":
                # Обработка отклика по текущей цене
                await handle_accept_with_price(callback, trip, current_price, db)
                return
            telegram_service = TelegramService(bot, CHANNEL_ID)

            # Обновляем сообщение в канале с новой ценой
            await telegram_service.update_trip_price(
                message_id=callback.message.message_id,
                trip=trip,
                creator=creator,
                new_price=new_price
            )

            await callback.answer(f"💰 Цена изменена: {new_price}₽")

        except Exception as e:
            logger.error(f"Error handling price action: {e}")
            await callback.answer("❌ Ошибка при изменении цены", show_alert=True)


async def handle_accept_with_price(callback: CallbackQuery, trip: Trip, price: int, db):
    """Обработка отклика с указанной ценой"""
    user_id = callback.from_user.id

    # Получаем информацию о пользователе
    user_result = await db.execute(
        select(User).where(User.telegram_id == user_id)
    )
    user = user_result.scalar_one_or_none()

    if not user.is_verified:
        await callback.answer("❌ Подписка PRO неактивна. Чтобы приобрести подписку, отправьте в бот /buy",
                              show_alert=True)
        return

    if not user:
        await callback.answer("❌ Пользователь не найден в системе", show_alert=True)
        return

    # Проверяем роль пользователя
    if user.role != UserRole.DRIVER:
        await callback.answer("❌ Только водители могут принимать заказы", show_alert=True)
        return

    # Проверяем что пользователь не создатель поездки
    if trip.creator_id == user.id:
        await callback.answer("❌ Вы не можете принять свою собственную поездку", show_alert=True)
        return

    # Проверяем что поездка еще активна
    if trip.status != TripStatus.PUBLISHED:
        await callback.answer("❌ Поездка уже неактивна", show_alert=True)
        return

    # Получаем активные автомобили пользователя
    vehicles_result = await db.execute(
        select(Vehicle)
        .where(Vehicle.driver_id == user.id)
        .where(Vehicle.is_active == True)
    )
    vehicles = vehicles_result.scalars().all()

    if not vehicles:
        await callback.answer("❌ У вас нет активных автомобилей", show_alert=True)
        return

    # Если автомобиль только один - используем старую логику
    if len(vehicles) == 1:
        vehicle = vehicles[0]

        # Проверяем не откликался ли уже пользователь на эту поездку
        existing_response_result = await db.execute(
            select(TripResponse)
            .where(TripResponse.trip_id == trip.id)
            .where(TripResponse.driver_id == user.id)
        )
        existing_response = existing_response_result.scalar_one_or_none()

        if existing_response:
            await callback.answer("❌ Вы уже откликались на эту поездку", show_alert=True)
            return

        # Создаем запись об отклике с ценой
        trip_response = TripResponse(
            trip_id=trip.id,
            driver_id=user.id,
            vehicle_id=vehicle.id,
            status=TripResponseStatus.PENDING,
            proposed_price=price
        )

        db.add(trip_response)
        await db.commit()

        # Отправляем уведомление агенту с предложенной ценой
        await notify_agent_about_response(trip, user, vehicle, price)

        await callback.answer(f"✅ Отклик отправлен! Ваша цена: {price}₽", show_alert=True)
    else:
        # Если автомобилей несколько - показываем выбор
        await show_vehicle_selection(callback, trip, user, vehicles, price)


async def notify_agent_about_offer(trip: Trip, driver: User, vehicle: Vehicle, price: float):
    """Уведомляет агента о новом отклике с ценой (теперь использует общую функцию)"""
    await notify_agent_about_response(trip, driver, vehicle, price)


async def delete_message_from_channel(message_id: int):
    try:
        await bot.delete_message(
            chat_id=CHANNEL_ID,
            message_id=message_id
        )
    except Exception as e:
        logger.error(f"Error deleting message from channel: {e}")


@router.callback_query(F.data.startswith("accept_trip:"))
async def handle_accept_trip(callback: CallbackQuery):
    """Обработчик клика на кнопку 'Принять заказ'"""
    async with async_session_maker() as db:
        try:
            # Парсим trip_id из callback_data
            trip_id = int(callback.data.split(":")[1])
            user_id = callback.from_user.id

            logger.info(f"Processing accept_trip for trip {trip_id} from user {user_id}")

            # Получаем информацию о пользователе
            user_result = await db.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await callback.answer("❌ Пользователь не найден в системе", show_alert=True)
                return

            # Проверяем роль пользователя
            if user.role != UserRole.DRIVER:
                await callback.answer("❌ Только водители могут принимать заказы", show_alert=True)
                return

            if not user.is_verified:
                await callback.answer("❌ Подписка PRO неактивна. Чтобы приобрести подписку, отправьте в бот /buy",
                                      show_alert=True)
                return

            # Получаем информацию о поездке
            trip_result = await db.execute(
                select(Trip).where(Trip.id == trip_id)
            )
            trip = trip_result.scalar_one_or_none()

            if not trip:
                await callback.answer("❌ Поездка не найдена", show_alert=True)
                return

            # Проверяем что пользователь не создатель поездки
            if trip.creator_id == user.id:
                await callback.answer("❌ Вы не можете принять свою собственную поездку", show_alert=True)
                return

            # Проверяем что поездка еще активна
            if trip.status == TripStatus.CONFIRMED or trip.status == TripStatus.COMPLETED:
                await callback.answer("❌ Поездка уже неактивна", show_alert=True)
                return

            # Получаем активные автомобили пользователя
            vehicles_result = await db.execute(
                select(Vehicle)
                .where(Vehicle.driver_id == user.id)
                .where(Vehicle.is_active == True)
            )
            vehicles = vehicles_result.scalars().all()

            if not vehicles:
                await callback.answer("❌ У вас нет добавленных авто. Сделать это можно в мини приложении",
                                      show_alert=True)
                return

            # Если автомобиль только один - используем старую логику
            if len(vehicles) == 1:
                vehicle = vehicles[0]

                # Проверяем не откликался ли уже пользователь на эту поездку
                existing_response_result = await db.execute(
                    select(TripResponse)
                    .where(TripResponse.trip_id == trip_id)
                    .where(TripResponse.driver_id == user.id)
                )
                existing_response = existing_response_result.scalar_one_or_none()

                if existing_response:
                    await callback.answer("❌ Вы уже откликались на эту поездку", show_alert=True)
                    return

                trip.status = TripStatus.PENDING

                # Создаем запись об отклике
                trip_response = TripResponse(
                    trip_id=trip_id,
                    driver_id=user.id,
                    vehicle_id=vehicle.id,
                    status=TripResponseStatus.PENDING
                )

                db.add(trip_response)
                await db.commit()
                await db.refresh(trip_response)

                # Отправляем уведомление создателю
                await notify_agent_about_response(trip, user, vehicle, None)

                await callback.answer("✅ Ваш отклик отправлен создателю поездки", show_alert=True)
                logger.info(f"User {user.id} responded to trip {trip_id} with single vehicle {vehicle.id}")

            else:
                # Если автомобилей несколько - показываем выбор
                await show_vehicle_selection(callback, trip, user, vehicles, None)
                await callback.answer("✅ Выберите авто в чате с ботом", show_alert=True)

        except Exception as e:
            logger.error(f"Error handling accept trip: {e}")
            await callback.answer("❌ Произошла ошибка при обработке запроса", show_alert=True)
            await db.rollback()


async def show_vehicle_selection(callback: CallbackQuery, trip: Trip, user: User, vehicles: list,
                                 proposed_price: float = None):
    """Показывает выбор автомобиля для отклика"""
    try:
        # Форматируем информацию о поездке
        formatted_date = trip.departure_datetime.strftime("%d.%m.%Y %H:%M")

        trip_info = (
            f"📍 <b>Маршрут:</b> {trip.from_address} → {trip.to_address}\n"
            f"🕐 <b>Дата и время выезда:</b> {formatted_date}\n"
            f"👥 <b>Количество мест:</b> {trip.total_seats}\n"
        )

        if proposed_price:
            trip_info += f"💰 <b>Цена:</b> {proposed_price} ₽\n"
        elif trip.price:
            trip_info += f"💰 <b>Цена:</b> {trip.price} ₽\n"
        else:
            trip_info += "💰 <b>Цена:</b> Договорная\n"

        message_text = (
            f"🚗 <b>ВЫБЕРИТЕ АВТОМОБИЛЬ ДЛЯ ПОЕЗДКИ #{trip.id}</b>\n\n"
            f"{trip_info}\n"
            f"👇 <i>Выберите один из ваших автомобилей:</i>"
        )

        # Создаем клавиатуру с автомобилями
        keyboard = create_vehicle_selection_keyboard(trip.id, vehicles, proposed_price or 0)

        await bot.send_message(
            chat_id=user.telegram_id,
            text=message_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

        await callback.answer()

    except Exception as e:
        logger.error(f"Error showing vehicle selection: {e}")
        await callback.answer("❌ Ошибка при выборе автомобиля", show_alert=True)


@router.callback_query(SelectVehicleCallback.filter())
async def handle_vehicle_selection(callback: CallbackQuery, callback_data: SelectVehicleCallback):
    """Обработчик выбора автомобиля для отклика"""
    async with async_session_maker() as db:
        try:
            trip_id = callback_data.trip_id
            vehicle_id = callback_data.vehicle_id
            proposed_price = callback_data.proposed_price
            user_id = callback.from_user.id

            logger.info(f"Processing vehicle selection for trip {trip_id}, vehicle {vehicle_id} from user {user_id}")

            # Получаем информацию о пользователе
            user_result = await db.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await callback.answer("❌ Пользователь не найден в системе", show_alert=True)
                return

            # Получаем информацию о поездке
            trip_result = await db.execute(
                select(Trip).where(Trip.id == trip_id)
            )
            trip = trip_result.scalar_one_or_none()

            if not trip:
                await callback.answer("❌ Поездка не найдена", show_alert=True)
                return

            # Получаем информацию о выбранном автомобиле
            vehicle_result = await db.execute(
                select(Vehicle)
                .where(Vehicle.id == vehicle_id)
                .where(Vehicle.driver_id == user.id)
                .where(Vehicle.is_active == True)
            )
            vehicle = vehicle_result.scalar_one_or_none()

            if not vehicle:
                await callback.answer("❌ Автомобиль не найден или неактивен", show_alert=True)
                return

            # Проверяем не откликался ли уже пользователь на эту поездку
            existing_response_result = await db.execute(
                select(TripResponse)
                .where(TripResponse.trip_id == trip_id)
                .where(TripResponse.driver_id == user.id)
            )
            existing_response = existing_response_result.scalar_one_or_none()

            if existing_response:
                await callback.answer("❌ Вы уже откликались на эту поездку", show_alert=True)
                return

            # Обновляем статус поездки
            trip.status = TripStatus.PENDING

            # Создаем запись об отклике
            trip_response = TripResponse(
                trip_id=trip_id,
                driver_id=user.id,
                vehicle_id=vehicle.id,
                status=TripResponseStatus.PENDING,
                proposed_price=proposed_price if proposed_price > 0 else None
            )

            db.add(trip_response)
            await db.commit()
            await db.refresh(trip_response)

            # Отправляем уведомление создателю
            await notify_agent_about_response(trip, user, vehicle, proposed_price if proposed_price > 0 else None)

            # Удаляем сообщение с выбором автомобиля
            await callback.message.delete()

            await callback.answer("✅ Ваш отклик отправлен создателю поездки", show_alert=True)
            logger.info(f"User {user.id} responded to trip {trip_id} with selected vehicle {vehicle.id}")

        except Exception as e:
            logger.error(f"Error handling vehicle selection: {e}")
            await callback.answer("❌ Произошла ошибка при обработке выбора", show_alert=True)
            await db.rollback()


async def notify_agent_about_response(trip: Trip, driver: User, vehicle: Vehicle, proposed_price: float = None):
    """Уведомляет агента о новом отклике (общая функция для всех случаев)"""

    car_class = ''
    if vehicle.car_class.value == CarClass.PASSENGER_CAR.value:
        car_class = "легковой авто"
    elif vehicle.car_class.value == CarClass.BUSINESS.value:
        car_class = "бизнес"
    elif vehicle.car_class.value == CarClass.MICROBUS.value:
        car_class = "микроавтобус"
    elif vehicle.car_class.value == CarClass.BUS.value:
        car_class = "автобус"

    driver_info = f"👤 <b>Водитель:</b> {driver.first_name or 'Пользователь'}"
    if driver.username:
        driver_info += f" (@{driver.username})"
    vehicle_info = f"🚗 <b>Авто:</b> {vehicle.color} {vehicle.brand} {vehicle.model} ({car_class}) {vehicle.license_plate}"
    vehicle_info += f"\n⭐ Удобства: {vehicle.additional_info}" if vehicle.additional_info else ""

    trip_info = f"📍 <b>Маршрут:</b> {trip.from_address} → {trip.to_address}"
    trip_info += f"\n🕐 <b>Отправление:</b> {trip.departure_datetime.strftime('%d.%m.%Y %H:%M')}"
    trip_info += f"\n👥 <b>Мест:</b> {trip.total_seats}"

    if proposed_price:
        trip_info += f"\n💰 <b>Цена:</b> {proposed_price} ₽"
    elif trip.price:
        trip_info += f"\n💰 <b>Цена:</b> {trip.price} ₽"

    message_to_creator = (
        f"✅ <b>НОВЫЙ ОТКЛИК НА ВАШУ ПОЕЗДКУ #{trip.id}</b>\n\n"
        f"{driver_info}\n\n"
        f"{vehicle_info}\n\n"
        f"{trip_info}\n\n"
        f"<i>👇 Если водитель вам подходит, отправьте ему контакты</i>"
    )

    # Получаем telegram_id создателя
    async with async_session_maker() as db:
        creator_result = await db.execute(
            select(User.telegram_id).where(User.id == trip.creator_id)
        )
        creator_telegram_id = creator_result.scalar_one()

    # Отправляем сообщение создателю с кнопкой отправки контактов
    await bot.send_message(
        chat_id=creator_telegram_id,
        text=message_to_creator,
        parse_mode=ParseMode.HTML,
        reply_markup=create_share_contacts_keyboard(trip_id=trip.id, driver_id=driver.id, vehicle_id=vehicle.id)
    )


DRIVER_SUBSCRIPTION_1 = "driver_subscription_1_month"
DRIVER_SUBSCRIPTION_3 = "driver_subscription_3_months"
DRIVER_SUBSCRIPTION_12 = "driver_subscription_12_months"

# Конфигурация товаров для подписок
PRODUCTS_CONFIG = {
    DRIVER_SUBSCRIPTION_1: {
        "title": "Подписка PRO на 1 месяц",
        "description": "Доступ к PRO функциям на 30 дней",
        "amount": 29900,
        "currency": "RUB"
    },
    DRIVER_SUBSCRIPTION_3: {
        "title": "Подписка PRO на 3 месяца",
        "description": "Доступ к PRO функции на 90 дней",
        "amount": 84900,
        "currency": "RUB"
    },
    DRIVER_SUBSCRIPTION_12: {
        "title": "Подписка PRO на 1 год",
        "description": "Доступ к PRO функциям на 365 дней",
        "amount": 329900,
        "currency": "RUB"
    }
}



@router.callback_query(F.data.startswith("buy_subscription"))
async def button_buy(callback: types.CallbackQuery):
    """Команда /buy - показывает варианты подписок"""
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="📅 1 месяц - 299 руб",
                    callback_data=DRIVER_SUBSCRIPTION_1
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="📅 3 месяца - 849 руб",
                    callback_data=DRIVER_SUBSCRIPTION_3
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="📅 1 год - 3299 руб",
                    callback_data=DRIVER_SUBSCRIPTION_12
                )
            ]
        ]
    )

    await callback.message.answer(
        "💰 <b>Выберите подписку:</b>\n\n"
        "• <b>PRO на 1 месяц</b> - полный доступ ко всем функциям\n"
        "• <b>PRO на 3 месяца</b> - выгоднее на 5%\n"
        "• <b>PRO на 1 год</b> - выгоднее на 8%\n\n"
        "💡 <i>После оплаты вам будет доступен весь функционал бота</i>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.message(Command("buy"))
async def cmd_buy(message: types.Message):
    """Команда /buy - показывает варианты подписок"""
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="📅 1 месяц - 299 руб",
                    callback_data=DRIVER_SUBSCRIPTION_1
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="📅 3 месяца - 849 руб",
                    callback_data=DRIVER_SUBSCRIPTION_3
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="📅 1 год - 3299 руб",
                    callback_data=DRIVER_SUBSCRIPTION_12
                )
            ]
        ]
    )

    await message.answer(
        "💰 <b>Выберите подписку:</b>\n\n"
        "• <b>PRO на 1 месяц</b> - полный доступ ко всем функциям\n"
        "• <b>PRO на 3 месяца</b> - выгоднее на 5%\n"
        "• <b>PRO на 1 год</b> - выгоднее на 8%\n\n"
        "💡 <i>После оплаты вам будет доступен весь функционал бота</i>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callback_query(F.data.in_(PRODUCTS_CONFIG.keys()))
async def callback_buy_subscription(callback: types.CallbackQuery):
    """Обработчик нажатия на кнопку покупки подписки"""
    try:
        product_id = callback.data

        if product_id not in PRODUCTS_CONFIG:
            await callback.answer("❌ Товар не найден")
            return

        product = PRODUCTS_CONFIG[product_id]
        logger.info(f'{product["amount"]}')

        # Формируем данные для чека (provider_data)
        provider_data = {
            "receipt": {
                "items": [
                    {
                        "description": product['title'],
                        "quantity": 1.00,
                        "amount": {
                            "value": product['amount'] / 100,  # Переводим из копеек в рубли
                            "currency": product['currency']
                        },
                        "vat_code": 1,  # НДС 20%
                        "payment_mode": "full_payment",
                        "payment_subject": "commodity"  # Товар
                    }
                ],
                "tax_system_code": 1  # Общая система налогообложения
            }
        }

        # Отправляем инвойс с данными для чека
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=product['title'],
            description=product['description'],
            payload=product_id,
            provider_token=settings.YOKASSA_TOKEN_LIVE,
            currency=product['currency'],
            prices=[
                LabeledPrice(
                    label=product['title'],
                    amount=product['amount']  # В копейках
                )
            ],
            provider_data=json.dumps(provider_data),  # Добавляем provider_data
            start_parameter=product_id,
            need_name=False,
            need_phone_number=False,
            need_email=True,  # Запрашиваем email для чека
            send_email_to_provider=True,  # Отправляем email провайдеру
            need_shipping_address=False,
            is_flexible=False
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in callback_buy_subscription: {e}")
        await callback.answer("❌ Произошла ошибка при создании счета")


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    """Обработчик pre-checkout запроса"""
    try:
        # Проверяем payload
        if pre_checkout_query.invoice_payload not in PRODUCTS_CONFIG:
            await pre_checkout_query.answer(
                ok=False,
                error_message="Товар не найден"
            )
            return

        # Если все ок - подтверждаем
        await pre_checkout_query.answer(ok=True)

    except Exception as e:
        logger.error(f"Error in pre_checkout_handler: {e}")
        await pre_checkout_query.answer(
            ok=False,
            error_message="Произошла ошибка при обработке запроса"
        )


@router.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    """Обработчик успешного платежа"""
    async with async_session_maker() as db:
        try:
            successful_payment = message.successful_payment

            logger.info(f"✅ Успешный платеж от пользователя {message.from_user.id}")
            logger.info(f"💰 Сумма: {successful_payment.total_amount / 100} {successful_payment.currency}")
            logger.info(f"📦 Товар: {successful_payment.invoice_payload}")

            # Получаем информацию о пользователе
            user_result = await db.execute(
                select(User).where(User.telegram_id == message.from_user.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await message.answer("❌ Пользователь не найден в системе")
                return

            # Определяем тип подписки и количество месяцев
            subscription_map = {
                DRIVER_SUBSCRIPTION_1: 1,
                DRIVER_SUBSCRIPTION_3: 3,
                DRIVER_SUBSCRIPTION_12: 12
            }

            months = subscription_map.get(successful_payment.invoice_payload, 1)

            # Обновляем подписку пользователя
            from datetime import timezone
            current_time = datetime.now(timezone.utc)

            if user.subscription_exp:
                if user.subscription_exp.tzinfo is None:
                    user_subscription_exp = user.subscription_exp.replace(tzinfo=timezone.utc)
                else:
                    user_subscription_exp = user.subscription_exp

                if user_subscription_exp > current_time:
                    new_exp = user_subscription_exp + timedelta(days=30 * months)
                else:
                    new_exp = current_time + timedelta(days=30 * months)
            else:
                new_exp = current_time + timedelta(days=30 * months)

            user.subscription_exp = new_exp
            user.is_verified = True

            # Создаем запись о финансовой операции
            from database.models import FinancialOperation

            operation = FinancialOperation(
                user_id=user.id,
                operation_type=successful_payment.invoice_payload,  # Просто передаем строку
                amount=successful_payment.total_amount / 100,
                description=f"Оплата через Telegram Bot: {PRODUCTS_CONFIG[successful_payment.invoice_payload]['title']}",
                status="completed",
                external_payment_id=successful_payment.telegram_payment_charge_id,
                telegram_payment_charge_id=successful_payment.telegram_payment_charge_id,
                provider_payload=str(successful_payment.model_dump())
            )

            db.add(operation)
            await db.commit()

            display_exp = new_exp.replace(tzinfo=None) if new_exp.tzinfo else new_exp

            await message.answer(
                "🎉 <b>Оплата прошла успешно!</b>\n\n"
                f"✅ <b>Активирована подписка:</b> {PRODUCTS_CONFIG[successful_payment.invoice_payload]['title']}\n"
                f"💳 <b>Сумма:</b> {successful_payment.total_amount / 100} {successful_payment.currency}\n"
                f"📅 <b>Подписка активна до:</b> {display_exp.strftime('%d.%m.%Y %H:%M')}\n\n"
                "Теперь вам доступен весь функционал бота! 🚀",
                parse_mode="HTML"
            )

            logger.info(f"✅ Подписка активирована для пользователя {user.id} на {months} месяцев")

        except Exception as e:
            logger.error(f"Error in successful_payment_handler: {e}")
            await db.rollback()
            await message.answer("❌ Произошла ошибка при активации подписки")
