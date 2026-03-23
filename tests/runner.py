#!/usr/bin/env python3
"""
Основной скрипт для запуска нагрузочного тестирования.
"""
import asyncio
import argparse
from user_pool import UserPool


async def main():
    parser = argparse.ArgumentParser(description="Запуск нагрузочного тестирования")
    parser.add_argument("--users", type=int, default=100, help="Количество пользователей")
    parser.add_argument("--duration", type=int, default=30, help="Длительность теста в секундах")
    parser.add_argument("--url", type=str, default="https://xn--80aqak6ae.xn--p1ai/",
                        help="Базовый URL API")
    parser.add_argument("--skip-auth", action="store_true",
                        help="Пропустить фазу аутентификации")

    args = parser.parse_args()

    print(f"""
🚀 ЗАПУСК НАГРУЗОЧНОГО ТЕСТИРОВАНИЯ
================================
Количество пользователей: {args.users}
Длительность: {args.duration} секунд
URL API: {args.url}
Пропуск аутентификации: {args.skip_auth}
================================
    """)

    # Создаем и запускаем пул пользователей
    pool = UserPool(num_users=args.users, base_url=args.url)

    await pool.run_load_test(
        auth_first=not args.skip_auth,
        activity_duration=args.duration
    )


if __name__ == "__main__":
    asyncio.run(main())