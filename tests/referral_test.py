import pytest
import sys
import os
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta, timezone

from database.models import UserRole

# Добавляем корень проекта в путь импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException, status



@pytest.mark.asyncio
async def test_create_referral_success():
    """Тест успешного создания реферальной записи"""

    mock_db = AsyncMock()

    # Создаем моки пользователей
    mock_referrer = MagicMock()
    mock_referrer.id = 100
    mock_referrer.telegram_id = 123456789  # Это referral_code
    mock_referrer.subscription_exp = None
    mock_referrer.is_verified = False

    mock_user = MagicMock()
    mock_user.id = 200
    mock_user.subscription_exp = None
    mock_user.is_verified = False

    # Мок запроса к БД для поиска реферера
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_referrer
    mock_db.execute.return_value = mock_result

    # Мок для проверки существующей реферальной записи
    existing_referral_result = MagicMock()
    existing_referral_result.scalar_one_or_none.return_value = None
    mock_db.execute.side_effect = [
        mock_result,  # Первый вызов: поиск реферера
        existing_referral_result  # Второй вызов: проверка существующей записи
    ]

    from services.referral import create_referral
    from database.models import Referral

    # Вызываем функцию
    referral = await create_referral(
        referral_code=123456789,  # telegram_id реферера
        user=mock_user,
        db=mock_db
    )

    # Проверяем что referral создан
    assert isinstance(referral, Referral)

    # Проверяем что db.add был вызван с Referral
    assert mock_db.add.called

    # Проверяем что подписки обновлены
    assert mock_user.is_verified is True
    assert mock_referrer.is_verified is True

    # Проверяем что подписка продлена на 7 дней
    assert mock_user.subscription_exp is not None
    assert mock_referrer.subscription_exp is not None

    # Проверяем commit
    assert mock_db.commit.called

    print("Тест успешного создания реферальной записи пройден!")


@pytest.mark.asyncio
async def test_create_referral_user_not_found():
    """Тест создания реферала когда реферер не найден"""

    mock_db = AsyncMock()
    mock_user = MagicMock()
    mock_user.id = 200

    # Мок: реферер не найден
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    from services.referral import create_referral

    # Проверяем что выбрасывается исключение
    with pytest.raises(HTTPException) as exc_info:
        await create_referral(
            referral_code=999999999,  # Несуществующий telegram_id
            user=mock_user,
            db=mock_db
        )

    assert exc_info.value.status_code == 404
    assert "не найден" in exc_info.value.detail

    print("Тест создания реферала когда реферер не найден пройден!")


@pytest.mark.asyncio
async def test_create_referral_self_referral():
    """Тест создания реферала самого себя"""

    mock_db = AsyncMock()

    # Пользователь пытается пригласить сам себя
    mock_user = MagicMock()
    mock_user.id = 100
    mock_user.telegram_id = 123456789

    # Мок: поиск реферера возвращает того же пользователя
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    from services.referral import create_referral

    with pytest.raises(HTTPException) as exc_info:
        await create_referral(
            referral_code=123456789,  # Свой же telegram_id
            user=mock_user,
            db=mock_db
        )

    assert exc_info.value.status_code == 400
    assert "собственный реферальный код" in exc_info.value.detail

    print("Тест создания реферала самого себя пройден!")


@pytest.mark.asyncio
async def test_create_referral_already_used():
    """Тест когда пользователь уже использовал реферальный код"""

    mock_db = AsyncMock()

    mock_referrer = MagicMock()
    mock_referrer.id = 100
    mock_referrer.telegram_id = 123456789

    mock_user = MagicMock()
    mock_user.id = 200

    # Мок для поиска реферера
    mock_referrer_result = MagicMock()
    mock_referrer_result.scalar_one_or_none.return_value = mock_referrer

    # Мок для проверки существующего реферала (возвращает существующую запись)
    mock_existing_referral = MagicMock()
    mock_existing_result = MagicMock()
    mock_existing_result.scalar_one_or_none.return_value = mock_existing_referral

    mock_db.execute.side_effect = [
        mock_referrer_result,  # Поиск реферера
        mock_existing_result  # Проверка существующего реферала
    ]

    from services.referral import create_referral

    with pytest.raises(HTTPException) as exc_info:
        await create_referral(
            referral_code=123456789,
            user=mock_user,
            db=mock_db
        )

    assert exc_info.value.status_code == 400
    assert "уже использовали реферальный код" in exc_info.value.detail

    print("Тест когда пользователь уже использовал реферальный код пройден!")


