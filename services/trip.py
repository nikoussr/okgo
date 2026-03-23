from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, or_, and_
from sqlalchemy.orm import joinedload
from fastapi import HTTPException, status
from telegram_bot.core import bot, CHANNEL_ID
from database.models import Trip, Vehicle, User, TripType, TripStatus, TripResponse, TripResponseStatus
from schemas.trip import TripCreate, TripUpdate, TripSearchParams, TripSearchRole
from telegram_bot.handlers import delete_message_from_channel
from telegram_bot.service import TelegramService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_trip(
        trip_data: TripCreate,
        driver: User,
        db: AsyncSession
) -> Trip:
    """Создать новую поездку"""

    if trip_data.trip_type == TripType.DELEGATED:
        if not driver.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have a PRO status. Send /buy to the bot."
            )
        # Создаем поездку
        trip = Trip(
            creator_id=driver.id,  # Создатель - текущий пользователь
            from_address=trip_data.from_address,
            to_address=trip_data.to_address,
            departure_datetime=trip_data.departure_datetime,
            price=trip_data.price,  # Общая цена за поездку
            total_seats=trip_data.total_seats,
            passenger_phone_number=trip_data.passenger_phone_number,
            car_class=trip_data.car_class,
            description=trip_data.description,
            trip_type=trip_data.trip_type or None,
            status=TripStatus.PUBLISHED,
            delegation_commission=trip_data.delegation_commission,
            is_delegation_active=trip_data.is_delegation_active
        )
    else:
        vehicle_id = trip_data.vehicle_id

        # Если указан vehicle_id - проверяем автомобиль
        if vehicle_id:
            # Проверяем что автомобиль принадлежит водителю
            result = await db.execute(
                select(Vehicle)
                .where(Vehicle.id == vehicle_id)
                .where(Vehicle.driver_id == driver.id)
            )
            vehicle = result.scalar_one_or_none()

            if not vehicle:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Vehicle not found or doesn't belong to you"
                )

            if not vehicle.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Vehicle is not active"
                )

            # Берем car_class из vehicle
            car_class = vehicle.car_class
            vehicle_id = vehicle.id
        else:
            vehicle_id = None

        # Создаем поездку
        trip = Trip(
            creator_id=driver.id,  # Создатель - текущий пользователь
            driver_id=driver.id,  # Водитель (если OWN - текущий, иначе None)
            vehicle_id=vehicle_id,
            from_address=trip_data.from_address,
            to_address=trip_data.to_address,
            departure_datetime=trip_data.departure_datetime,
            price=trip_data.price,  # Общая цена за поездку
            total_seats=trip_data.total_seats,
            passenger_phone_number=trip_data.passenger_phone_number,
            delegation_commission=trip_data.delegation_commission,
            car_class=trip_data.car_class or None,
            description=trip_data.description,
            trip_type=trip_data.trip_type,
            status=TripStatus.PUBLISHED,
            is_delegation_active=trip_data.is_delegation_active
        )

    db.add(trip)
    await db.commit()
    await db.refresh(trip)

    # Отправка поездки в телеграм канал
    if trip.trip_type == TripType.DELEGATED and trip.is_delegation_active:
        try:
            telegram_service = TelegramService(bot, CHANNEL_ID)
            channel_message_id = await telegram_service.send_trip_to_channel(trip, driver)
            trip.channel_message_id = channel_message_id
            await db.commit()
            await db.refresh(trip)
        except Exception as e:
            logger.error(f"Failed to send trip {trip.id} to Telegram channel: {e}")
            # Можно добавить отправку уведомления админу или в лог-канал

    return trip


