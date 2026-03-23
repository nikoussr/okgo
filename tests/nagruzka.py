import time
import random
import json
import hmac
import hashlib
from urllib.parse import parse_qs, urlencode
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
import jwt


class TelegramAuthGenerator:
    """
    Генератор валидных данных для аутентификации Telegram WebApp.
    Включает полный цикл: initData -> реферальный код -> JWT токен.
    """

    def __init__(self, bot_token: str, jwt_secret: str, base_url: str = "https://xn--80aqak6ae.xn--p1ai/"):
        """
        Инициализация генератора.

        Args:
            bot_token: Токен вашего Telegram бота
            jwt_secret: Секретный ключ для JWT (должен совпадать с settings.JWT_SECRET_KEY)
            base_url: Базовый URL вашего API
        """
        self.bot_token = bot_token
        self.jwt_secret = jwt_secret
        self.base_url = base_url

        # Примеры имен и фамилий для генерации реалистичных данных
        self.first_names = ["Иван", "Алексей", "Дмитрий", "Сергей", "Михаил", "Андрей",
                            "Анна", "Мария", "Елена", "Ольга", "Наталья", "Татьяна"]
        self.last_names = ["Иванов", "Петров", "Сидоров", "Смирнов", "Кузнецов",
                           "Васильев", "Павлов", "Семенов", "Голубев", "Виноградов"]

    def generate_telegram_user_data(self, user_id: int) -> Dict:
        """Генерация реалистичных данных пользователя Telegram"""
        first_name = random.choice(self.first_names)
        last_name = random.choice(self.last_names)
        username = f"user_{user_id}_{random.randint(1000, 9999)}"

        return {
            "id": user_id,
            "first_name": first_name,
            "last_name": last_name,
            "username": username,
            "language_code": "ru",
            "is_premium": random.choice([True, False]),
            "allows_write_to_pm": True
        }

    def create_valid_init_data(self, user_id: int) -> str:
        """
        Создание валидного initData с правильной подписью.

        Важно: Этот метод должен использовать ТОЧНО ТАКОЙ ЖЕ алгоритм,
        как в вашем validate_telegram_webapp_data()
        """
        # Генерируем данные пользователя
        user_data = self.generate_telegram_user_data(user_id)
        user_json = json.dumps(user_data, separators=(',', ':'))

        # Текущее время и другие параметры
        auth_date = int(time.time())

        # Создаем словарь параметров (как в parse_qs)
        params = {
            'auth_date': str(auth_date),
            'user': user_json,
            # Можно добавить другие параметры если нужно
            # 'query_id': f"query_{random.randint(1000000, 9999999)}",
            # 'chat_type': "sender",
            # 'chat_instance': f"instance_{random.randint(1000000, 9999999)}",
        }

        # Сортируем ключи по алфавиту
        data_check_arr = []
        for key in sorted(params.keys()):
            value = params[key]
            data_check_arr.append(f"{key}={value}")

        data_check_string = '\n'.join(data_check_arr)

        # Вычисляем secret_key = HMAC_SHA256(bot_token, "WebAppData")
        secret_key = hmac.new(
            "WebAppData".encode(),
            self.bot_token.encode(),
            hashlib.sha256
        ).digest()

        # Вычисляем hash = HMAC_SHA256(secret_key, data_check_string)
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        # Добавляем hash к параметрам
        params['hash'] = calculated_hash

        # Преобразуем в строку init_data (как в URL)
        init_data_parts = []
        for key in sorted(params.keys()):
            if key != 'hash':
                init_data_parts.append(f"{key}={params[key]}")

        # Hash всегда последний
        init_data_parts.append(f"hash={params['hash']}")
        init_data = '&'.join(init_data_parts)

        return init_data

    def decode_init_data(self, init_data: str) -> Optional[Dict]:
        """
        Парсинг строки initData для извлечения данных пользователя.
        Аналогично тому, что делает parse_qs в вашем validate_telegram_webapp_data.
        """
        try:
            # Парсим строку init_data (формат: key1=value1&key2=value2...)
            parsed = {}
            for pair in init_data.split('&'):
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    parsed[key] = value

            # Если есть user данные, парсим JSON
            if 'user' in parsed:
                user_data = json.loads(parsed['user'])
                parsed['user'] = user_data

            return parsed
        except Exception as e:
            print(f"Ошибка парсинга initData: {e}")
            return None

    def create_referral_payload(self, telegram_id: int) -> Dict:
        """Создание payload для ввода реферального кода"""
        # В реальном тесте здесь должен быть существующий реферальный код
        # Для теста используем фиксированный или сгенерированный код
        referral_codes = [695088267]

        return {
            "telegram_id": telegram_id,
            "referral_code": random.choice(referral_codes)
        }

    def decode_token(self, token: str) -> Optional[Dict]:
        """Декодирование JWT токена для проверки"""
        try:
            # Используйте тот же алгоритм, что и в вашем приложении
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=["HS256"]  # Измените если используете другой алгоритм
            )
            return payload
        except jwt.PyJWTError as e:
            print(f"Ошибка декодирования токена: {e}")
            return None

    def verify_token_age(self, token: str, max_age_minutes: int = 60) -> bool:
        """Проверка возраста токена"""
        payload = self.decode_token(token)
        if not payload:
            return False

        if 'exp' not in payload:
            return False

        exp_timestamp = payload['exp']
        current_timestamp = int(time.time())

        # Проверяем не истек ли токен
        if exp_timestamp < current_timestamp:
            return False

        # Проверяем возраст токена
        token_age = current_timestamp - (exp_timestamp - (max_age_minutes * 60))
        return token_age >= 0