@pytest.mark.asyncio
async def test_create_referral_with_existing_subscription():
    """Тест создания реферала когда у пользователей уже есть подписки"""

    mock_db = AsyncMock()

    # Создаем даты подписок
    existing_date = datetime.now(timezone.utc) + timedelta(days=10)

    mock_referrer = MagicMock()
    mock_referrer.id = 100
    mock_referrer.telegram_id = 123456789
    mock_referrer.subscription_exp = existing_date  # Уже есть подписка
    mock_referrer.is_verified = True

    mock_user = MagicMock()
    mock_user.id = 200
    mock_user.subscription_exp = existing_date  # Уже есть подписка
    mock_user.is_verified = True

    # Моки для запросов
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_referrer
    mock_db.execute.return_value = mock_result

    existing_referral_result = MagicMock()
    existing_referral_result.scalar_one_or_none.return_value = None
    mock_db.execute.side_effect = [
        mock_result,
        existing_referral_result
    ]

    from services.referral import create_referral

    referral = await create_referral(
        referral_code=123456789,
        user=mock_user,
        db=mock_db
    )

    # Проверяем что подписки продлены на 7 дней
    expected_date = existing_date + timedelta(days=7)
    assert mock_user.subscription_exp == expected_date
    assert mock_referrer.subscription_exp == expected_date

    print("Тест создания реферала когда у пользователей уже есть подписки пройден!")


@pytest.mark.asyncio
async def test_get_user_referrer_true():
    """Тест когда у пользователя есть реферер"""

    mock_db = AsyncMock()

    # Мок существующего реферала
    mock_referral = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_referral
    mock_db.execute.return_value = mock_result

    from services.referral import get_user_referrer

    result = await get_user_referrer(user_id=123, db=mock_db)

    assert result is True

    # Проверяем что execute был вызван
    assert mock_db.execute.called

    # Получаем переданный запрос
    call = mock_db.execute.call_args
    query = call[0][0]  # Первый аргумент - это query

    # Проверяем что это SELECT запрос к таблице referrals
    assert "SELECT" in str(query)
    assert "referrals" in str(query)
    assert "WHERE" in str(query)

    print("Тест когда у пользователя есть реферер пройден!")


@pytest.mark.asyncio
async def test_get_user_referrer_false():
    """Тест когда у пользователя нет реферера"""

    mock_db = AsyncMock()

    # Мок: реферал не найден
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    from services.referral import get_user_referrer

    result = await get_user_referrer(user_id=123, db=mock_db)

    assert result is False

    print("Тест когда у пользователя нет реферера пройден!")


