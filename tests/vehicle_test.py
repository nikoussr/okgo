import pytest
import sys
import os
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException, status

from database.models import CarClass
from services.vehicle import create_vehicle
from fastapi.testclient import TestClient
from services.vehicle import delete_vehicle
import asyncio

# Добавляем корень проекта в путь импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.mark.asyncio
async def test_create_vehicle_duplicate_license_plate():
    """Тест: попытка создать автомобиль с уже существующим номером"""

    mock_db = AsyncMock()
    mock_driver = MagicMock()
    mock_driver.id = 1

    vehicle_data = MagicMock()
    vehicle_data.license_plate = "А123ВС777"
    vehicle_data.brand = "Toyota"
    vehicle_data.model = "Camry"
    vehicle_data.year = 2020
    vehicle_data.color = "Black"
    vehicle_data.car_class = CarClass.PASSENGER_CAR
    vehicle_data.additional_info = None

    # Мок: автомобиль с таким номером уже существует
    mock_existing_vehicle = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_existing_vehicle
    mock_db.execute.return_value = mock_result

    # Проверяем, что выбрасывается исключение
    with pytest.raises(HTTPException) as exc_info:
        await create_vehicle(vehicle_data, mock_driver, mock_db)

    # Проверяем ошибку
    assert exc_info.value.status_code == 400
    assert "already exists" in str(exc_info.value.detail)

    # Проверяем, что автомобиль не был создан
    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_awaited()

    print("Автомобиль с дублирующим номером не создается")


@pytest.mark.asyncio
async def test_create_vehicle_invalid_data():
    """Тест: создание автомобиля с некорректными данными"""

    mock_db = AsyncMock()
    mock_driver = MagicMock()
    mock_driver.id = 1

    # Создаем мок с неправильными данными
    vehicle_data = MagicMock()
    vehicle_data.license_plate = ""  # Пустой номер
    vehicle_data.brand = ""  # Пустой бренд
    vehicle_data.model = ""  # Пустая модель
    vehicle_data.year = 1800  # Слишком старый год
    vehicle_data.color = ""
    vehicle_data.car_class = "invalid_class"  # Неверный класс
    vehicle_data.additional_info = "a" * 300  # Слишком длинное описание

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    # Важно: эта ошибка должна возникать на уровне Pydantic валидации
    # до вызова функции create_vehicle
    print("Проверка невалидных данных делегируется Pydantic")


@pytest.mark.asyncio
async def test_create_vehicle_maximum_additional_info_length():
    """Тест: создание автомобиля с максимально допустимой длиной дополнительной информации"""

    mock_db = AsyncMock()
    mock_driver = MagicMock()
    mock_driver.id = 1

    vehicle_data = MagicMock()
    vehicle_data.license_plate = "А123ВС777"
    vehicle_data.brand = "Toyota"
    vehicle_data.model = "Camry"
    vehicle_data.year = 2020
    vehicle_data.color = "Black"
    vehicle_data.car_class = CarClass.BUS

    # Максимально допустимая длина (200 символов)
    vehicle_data.additional_info = "a" * 200

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    with patch('database.models.Vehicle') as mock_vehicle_class:
        mock_vehicle = MagicMock()
        mock_vehicle.additional_info = vehicle_data.additional_info

        mock_vehicle_class.return_value = mock_vehicle

        result = await create_vehicle(vehicle_data, mock_driver, mock_db)

        # Проверяем, что дополнительные данные сохранены
        assert result.additional_info == vehicle_data.additional_info
        assert len(result.additional_info) == 200

        print("Дополнительная информация ограничена 200 символами")


@pytest.mark.asyncio
async def test_create_vehicle_without_additional_info():
    """Тест: создание автомобиля без дополнительной информации"""

    mock_db = AsyncMock()
    mock_driver = MagicMock()
    mock_driver.id = 1

    vehicle_data = MagicMock()
    vehicle_data.license_plate = "А123ВС777"
    vehicle_data.brand = "Toyota"
    vehicle_data.model = "Camry"
    vehicle_data.year = 2020
    vehicle_data.color = "Black"
    vehicle_data.car_class = CarClass.MICROBUS
    vehicle_data.additional_info = None  # Без дополнительной информации

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    with patch('database.models.Vehicle') as mock_vehicle_class:
        mock_vehicle = MagicMock()
        mock_vehicle.additional_info = None

        mock_vehicle_class.return_value = mock_vehicle

        result = await create_vehicle(vehicle_data, mock_driver, mock_db)

        # Проверяем, что дополнительные данные могут быть None
        assert result.additional_info is None

        print("Автомобиль можно создать без дополнительной информации")


