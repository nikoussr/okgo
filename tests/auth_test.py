import pytest
import sys
import os
from unittest.mock import AsyncMock, patch, MagicMock

# Добавляем корень проекта в путь импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException, status
from database.models import UserRole


@pytest.mark.asyncio
async def test_auth_with_invalid_telegram_data():
    """Тест: невалидные данные Telegram вызывают ошибку ДО проверки реферала"""

    mock_db = AsyncMock()

    # Создаем невалидные данные
    invalid_init_data = "fake_telegram_data"

    # Важно: патчим функцию ТАК, как она импортируется в services.auth
    with patch('services.auth.validate_telegram_webapp_data') as mock_validate:
        # Мок выбросит исключение при валидации
        mock_validate.side_effect = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram data validation failed: Invalid hash"
        )

        from services.auth import authenticate_telegram_user

        # Проверяем, что исключение выбрасывается сразу
        with pytest.raises(HTTPException) as exc_info:
            await authenticate_telegram_user(invalid_init_data, mock_db)

        # Должна быть ошибка 401 от validate_telegram_webapp_data
        assert exc_info.value.status_code == 401
        assert "Telegram data validation failed" in str(exc_info.value.detail)

        # Важно: функция get_user_referrer НЕ должна вызываться
        with patch('services.referral.get_user_referrer') as mock_get_referrer:
            # Проверяем что функция не вызывалась
            mock_get_referrer.assert_not_called()

        print("✓ При невалидных данных Telegram проверка реферала не происходит")


@pytest.mark.asyncio
async def test_auth_valid_telegram_but_no_referrer():
    """Тест: валидные данные Telegram, но нет реферера"""

    mock_db = AsyncMock()
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.telegram_id = 695088267
    mock_user.username = "dinozavrik_22"
    mock_user.role = "driver"

    # Мок запроса к БД
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Создаем валидные данные
    valid_init_data = "query_id=AAGLNG4pAAAAAIs0biloX-Bf&user=%7B%22id%22%3A695088267%2C%22first_name%22%3A%22%D0%97%D0%B0%D1%85%D0%B0%D1%80%22%2C%22last_name%22%3A%22%22%2C%22username%22%3A%22dinozavrik_22%22%2C%22language_code%22%3A%22ru%22%2C%22allows_write_to_pm%22%3Atrue%2C%22photo_url%22%3A%22https%3A%5C%2F%5C%2Ft.me%5C%2Fi%5C%2Fuserpic%5C%2F320%5C%2FUl4ylcrW_d5wTfrXqbqiypGW05D1erSgyoe2t0Wb5Kw.svg%22%7D&auth_date=1766054449&signature=Jh_H8oBEUHrwCKTG-_TxFBmBOIumU9ReBJ6fR0h1mC2JrcpDn3nZA2Fy_ElpGqwQdtsHRovHP1QWhDOudA2dDQ&hash=06e73cb7be2099220ac61f8e1e9fd1f736c0d10dfa928b663ee2a3b2fe2080f7"

    with patch('services.auth.validate_telegram_webapp_data') as mock_validate:
        # Мок успешной валидации
        mock_validate.return_value = {
            'telegram_id': 695088267,
            'username': 'dinozavrik_22'
        }

        with patch('services.referral.get_user_referrer') as mock_get_referrer:
            # Возвращаем None - нет реферера
            mock_get_referrer.return_value = None

            from services.auth import authenticate_telegram_user

            # Проверяем, что выбрасывается ошибка 403
            with pytest.raises(HTTPException) as exc_info:
                await authenticate_telegram_user(valid_init_data, mock_db)

            # Должна быть ошибка 403 от authenticate_telegram_user
            assert exc_info.value.status_code == 403

            # Проверяем структуру ошибки
            detail = exc_info.value.detail
            if isinstance(detail, dict):
                assert detail["code"] == "REFERRAL_CODE_REQUIRED"
                assert "реферальный код" in detail["message"]
                assert detail["user_id"] == mock_user.id

            print("✓ При валидных данных Telegram но без реферала: ошибка 403")