@pytest.mark.asyncio
async def test_referral_router_create_success():
    """Тест успешного создания реферала через роутер"""

    mock_db = AsyncMock()

    # Мок пользователя
    mock_user = MagicMock()
    mock_user.id = 200
    mock_user.telegram_id = 695088267
    mock_user.username = "test_user"
    mock_user.first_name = "Test"
    mock_user.last_name = "User"
    mock_user.role = UserRole.DRIVER
    mock_user.phone_number = "+79991234567"
    mock_user.is_active = True
    mock_user.is_verified = True
    mock_user.subscription_exp = None
    mock_user.sbp_bank = "Т-Банк"
    mock_user.sbp_phone_number = "+79991234567"
    mock_user.organization = None
    mock_user.rating_avg = 0.0
    mock_user.rating_count = 0
    mock_user.created_at = datetime.now()
    mock_user.updated_at = datetime.now()

    # Мок реферера
    mock_referrer = MagicMock()
    mock_referrer.id = 100
    mock_referrer.telegram_id = 123456789

    # Мок реферальной записи
    mock_referral = MagicMock()

    # Настраиваем моки для запросов
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = mock_user

    referral_check_result = MagicMock()
    referral_check_result.scalar_one_or_none.return_value = None

    mock_db.execute.side_effect = [
        user_result,  # Поиск пользователя
        referral_check_result  # Проверка существующего реферала
    ]

    # Мок create_referral
    with patch('api.v1.endpoints.referrals.create_referral') as mock_create:
        mock_create.return_value = mock_referral

        # Мок create_access_token
        with patch('api.v1.endpoints.referrals.create_access_token') as mock_token:
            mock_token.return_value = "fake_jwt_token"

            from api.v1.endpoints.referrals import create_referral_public
            from schemas.referral import ReferralPublicCreate

            # Создаем данные для запроса
            referral_data = ReferralPublicCreate(
                telegram_id=695088267,
                referral_code=123456789
            )

            # Вызываем эндпоинт
            result = await create_referral_public(referral_data, mock_db)

            # Проверяем результат
            assert result.access_token == "fake_jwt_token"
            assert result.token_type == "bearer"
            assert result.user.id == 200

            print("Тест успешного создания реферала через роутер пройден!")


@pytest.mark.asyncio
async def test_referral_router_user_not_found():
    """Тест когда пользователь не найден через роутер"""

    mock_db = AsyncMock()

    # Мок: пользователь не найден
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    from api.v1.endpoints.referrals import create_referral_public
    from schemas.referral import ReferralPublicCreate
    from fastapi import HTTPException

    referral_data = ReferralPublicCreate(
        telegram_id=999999999,  # Несуществующий telegram_id
        referral_code=123456789
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_referral_public(referral_data, mock_db)

    assert exc_info.value.status_code == 404
    assert "Пользователь не найден" in str(exc_info.value.detail)

    print("Тест когда пользователь не найден через роутер пройден!")


@pytest.mark.asyncio
async def test_get_my_referrer_success():
    """Тест успешного получения информации о реферере"""

    mock_db = AsyncMock()
    mock_user = MagicMock()
    mock_user.id = 123

    # Мок get_user_referrer возвращает True
    with patch('api.v1.endpoints.referrals.get_user_referrer') as mock_get_referrer:
        mock_get_referrer.return_value = True

        from api.v1.endpoints.referrals import get_my_referrer

        result = await get_my_referrer(user=mock_user, db=mock_db)

        assert result["has_referrer"] is True
        assert "использовали реферальный код" in result["message"]

        print("Тест успешного получения информации о реферере пройден!")


@pytest.mark.asyncio
async def test_get_my_referrer_not_found():
    """Тест когда у пользователя нет реферера"""

    mock_db = AsyncMock()
    mock_user = MagicMock()
    mock_user.id = 123

    with patch('api.v1.endpoints.referrals.get_user_referrer') as mock_get_referrer:
        mock_get_referrer.return_value = False

        from api.v1.endpoints.referrals import get_my_referrer
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_my_referrer(user=mock_user, db=mock_db)

        assert exc_info.value.status_code == 404
        assert "не использовали реферальный код" in exc_info.value.detail

        print("Тест когда у пользователя нет реферера пройден!")


if __name__ == "__main__":
    import asyncio

    async def run_all_tests():
        tests = [
            ("Создание реферала", test_create_referral_success),
            ("Реферер не найден", test_create_referral_user_not_found),
            ("Реферал самого себя", test_create_referral_self_referral),
            ("Уже использован код", test_create_referral_already_used),
            ("С существующей подпиской", test_create_referral_with_existing_subscription),
            ("Есть реферер", test_get_user_referrer_true),
            ("Нет реферера", test_get_user_referrer_false),
            ("Роутер: успешное создание", test_referral_router_create_success),
            ("Роутер: пользователь не найден", test_referral_router_user_not_found),
            ("Получение реферера: успех", test_get_my_referrer_success),
            ("Получение реферера: не найден", test_get_my_referrer_not_found),
        ]
    asyncio.run(run_all_tests())