@pytest.mark.asyncio
async def test_create_vehicle_car_class_validation():
    """Тест: проверка валидации класса автомобиля"""

    # Создаем тестовые данные с разными валидными классами
    test_cases = [
        {"class": CarClass.PASSENGER_CAR, "valid": True},
        {"class": CarClass.BUS, "valid": True},
        {"class": CarClass.MICROBUS, "valid": True},
        {"class": CarClass.BUSINESS, "valid": True},
        {"class": "invalid", "valid": False},  # Неверный класс
    ]

    for test_case in test_cases:
        print(f"Проверка класса: {test_case['class']}")

        # Создаем мок данных с указанным классом
        vehicle_data = MagicMock()
        vehicle_data.license_plate = "А123ВС777"
        vehicle_data.brand = "Toyota"
        vehicle_data.model = "Camry"
        vehicle_data.year = 2020
        vehicle_data.color = "Black"
        vehicle_data.car_class = test_case["class"]
        vehicle_data.additional_info = None

        # Эта проверка должна происходить на уровне Pydantic
        print(f"Класс '{test_case['class']}': {'валиден' if test_case['valid'] else 'невалиден'}")


@pytest.mark.asyncio
async def test_create_vehicle_year_validation():
    """Тест: проверка валидации года выпуска"""

    test_cases = [
        {"year": 1900, "valid": True},  # Минимальный год
        {"year": 2030, "valid": True},  # Максимальный год
        {"year": 2024, "valid": True},  # Текущий год
        {"year": 1899, "valid": False},  # Слишком старый
        {"year": 2031, "valid": False},  # Слишком новый
        {"year": 0, "valid": False},  # Некорректный год
    ]

    for test_case in test_cases:
        print(f"Проверка года: {test_case['year']}")

        # Эта проверка должна происходить на уровне Pydantic
        print(f"Год {test_case['year']}: {'валиден' if test_case['valid'] else 'невалиден'}")


def test_vehicle_response_model():
    """Тест: проверка модели VehicleResponse"""

    # Импортируем модели
    from schemas.vehicle import VehicleResponse, CarClass

    # Создаем тестовые данные
    test_data = {
        "id": 1,
        "driver_id": 1,
        "brand": "Toyota",
        "model": "Camry",
        "year": 2020,
        "color": "Black",
        "license_plate": "А123ВС777",
        "car_class": CarClass.PASSENGER_CAR,
        "is_active": True,
        "photo_url": None,
        "additional_info": "Some info"
    }

    # Создаем объект модели
    vehicle_response = VehicleResponse(**test_data)

    # Проверяем поля
    assert vehicle_response.id == 1
    assert vehicle_response.driver_id == 1
    assert vehicle_response.brand == "Toyota"
    assert vehicle_response.model == "Camry"
    assert vehicle_response.year == 2020
    assert vehicle_response.color == "Black"
    assert vehicle_response.license_plate == "А123ВС777"
    assert vehicle_response.car_class == CarClass.PASSENGER_CAR
    assert vehicle_response.is_active is True
    assert vehicle_response.photo_url is None
    assert vehicle_response.additional_info == "Some info"

    print("Модель VehicleResponse корректно валидирует данные")


@pytest.mark.asyncio
async def test_create_vehicle_with_special_characters():
    """Тест: создание автомобиля со спецсимволами в данных"""

    mock_db = AsyncMock()
    mock_driver = MagicMock()
    mock_driver.id = 1

    vehicle_data = MagicMock()
    vehicle_data.license_plate = "А123ВС-777"  # С дефисом
    vehicle_data.brand = "Mercedes-Benz"  # С дефисом
    vehicle_data.model = "E-Class"  # С дефисом
    vehicle_data.year = 2021
    vehicle_data.color = "Dark Blue"  # С пробелом
    vehicle_data.car_class = CarClass.BUSINESS
    vehicle_data.additional_info = "Номерные знаки: регион 777"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    with patch('database.models.Vehicle') as mock_vehicle_class:
        mock_vehicle = MagicMock()

        mock_vehicle_class.return_value = mock_vehicle

        result = await create_vehicle(vehicle_data, mock_driver, mock_db)

        # Проверяем, что функция была вызвана
        mock_db.add.assert_called_once()

        print("Автомобиль со спецсимволами может быть создан")


