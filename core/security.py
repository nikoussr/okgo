import hmac
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from fastapi import HTTPException, status
from urllib.parse import parse_qs


def validate_telegram_webapp_data(init_data: str, bot_token: str) -> Dict[str, Any]:
    """
    Валидирует данные от Telegram WebApp.
    Документация: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    try:
        # Парсим init_data
        parsed_data = parse_qs(init_data)

        # Извлекаем hash
        received_hash = parsed_data.get('hash', [None])[0]
        if not received_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing hash in init_data"
            )

        # Создаем data_check_string (все параметры кроме hash, отсортированные по ключу)
        data_check_arr = []
        for key in sorted(parsed_data.keys()):
            if key != 'hash':
                value = parsed_data[key][0]
                data_check_arr.append(f"{key}={value}")

        data_check_string = '\n'.join(data_check_arr)
        # Вычисляем secret_key = HMAC_SHA256(bot_token, "WebAppData")
        secret_key = hmac.new(
            "WebAppData".encode(),
            bot_token.encode(),
            hashlib.sha256
        ).digest()

        # Вычисляем hash = HMAC_SHA256(secret_key, data_check_string)
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        # Сравниваем хэши
        if not hmac.compare_digest(calculated_hash, received_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid hash - data validation failed"
            )

        # Проверяем auth_date (данные не должны быть старше 1 часа)
        auth_date = parsed_data.get('auth_date', [None])[0]
        if auth_date:
            auth_timestamp = int(auth_date)
            current_timestamp = int(datetime.now().timestamp())
            if current_timestamp - auth_timestamp > 3600:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Init data is too old"
                )

        # Парсим user данные
        user_data_str = parsed_data.get('user', [None])[0]
        if not user_data_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing user data"
            )

        user_data = json.loads(user_data_str)

        return {
            'telegram_id': user_data.get('id'),
            'username': user_data.get('username'),
            'first_name': user_data.get('first_name'),
            'last_name': user_data.get('last_name'),
            'is_premium': user_data.get('is_premium', False),
        }

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user data format"
        )
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Telegram data validation failed: {str(e)}"
        )


def create_access_token(data: dict, secret_key: str, algorithm: str, expires_delta: Optional[timedelta] = None) -> str:
    """Создает JWT токен"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=1440)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)

    return encoded_jwt


def decode_access_token(token: str, secret_key: str, algorithm: str) -> Dict[str, Any]:
    """Декодирует JWT токен"""
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