async def search_my_trips_service(
        params: TripSearchParams,
        user: User,
        db: AsyncSession
) -> List[Trip]:
    """Поиск поездок пользователя с фильтрами по роли"""

    # Базовый запрос - зависит от роли
    query = select(Trip)

    # Формируем условия в зависимости от роли
    conditions = []

    if params.role == TripSearchRole.CREATOR:
        # Только поездки, где пользователь создатель
        conditions.append(Trip.creator_id == user.id)

        # Для создателя дополнительно фильтруем по trip_type
        if params.trip_type == TripType.OWN:
            # Собственные поездки создателя
            conditions.append(Trip.driver_id == user.id)
            conditions.append(Trip.trip_type == TripType.OWN)
        elif params.trip_type == TripType.DELEGATED:
            # Делегированные поездки создателя
            conditions.append(Trip.trip_type == TripType.DELEGATED)
        # Если trip_type не указан - все поездки создателя

    elif params.role == TripSearchRole.DRIVER:
        # Только поездки, где пользователь водитель
        conditions.append(Trip.driver_id == user.id)

        # Для водителя дополнительно фильтруем по trip_type
        if params.trip_type == TripType.OWN:
            # Собственные поездки водителя (он же и создатель)
            conditions.append(Trip.creator_id == user.id)
            conditions.append(Trip.trip_type == TripType.OWN)
        elif params.trip_type == TripType.DELEGATED:
            # Принятые делегированные поездки (водитель != создатель)
            conditions.append(Trip.creator_id != user.id)
            conditions.append(Trip.trip_type == TripType.DELEGATED)
        # Если trip_type не указан - все поездки водителя


    else:  # TripSearchRole.ALL
        # Все поездки пользователя
        # Базовое условие: пользователь должен быть либо создателем, либо водителем
        base_condition = or_(
            Trip.creator_id == user.id,
            Trip.driver_id == user.id
        )
        if params.trip_type:
            # Если указан тип поездки, добавляем дополнительную логику
            if params.trip_type == TripType.OWN:
                # Для OWN: пользователь должен быть И создателем И водителем
                conditions.append(Trip.creator_id == user.id)
                conditions.append(Trip.driver_id == user.id)
                conditions.append(Trip.trip_type == TripType.OWN)
            elif params.trip_type == TripType.DELEGATED:
                # Для DELEGATED: пользователь создатель ИЛИ водитель
                conditions.append(Trip.trip_type == TripType.DELEGATED)
                conditions.append(base_condition)
        else:
            # Если тип не указан, объединяем все три варианта
            conditions.append(
                or_(
                    # Собственные поездки
                    and_(
                        Trip.creator_id == user.id,
                        Trip.driver_id == user.id,
                        Trip.trip_type == TripType.OWN
                    ),
                    # Делегированные поездки как водитель
                    and_(
                        Trip.driver_id == user.id,
                        Trip.trip_type == TripType.DELEGATED
                    )
                )
            )

    # Применяем все условия
    if conditions:
        query = query.where(and_(*conditions))

    # Фильтр по статусу
    if params.status:
        query = query.where(Trip.status == params.status)

    # Фильтр по активности делегирования
    if params.is_delegation_active is not None:
        query = query.where(Trip.is_delegation_active == params.is_delegation_active)

    # Сортировка по дате создания (сначала новые)
    query = query.order_by(Trip.created_at.desc())

    # Пагинация
    query = query.offset(params.skip).limit(params.limit)

    # Загружаем связи
    query = query.options(
        joinedload(Trip.creator),
        joinedload(Trip.driver),
        joinedload(Trip.vehicle)
    )

    result = await db.execute(query)
    trips = result.unique().scalars().all()

    return list(trips)


async def get_trip_by_id(trip_id: int, db: AsyncSession) -> Optional[Trip]:
    """Получить поездку по ID"""
    result = await db.execute(
        select(Trip)
        .where(Trip.id == trip_id)
        .options(joinedload(Trip.driver), joinedload(Trip.vehicle))
    )
    return result.scalar_one_or_none()