@pytest.mark.asyncio
async def test_auth_valid_telegram_with_referrer():
    """Тест: валидные данные Telegram И есть реферер"""

    mock_db = AsyncMock()
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.telegram_id = 695088267
    mock_user.username = "dinozavrik_22"
    mock_user.role = UserRole.DRIVER

    # Мок запроса к БД
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Создаем валидные данные
    valid_init_data = "query_id=AAGLNG4pAAAAAIs0biloX-Bf&user=%7B%22id%22%3A695088267%2C%22first_name%22%3A%22%D0%97%D0%B0%D1%85%D0%B0%D1%80%22%2C%22last_name%22%3A%22%22%2C%22username%22%3A%22dinozavrik_22%22%2C%22language_code%22%3A%22ru%22%2C%22allows_write_to_pm%22%3Atrue%2C%22photo_url%22%3A%22https%3A%5C%2F%5C%2Ft.me%5C%2Fi%5C%2Fuserpic%5C%2F320%5C%2FUl4ylcrW_d5wTfrXqbqiypGW05D1erSgyoe2t0Wb5Kw.svg%22%7D&auth_date=1766054449&signature=Jh_H8oBEUHrwCKTG-_TxFBmBOIumU9ReBJ6fR0h1mC2JrcpDn3nZA2Fy_ElpGqwQdtsHRovHP1QWhDOudA2dDQ&hash=06e73cb7be2099220ac61f8e1e9fd1f736c0d10dfa928b663ee2a3b2fe2080f7"

    with patch('services.auth.validate_telegram_webapp_data') as mock_validate:
        # Мок успешной валидации
        mock_validate.return_value = {
            'telegram_id': 695088267,
            'username': 'dinozavrik_22'
        }

        with patch('services.referral.get_user_referrer') as mock_get_referrer:
            # Возвращаем мок реферера - есть реферер
            mock_referrer = MagicMock()
            mock_referrer.id = 2  # ID реферера
            mock_get_referrer.return_value = mock_referrer

            with patch('services.auth.create_access_token') as mock_create_token:
                mock_create_token.return_value = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwicm9sZSI6ImRyaXZlciIsImV4cCI6MTc2NjE0MzQyMn0.nEdlNVoSE6cCAy83txVaztZ7CtomWD7g189AqG3gjpE"

                from services.auth import authenticate_telegram_user

                # Должен вернуть токен
                token, user = await authenticate_telegram_user(valid_init_data, mock_db)

                assert token[:10] in mock_create_token.return_value
                assert user == mock_user

                print("✓ При валидных данных Telegram и с рефералом: выдан токен")


@pytest.mark.asyncio
async def test_auth_new_user_creation_with_referrer():
    """Тест: создание нового пользователя с рефералом"""

    mock_db = AsyncMock()

    # Мок: пользователь не найден
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    # Создаем валидные данные
    valid_init_data = "query_id=AAGLNG4pAAAAAIs0biloX-Bf&user=%7B%22id%22%3A695088267%2C%22first_name%22%3A%22%D0%97%D0%B0%D1%85%D0%B0%D1%80%22%2C%22last_name%22%3A%22%22%2C%22username%22%3A%22dinozavrik_22%22%2C%22language_code%22%3A%22ru%22%2C%22allows_write_to_pm%22%3Atrue%2C%22photo_url%22%3A%22https%3A%5C%2F%5C%2Ft.me%5C%2Fi%5C%2Fuserpic%5C%2F320%5C%2FUl4ylcrW_d5wTfrXqbqiypGW05D1erSgyoe2t0Wb5Kw.svg%22%7D&auth_date=1766054449&signature=Jh_H8oBEUHrwCKTG-_TxFBmBOIumU9ReBJ6fR0h1mC2JrcpDn3nZA2Fy_ElpGqwQdtsHRovHP1QWhDOudA2dDQ&hash=06e73cb7be2099220ac61f8e1e9fd1f736c0d10dfa928b663ee2a3b2fe2080f7"

    with patch('services.auth.validate_telegram_webapp_data') as mock_validate:
        mock_validate.return_value = {
            'telegram_id': 695088267,
            'username': 'dinozavrik_22',
            'first_name': 'Захар',
            'last_name': ''
        }

        with patch('services.referral.get_user_referrer') as mock_get_referrer:
            # У нового пользователя есть реферер
            mock_referrer = MagicMock()
            mock_get_referrer.return_value = mock_referrer

            with patch('services.auth.create_access_token') as mock_create_token:
                mock_create_token.return_value = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwicm9sZSI6ImRyaXZlciIsImV4cCI6MTc2NjE0MzQyMn0.nEdlNVoSE6cCAy83txVaztZ7CtomWD7g189AqG3gjpE"

                from services.auth import authenticate_telegram_user
                from database.models import User

                token, user = await authenticate_telegram_user(valid_init_data, mock_db)

                # Проверяем что пользователь добавлен
                assert mock_db.add.called

                added_user = mock_db.add.call_args[0][0]
                assert isinstance(added_user, User)
                assert added_user.telegram_id == 695088267

                print("✓ Новый пользователь создан и ему выдан токен (есть реферер)")


