from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.models import Trip


class AcceptTripCallback(CallbackData, prefix="accept_trip"):
    trip_id: int


class ShareContactsCallback(CallbackData, prefix="share_contacts"):
    """Callback для кнопки отправки контактов"""
    trip_id: int
    driver_id: int


class PriceActionCallback(CallbackData, prefix="price_action"):
    trip_id: int
    action: str  # increase, decrease, accept
    current_price: int


class SelectVehicleCallback(CallbackData, prefix="select_vehicle"):
    """Callback для выбора автомобиля при отклике"""
    trip_id: int
    vehicle_id: int
    proposed_price: float = 0  # Для передачи предложенной цены


def create_accept_trip_keyboard(trip: Trip, current_price: float) -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопкой принятия поездки"""
    builder = InlineKeyboardBuilder()
    print(trip.price)
    if trip.price:
        builder.row(InlineKeyboardButton(
            text="✅ Откликнуться",
            callback_data=f"accept_trip:{trip.id}"
        ))
    else:
        builder.row(
            InlineKeyboardButton(
                text="⬆️ +500₽",
                callback_data=PriceActionCallback(
                    trip_id=trip.id,
                    action="increase",
                    current_price=current_price
                ).pack()
            ),
            InlineKeyboardButton(
                text="✅ Откликнуться",
                callback_data=PriceActionCallback(
                    trip_id=trip.id,
                    action="accept",
                    current_price=current_price
                ).pack()
            ),
            InlineKeyboardButton(
                text="⬇️ -500₽",
                callback_data=PriceActionCallback(
                    trip_id=trip.id,
                    action="decrease",
                    current_price=current_price
                ).pack()
            )
        )
    return builder.as_markup()


def create_share_contacts_keyboard(trip_id: int, driver_id: int, vehicle_id: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру с кнопкой отправки контактов"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📞 Отправить контакты",
        callback_data=f"share_contacts:{trip_id}:{driver_id}:{vehicle_id}"
    )
    return builder.as_markup()


def create_vehicle_selection_keyboard(trip_id: int, vehicles: list, proposed_price: float = 0) -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора автомобиля"""
    builder = InlineKeyboardBuilder()

    for vehicle in vehicles:
        vehicle_text = f"{vehicle.brand} {vehicle.model} ({vehicle.license_plate})"
        builder.button(
            text=vehicle_text,
            callback_data=SelectVehicleCallback(
                trip_id=trip_id,
                vehicle_id=vehicle.id,
                proposed_price=proposed_price
            ).pack()
        )

    builder.adjust(1)  # По одной кнопке в строке
    return builder.as_markup()
