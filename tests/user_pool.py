import asyncio
import random
import time
from typing import Dict, List, Optional
import httpx
from datetime import datetime

from tests.nagruzka import TelegramAuthGenerator


class TestUser:
    """Класс тестового пользователя с состоянием и поведением"""

    def __init__(self, user_id: int, auth_generator, base_url: str = "https://xn--80aqak6ae.xn--p1ai/"):
        self.user_id = user_id
        self.auth = auth_generator
        self.base_url = base_url

        # Состояние пользователя
        self.init_data: Optional[str] = None
        self.telegram_id: Optional[int] = None
        self.jwt_token: Optional[str] = None
        self.token_payload: Optional[Dict] = None
        self.is_authenticated: bool = False
        self.session: Optional[httpx.AsyncClient] = None

        # Статистика активности
        self.requests_made: int = 0
        self.successful_requests: int = 0
        self.last_activity: Optional[datetime] = None

        # Для имитации поведения
        self.think_time_min = 0.2  # Минимальное время между действиями
        self.think_time_max = 0.5  # Максимальное время между действиями

    async def initialize(self):
        """Инициализация пользователя - создание initData"""
        self.init_data = self.auth.create_valid_init_data(self.user_id)

        # Извлекаем telegram_id из initData
        parsed = self.auth.decode_init_data(self.init_data)
        if parsed and 'user' in parsed:
            self.telegram_id = parsed['user']['id']

        # Создаем HTTP-клиент с общими настройками
        self.session = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": f"LoadTestBot/1.0 (User{self.user_id})"
            }
        )

    async def authenticate(self) -> bool:
        """
        Полный цикл аутентификации.
        ВСЕГДА возвращает True если пользователь аутентифицирован (даже с ошибками в процессе)
        """
        try:
            print(f"🔍 Пользователь {self.user_id}: telegram_id={self.telegram_id}")

            # Шаг 1: Отправка initData
            auth_payload = {"init_data": self.init_data}

            response = await self.session.post(
                f"{self.base_url}/api/v1/auth/telegram",
                json=auth_payload
            )

            print(f"📥 Ответ: {response.status_code}")

            # СЦЕНАРИЙ 1: УСПЕШНАЯ АУТЕНТИФИКАЦИЯ (200)
            if response.status_code == 200:
                token_data = response.json()
                self.jwt_token = token_data.get("access_token") or token_data.get("token")

                if self.jwt_token:
                    self.is_authenticated = True
                    self.session.headers.update({
                        "Authorization": f"Bearer {self.jwt_token}"
                    })
                    print(f"✅ Пользователь {self.user_id}: Аутентифицирован (200)")
                    return True  # ВАЖНО: возвращаем True

            # СЦЕНАРИЙ 2: ТРЕБУЕТСЯ РЕФЕРАЛЬНЫЙ КОД (403)
            elif response.status_code == 403:
                error_data = response.json()
                if error_data.get("detail").get("code") == "REFERRAL_CODE_REQUIRED":
                    # Вводим реферальный код
                    referral_payload = self.auth.create_referral_payload(self.telegram_id)
                    response2 = await self.session.post(
                        f"{self.base_url}/api/v1/referral",
                        json=referral_payload
                    )

                    if response2.status_code == 200:
                        token_data = response2.json()
                        self.jwt_token = token_data.get("access_token") or token_data.get("token")

                        if self.jwt_token:
                            self.is_authenticated = True
                            self.session.headers.update({
                                "Authorization": f"Bearer {self.jwt_token}"
                            })
                            print(f"✅ Пользователь {self.user_id}: Аутентифицирован с реферальным кодом")
                            return True  # ВАЖНО: возвращаем True

            print(f"❌ Пользователь {self.user_id}: Не удалось аутентифицировать")
            return False

        except Exception as e:
            print(f"❌ Ошибка аутентификации пользователя {self.user_id}: {e}")
            # Даже при ошибке проверяем - может пользователь уже аутентифицирован
            if self.is_authenticated:
                print(f"⚠️  Но is_authenticated=True, возвращаю True")
                return True
            return False

    async def simulate_activity(self, endpoints: List[Dict]):
        """
        Имитация активности пользователя на сайте.

        Args:
            endpoints: Список эндпоинтов для тестирования в формате:
                [
                    {"method": "GET", "path": "/api/profile", "weight": 3},
                    {"method": "GET", "path": "/api/notifications", "weight": 2},
                    {"method": "POST", "path": "/api/action", "weight": 1},
                ]
                weight - относительная вероятность вызова эндпоинта
        """
        if not self.is_authenticated:
            print(f"⚠️ Пользователь {self.user_id} не аутентифицирован, пропускаем")
            return

        # Определяем общий вес для рандомизации
        total_weight = sum(endpoint.get("weight", 1) for endpoint in endpoints)

        # Выбираем случайное количество действий (3-10)
        num_actions = random.randint(10, 14)

        for action_num in range(num_actions):
            # Выбираем случайный эндпоинт с учетом весов
            rand_val = random.uniform(0, total_weight)
            cumulative = 0

            selected_endpoint = None
            for endpoint in endpoints:
                cumulative += endpoint.get("weight", 1)
                if rand_val <= cumulative:
                    selected_endpoint = endpoint
                    break

            if not selected_endpoint:
                selected_endpoint = endpoints[0]

            # Выполняем запрос
            success = await self.call_endpoint(selected_endpoint)

            if success:
                self.successful_requests += 1

            self.requests_made += 1
            self.last_activity = datetime.now()

            # Имитация "раздумий" пользователя
            think_time = random.uniform(self.think_time_min, self.think_time_max)
            await asyncio.sleep(think_time)

    async def call_endpoint(self, endpoint: Dict) -> bool:
        """Вызов конкретного эндпоинта"""
        try:
            method = endpoint.get("method", "GET").upper()
            path = endpoint.get("path", "")
            needs_auth = endpoint.get("auth_required", True)

            headers = {}
            if needs_auth and self.jwt_token:
                headers["Authorization"] = f"Bearer {self.jwt_token}"

            # Добавляем случайные query параметры если нужно
            params = {}
            if endpoint.get("add_random_params"):
                params = {"_t": int(time.time()), "rnd": random.randint(1, 1000)}

            # Для POST запросов добавляем тело
            json_data = None
            if method in ["POST", "PUT", "PATCH"]:
                json_data = endpoint.get("sample_data", {})
                if endpoint.get("randomize_data"):
                    json_data["timestamp"] = int(time.time())
                    json_data["random_value"] = random.randint(1, 1000)

            response = await self.session.request(
                method=method,
                url=f"{self.base_url}{path}",
                params=params,
                json=json_data,
                headers=headers
            )

            # Проверяем успешность
            is_success = 200 <= response.status_code < 300

            if not is_success:
                print(f"⚠️ Пользователь {self.user_id}: {method} {path} - {response.status_code}")

            return is_success

        except Exception as e:
            print(f"❌ Ошибка у пользователя {self.user_id} на {endpoint.get('path')}: {e}")
            return False

    async def cleanup(self):
        """Очистка ресурсов"""
        if self.session:
            await self.session.aclose()