async def update_trip(
        trip_id: int,
        trip_data: TripUpdate,
        driver: User,
        db: AsyncSession
) -> Trip:
    """Обновить поездку"""
    from datetime import datetime, timezone

    trip = await get_trip_by_id(trip_id, db)

    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip not found"
        )

    if trip.driver_id != driver.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own trips"
        )

    # Проверяем, активируется ли делегирование
    is_activating_delegation = (
            (trip_data.trip_type == TripType.DELEGATED and
             trip_data.is_delegation_active is True) or
            (trip_data.is_delegation_active is True and
             trip_data.trip_type == TripType.DELEGATED)
    )

    # Проверяем подписку при активации делегирования
    if is_activating_delegation and not driver.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Для делегирования поездки необходима активная PRO подписка"
        )

    # Сохраняем старые значения
    old_trip_type = trip.trip_type
    old_is_delegation_active = trip.is_delegation_active
    old_departure_time = trip.departure_datetime  # Сохраняем старое время отправления

    # Обновляем поля
    update_data = trip_data.model_dump(exclude_unset=True)

    # Применяем обновления
    for field, value in update_data.items():
        setattr(trip, field, value)

    # Проверяем, нужно ли отправлять в канал
    should_send_to_channel = (
            trip.trip_type == TripType.DELEGATED and
            trip.is_delegation_active and
            (old_trip_type != TripType.DELEGATED or
             not old_is_delegation_active)
    )

    # Проверяем, что дата поездки не в прошлом (для всех обновлений)
    current_time = datetime.now(timezone.utc)

    # Используем новое время, если оно было обновлено, иначе старое
    departure_time_to_check = trip.departure_datetime if 'departure_datetime' in update_data else old_departure_time

    if departure_time_to_check and departure_time_to_check < current_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Невозможно обновить поездку с датой в прошлом"
        )

    # Очищаем driver_id при активации делегирования
    if should_send_to_channel:
        # Дополнительная проверка для делегирования
        if not trip.departure_datetime or trip.departure_datetime < current_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Невозможно делегировать поездку с датой в прошлом"
            )

        trip.driver_id = None
        logger.info(f"Trip {trip.id} driver_id cleared for delegation")

    await db.commit()
    await db.refresh(trip)

    # Отправка в телеграм канал
    if should_send_to_channel:
        try:
            telegram_service = TelegramService(bot, CHANNEL_ID)

            if not trip.channel_message_id:
                driver_info = await db.execute(
                    select(User).where(User.id == trip.creator_id)
                )
                creator = driver_info.scalar_one_or_none()

                # Финальная проверка перед отправкой
                if not trip.departure_datetime or trip.departure_datetime < current_time:
                    logger.error(f"Cannot send trip {trip.id} to channel: departure time is in the past")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Невозможно отправить поездку в канал: дата поездки в прошлом"
                    )

                channel_message_id = await telegram_service.send_trip_to_channel(trip, creator)
                trip.channel_message_id = channel_message_id
                await db.commit()
                await db.refresh(trip)

                logger.info(f"Trip {trip.id} sent to channel, message_id: {channel_message_id}")

        except HTTPException:
            # Пробрасываем HTTPException дальше
            raise
        except Exception as e:
            logger.error(f"Failed to send trip {trip.id} to Telegram channel: {e}")
            # Можно также вернуть ошибку пользователю или оставить как есть
            # Откатываем изменения driver_id если отправка не удалась
            trip.driver_id = driver.id
            trip.is_delegation_active = False
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка при отправке поездки в канал: {str(e)}"
            )

    return trip


async def delete_trip(trip_id: int, driver: User, db: AsyncSession) -> dict:
    """Удалить/отменить поездку"""
    trip = await get_trip_by_id(trip_id, db)

    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip not found"
        )

    # Проверяем что пользователь является создателем поездки
    if trip.creator_id != driver.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own trips"
        )

    try:
        # Получаем все отклики на поездку
        responses = await get_trip_responses(trip_id, db)

        # Проверяем есть ли подтвержденные отклики (отправленные контакты)
        confirmed_responses = [r for r in responses if r.status == TripResponseStatus.ACCEPTED]

        if confirmed_responses:
            # Есть подтвержденные отклики - удалять нельзя
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete trip with confirmed responses (contacts already sent)"
            )

        # Если есть неподтвержденные отклики или их нет вообще - можно удалять
        has_responses = len(responses) > 0

        # Удаляем все связанные отклики (если есть)
        if has_responses:
            await db.execute(
                delete(TripResponse).where(TripResponse.trip_id == trip_id)
            )
            logger.info(f"Deleted {len(responses)} responses for trip {trip_id}")

        # Удаляем сообщение из канала (если есть)
        message_deleted = False
        if trip.channel_message_id:
            try:
                await delete_message_from_channel(message_id=trip.channel_message_id)
                message_deleted = True
                logger.info(f"Message {trip.channel_message_id} deleted from channel")
            except Exception as e:
                logger.warning(f"Failed to delete message from channel: {e}")
                message_deleted = False

        # Удаляем саму поездку
        await db.delete(trip)
        await db.commit()

        logger.info(f"Trip {trip_id} successfully deleted")

        # Возвращаем детальную информацию для фронтенда
        return {
            "status": True,
            "message": "Trip deleted successfully",
            "details": {
                "trip_id": trip_id,
                "responses_deleted": len(responses) if has_responses else 0,
                "channel_message_deleted": message_deleted,
                "deletion_type": "full" if has_responses else "simple"
            }
        }

    except HTTPException:
        # Перебрасываем уже созданные HTTPException
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting trip {trip_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete trip"
        )


async def get_trip_responses(trip_id: int, db: AsyncSession) -> List[TripResponse]:
    """Получить все отклики на поездку"""
    result = await db.execute(
        select(TripResponse).where(TripResponse.trip_id == trip_id)
    )
    return result.scalars().all()