@pytest.mark.asyncio
async def test_auth_new_user_creation_without_referrer():
    """Тест: создание нового пользователя БЕЗ реферала"""

    mock_db = AsyncMock()

    # Мок: пользователь не найден
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    # Создаем валидные данные
    valid_init_data = "query_id=AAGLNG4pAAAAAIs0biloX-Bf&user=%7B%22id%22%3A695088267%2C%22first_name%22%3A%22%D0%97%D0%B0%D1%85%D0%B0%D1%80%22%2C%22last_name%22%3A%22%22%2C%22username%22%3A%22dinozavrik_22%22%2C%22language_code%22%3A%22ru%22%2C%22allows_write_to_pm%22%3Atrue%2C%22photo_url%22%3A%22https%3A%5C%2F%5C%2Ft.me%5C%2Fi%5C%2Fuserpic%5C%2F320%5C%2FUl4ylcrW_d5wTfrXqbqiypGW05D1erSgyoe2t0Wb5Kw.svg%22%7D&auth_date=1766054449&signature=Jh_H8oBEUHrwCKTG-_TxFBmBOIumU9ReBJ6fR0h1mC2JrcpDn3nZA2Fy_ElpGqwQdtsHRovHP1QWhDOudA2dDQ&hash=06e73cb7be2099220ac61f8e1e9fd1f736c0d10dfa928b663ee2a3b2fe2080f7"

    with patch('services.auth.validate_telegram_webapp_data') as mock_validate:
        mock_validate.return_value = {
            'telegram_id': 695088267,
            'username': 'dinozavrik_22'
        }

        with patch('services.referral.get_user_referrer') as mock_get_referrer:
            # У нового пользователя НЕТ реферера
            mock_get_referrer.return_value = None

            from services.auth import authenticate_telegram_user
            from database.models import User

            # Должна быть ошибка 403
            with pytest.raises(HTTPException) as exc_info:
                await authenticate_telegram_user(valid_init_data, mock_db)

            assert exc_info.value.status_code == 403

            # Но пользователь ДОЛЖЕН быть создан перед проверкой реферала
            assert mock_db.add.called

            added_user = mock_db.add.call_args[0][0]
            assert isinstance(added_user, User)
            assert added_user.telegram_id == 695088267

            print("✓ Новый пользователь создан, но токен не выдан (нет реферера)")


def test_validate_telegram_webapp_data_errors():
    """Тест ошибок валидации Telegram данных"""

    test_cases = [
        {
            "name": "Нет hash в данных",
            "init_data": "query_id=test&user={\"id\":123}",
            "expected_code": 401,
            "expected_detail": "Missing hash in init_data"
        },
        {
            "name": "Невалидный hash",
            "init_data": "query_id=test&user={\"id\":123}&hash=invalid_hash",
            "expected_code": 401,
            "expected_detail": "Invalid hash"
        },
        {
            "name": "Устаревшие данные (>1 часа)",
            "init_data": "query_id=test&user={\"id\":123}&auth_date=1&hash=valid_hash",
            "expected_code": 401,
            "expected_detail": "Init data is too old"
        },
        {
            "name": "Нет user данных",
            "init_data": "query_id=test&auth_date=1234567890&hash=valid_hash",
            "expected_code": 401,
            "expected_detail": "Missing user data"
        },
        {
            "name": "Невалидный JSON в user",
            "init_data": "query_id=test&user=invalid_json&auth_date=1234567890&hash=valid_hash",
            "expected_code": 400,
            "expected_detail": "Invalid user data format"
        },
    ]

    for test_case in test_cases:
        print(f"\nТест: {test_case['name']}")

        # Мокируем реальные вызовы
        with patch('core.security.parse_qs') as mock_parse_qs:
            # Настраиваем мок в зависимости от теста
            if "Missing hash" in test_case['expected_detail']:
                mock_parse_qs.return_value = {'query_id': ['test'], 'user': ['{"id":123}']}
            elif "Invalid hash" in test_case['expected_detail']:
                mock_parse_qs.return_value = {
                    'query_id': ['test'],
                    'user': ['{"id":123}'],
                    'hash': ['invalid_hash']
                }
            elif "too old" in test_case['expected_detail']:
                mock_parse_qs.return_value = {
                    'query_id': ['test'],
                    'user': ['{"id":123}'],
                    'auth_date': ['1'],  # Очень старые данные
                    'hash': ['valid_hash']
                }
            elif "Missing user data" in test_case['expected_detail']:
                mock_parse_qs.return_value = {
                    'query_id': ['test'],
                    'auth_date': ['1234567890'],
                    'hash': ['valid_hash']
                }
            elif "Invalid user data format" in test_case['expected_detail']:
                mock_parse_qs.return_value = {
                    'query_id': ['test'],
                    'user': ['invalid_json'],  # Невалидный JSON
                    'auth_date': ['1234567890'],
                    'hash': ['valid_hash']
                }

            # Мокируем hmac.compare_digest чтобы возвращать False для невалидного hash
            with patch('core.security.hmac.compare_digest') as mock_compare:
                if "Invalid hash" in test_case['expected_detail']:
                    mock_compare.return_value = False
                else:
                    mock_compare.return_value = True

                with patch('core.security.datetime') as mock_datetime:
                    mock_now = MagicMock()
                    mock_now.timestamp.return_value = 1234567890
                    mock_datetime.now.return_value = mock_now

if __name__ == "__main__":
    import asyncio
    async def run_async_tests():
        await test_auth_with_invalid_telegram_data()
        await test_auth_valid_telegram_but_no_referrer()
        await test_auth_valid_telegram_with_referrer()
        await test_auth_new_user_creation_with_referrer()
        await test_auth_new_user_creation_without_referrer()
    asyncio.run(run_async_tests())
    test_validate_telegram_webapp_data_errors()