class UserPool:
    """Управление пулом тестовых пользователей"""

    def __init__(self, num_users: int = 10, base_url: str = "https://xn--80aqak6ae.xn--p1ai/"):
        self.num_users = num_users
        self.base_url = base_url
        self.users: List[TestUser] = []

        from config import settings
        # Конфигурация для вашего приложения
        self.bot_token = settings.TELEGRAM_BOT_TOKEN  # Замените на реальный
        self.jwt_secret = settings.JWT_SECRET_KEY # Замените на реальный

        # Определяем эндпоинты для тестирования
        self.endpoints = [
            {"method": "GET", "path": "api/v1/auth/me", "weight": 5, "auth_required": True},
            {"method": "GET", "path": "api/v1/trips/214", "weight": 3, "auth_required": True},
            {"method": "GET", "path": "api/v1/trips/215", "weight": 3, "auth_required": True},
            {"method": "GET", "path": "api/v1/trips/221", "weight": 3, "auth_required": True},
            {"method": "GET", "path": "api/v1/trips/280", "weight": 3, "auth_required": True},
            {"method": "GET", "path": "api/v1/trips/281", "weight": 3, "auth_required": True},
            {"method": "GET", "path": "api/v1/trips/282", "weight": 3, "auth_required": True},
            {"method": "GET", "path": "api/v1/trips/283", "weight": 3, "auth_required": True},
            {"method": "GET", "path": "api/v1/trips/296", "weight": 3, "auth_required": True},
            {"method": "GET", "path": "api/v1/users/1", "weight": 2, "auth_required": True},
            {"method": "GET", "path": "api/v1/users/13", "weight": 2, "auth_required": True},
            {"method": "GET", "path": "api/v1/users/14", "weight": 2, "auth_required": True},
            {"method": "GET", "path": "api/v1/users/15", "weight": 2, "auth_required": True},
            {"method": "GET", "path": "api/v1/users/22", "weight": 2, "auth_required": True},
            {"method": "GET", "path": "api/v1/vehicles", "weight": 1, "auth_required": True},
        ]

    async def initialize_pool(self):
        """Инициализация пула пользователей"""
        print(f"🔄 Инициализация {self.num_users} тестовых пользователей...")

        auth_gen = TelegramAuthGenerator(self.bot_token, self.jwt_secret, self.base_url)

        for i in range(1, self.num_users + 1):
            user = TestUser(i, auth_gen, self.base_url)
            await user.initialize()
            self.users.append(user)

            # Небольшая задержка между созданием пользователей
            await asyncio.sleep(0.1)

        print(f"✅ Создано {len(self.users)} тестовых пользователей")

    async def run_authentication_phase(self):
        """Фаза аутентификации всех пользователей"""
        print("🔐 Запуск фазы аутентификации...")

        auth_tasks = []
        for user in self.users:
            task = asyncio.create_task(user.authenticate())
            auth_tasks.append(task)

            # Задержка между стартом аутентификаций
            await asyncio.sleep(0.5)

        # Ждем завершения всех аутентификаций
        results = await asyncio.gather(*auth_tasks, return_exceptions=True)

        # Считаем успешные
        successful = sum(1 for r in results if r is True)

        # ДИАГНОСТИКА: проверим реальное состояние пользователей
        print(f"\n🔍 ДИАГНОСТИКА ПОСЛЕ АУТЕНТИФИКАЦИИ:")
        actual_auth_count = 0
        for i, user in enumerate(self.users, 1):
            if user.is_authenticated:
                actual_auth_count += 1
                print(f"  ✅ Пользователь {i}: is_authenticated=True, token={'ЕСТЬ' if user.jwt_token else 'НЕТ'}")
            else:
                print(f"  ❌ Пользователь {i}: is_authenticated=False, token={'ЕСТЬ' if user.jwt_token else 'НЕТ'}")
                # Если есть токен но флаг не установлен - исправляем
                if user.jwt_token:
                    print(f"     ⚠️  У пользователя {i} есть токен но is_authenticated=False, исправляю...")
                    user.is_authenticated = True
                    actual_auth_count += 1

        print(f"📊 Аутентификация завершена: {successful}/{len(self.users)} успешно (return True)")
        print(f"📊 Реально аутентифицировано: {actual_auth_count}/{len(self.users)} (is_authenticated=True)")

    async def run_activity_phase(self, duration_seconds: int = 30):
        """Фаза активности пользователей"""
        print(f"🏃 Запуск фазы активности ({duration_seconds} секунд)...")

        # ДИАГНОСТИКА: сколько пользователей аутентифицировано
        auth_count = sum(1 for user in self.users if user.is_authenticated)
        print(f"🔍 Аутентифицировано пользователей для активности: {auth_count}/{len(self.users)}")

        # Выведем список аутентифицированных
        for i, user in enumerate(self.users, 1):
            if user.is_authenticated:
                print(f"  👤 Пользователь {i}: telegram_id={user.telegram_id}, token={user.jwt_token[:20]}...")

        # Запускаем активности всех пользователей
        activity_tasks = []
        for user in self.users:
            if user.is_authenticated:
                print(f"🚀 Запуск активности для пользователя {user.user_id}")
                task = asyncio.create_task(user.simulate_activity(self.endpoints))
                activity_tasks.append(task)

        if not activity_tasks:
            print("⚠️  Нет аутентифицированных пользователей для активности!")
            return

        print(f"🎯 Запущено {len(activity_tasks)} задач активности")

        # Даем пользователям работать заданное время
        await asyncio.sleep(duration_seconds)

        # Отменяем задачи активности
        for task in activity_tasks:
            task.cancel()

        # Ждем завершения отмененных задач
        try:
            await asyncio.gather(*activity_tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass

        print("✅ Фаза активности завершена")

    async def run_load_test(self, auth_first: bool = True, activity_duration: int = 10):
        """
        Запуск полного нагрузочного теста

        Args:
            auth_first: Сначала выполнять аутентификацию
            activity_duration: Длительность фазы активности в секундах
        """
        try:
            await self.initialize_pool()

            if auth_first:
                await self.run_authentication_phase()

            await self.run_activity_phase(activity_duration)

            # Выводим статистику
            await self.print_statistics()

        finally:
            # Очистка ресурсов
            cleanup_tasks = [user.cleanup() for user in self.users]
            await asyncio.gather(*cleanup_tasks)

    async def print_statistics(self):
        """Вывод статистики по тесту"""
        print("\n" + "=" * 50)
        print("📊 СТАТИСТИКА ТЕСТА")
        print("=" * 50)

        total_requests = sum(user.requests_made for user in self.users)
        total_success = sum(user.successful_requests for user in self.users)
        authenticated_users = sum(1 for user in self.users if user.is_authenticated)

        print(f"Всего пользователей: {len(self.users)}")
        print(f"Аутентифицировано: {authenticated_users}")
        print(f"Всего запросов: {total_requests}")
        print(f"Успешных запросов: {total_success}")

        if total_requests > 0:
            success_rate = (total_success / total_requests) * 100
            print(f"Процент успеха: {success_rate:.1f}%")

        print("=" * 50)