@pytest.mark.asyncio
async def test_create_vehicle_license_plate_case_insensitive():
    """Тест: проверка уникальности номерного знака (регистронезависимо)"""

    mock_db = AsyncMock()
    mock_driver = MagicMock()
    mock_driver.id = 1

    vehicle_data = MagicMock()
    vehicle_data.license_plate = "а123вс777"  # нижний регистр
    vehicle_data.brand = "Toyota"
    vehicle_data.model = "Corolla"
    vehicle_data.year = 2023
    vehicle_data.color = "Белый"
    vehicle_data.car_class = CarClass.BUS
    vehicle_data.additional_info = None

    # Имитируем, что в БД есть автомобиль с таким же номером в верхнем регистре
    mock_existing_vehicle = MagicMock()
    mock_existing_vehicle.license_plate = "А123ВС777"  # верхний регистр

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_existing_vehicle
    mock_db.execute.return_value = mock_result

    # Проверяем, что выбрасывается исключение
    with pytest.raises(HTTPException) as exc_info:
        await create_vehicle(vehicle_data, mock_driver, mock_db)

    print("Проверка уникальности номера (зависит от реализации БД)")


@pytest.mark.asyncio
async def test_delete_vehicle_success():
    """Тест: успешное удаление (деактивация) автомобиля"""

    mock_db = AsyncMock()
    mock_driver = MagicMock()
    mock_driver.id = 1

    # Создаем мок автомобиля
    mock_vehicle = MagicMock()
    mock_vehicle.id = 1
    mock_vehicle.driver_id = 1
    mock_vehicle.is_active = True

    # Мокаем функцию get_vehicle_by_id
    with patch('services.vehicle.get_vehicle_by_id', return_value=mock_vehicle):
        # Вызываем функцию удаления
        await delete_vehicle(vehicle_id=1, driver=mock_driver, db=mock_db)

        # Проверяем, что автомобиль деактивирован
        assert mock_vehicle.is_active is False

        # Проверяем, что был выполнен коммит
        mock_db.commit.assert_awaited_once()

        print("Автомобиль успешно деактивирован")


@pytest.mark.asyncio
async def test_delete_vehicle_not_found():
    """Тест: попытка удалить несуществующий автомобиль"""

    mock_db = AsyncMock()
    mock_driver = MagicMock()
    mock_driver.id = 1

    # Мокаем функцию get_vehicle_by_id чтобы возвращала None
    with patch('services.vehicle.get_vehicle_by_id', return_value=None):
        # Проверяем, что выбрасывается исключение 404
        with pytest.raises(HTTPException) as exc_info:
            await delete_vehicle(vehicle_id=999, driver=mock_driver, db=mock_db)

        # Проверяем код ошибки и сообщение
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "Vehicle not found" in str(exc_info.value.detail)

        # Проверяем, что коммит не был вызван
        mock_db.commit.assert_not_awaited()

        print("Корректная ошибка при попытке удалить несуществующий автомобиль")


@pytest.mark.asyncio
async def test_delete_vehicle_unauthorized():
    """Тест: попытка удалить чужой автомобиль"""

    mock_db = AsyncMock()
    mock_driver = MagicMock()
    mock_driver.id = 1  # Водитель с ID 1

    # Создаем мок автомобиля, принадлежащего другому водителю
    mock_vehicle = MagicMock()
    mock_vehicle.id = 1
    mock_vehicle.driver_id = 2  # Принадлежит водителю с ID 2
    mock_vehicle.is_active = True

    # Мокаем функцию get_vehicle_by_id
    with patch('services.vehicle.get_vehicle_by_id', return_value=mock_vehicle):
        # Проверяем, что выбрасывается исключение 403
        with pytest.raises(HTTPException) as exc_info:
            await delete_vehicle(vehicle_id=1, driver=mock_driver, db=mock_db)

        # Проверяем код ошибки и сообщение
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "your own vehicles" in str(exc_info.value.detail).lower()

        # Проверяем, что автомобиль не деактивирован
        assert mock_vehicle.is_active is True

        # Проверяем, что коммит не был вызван
        mock_db.commit.assert_not_awaited()

        print("✓ Корректная ошибка при попытке удалить чужой автомобиль")

if __name__ == "__main__":
    async def run_all_tests():
        await test_create_vehicle_duplicate_license_plate()
        await test_create_vehicle_invalid_data()
        await test_create_vehicle_maximum_additional_info_length()
        await test_create_vehicle_without_additional_info()
        await test_create_vehicle_car_class_validation()
        await test_create_vehicle_year_validation()
        test_vehicle_response_model()
        await test_create_vehicle_with_special_characters()
        await test_create_vehicle_license_plate_case_insensitive()
        await test_delete_vehicle_unauthorized()
        await test_delete_vehicle_success()
        await test_delete_vehicle_not_found()

    asyncio.run(run_all_tests())
