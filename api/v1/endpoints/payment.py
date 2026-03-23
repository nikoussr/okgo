'''from typing import Any, Dict
import enum
import hmac
import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from database.session import get_async_session
from api.deps import get_current_user
from database.models import User, FinancialOperation, FinancialOperationType
from services.payment import PaymentService, SubscriptionService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Секретный ключ для проверки подписи webhook (должен совпадать с настройками в YooKassa)
WEBHOOK_SECRET = "test_nXT2WY8pxaxfhIsworp1_f-Ni2uXhis_BfPyENzMpqI"


@router.post("/create")
async def create_payment(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    """
    Создать платеж для подписки (фиксированная сумма)
    """
    payment_service = PaymentService(db)

    # Фиксированная сумма подписки
    subscription_amount = 490.00
    description = "Оформление подписки на 30 дней"

    return await payment_service.create_payment(
        user_id=current_user.id,
        amount=subscription_amount,
        description=description,
    )


@router.get("/status/{payment_id}")
async def get_payment_status(
        payment_id: str,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    """
    Проверка статуса платежа
    """
    payment_service = PaymentService(db)
    return await payment_service.check_payment_status(payment_id)


@router.get("/subscription/status")
async def get_subscription_status(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
):
    """
    Получить статус подписки текущего пользователя
    """
    subscription_service = SubscriptionService(db)
    return await subscription_service.get_subscription_status(current_user)


@router.post("/webhook/yookassa")
async def yookassa_webhook(
        request: Request,
        db: AsyncSession = Depends(get_async_session),
        yookassa_signature: str = Header(None, alias="HTTP_YOOKASSA_SIGNATURE")
):
    """
    Webhook для получения уведомлений от YooKassa
    """
    try:
        # Получаем тело запроса как строку для логирования
        body_bytes = await request.body()
        body_str = body_bytes.decode('utf-8')

        # Парсим JSON
        notification_data = json.loads(body_str)

        # Логируем полученное уведомление
        logger.info(f"📨 Получен webhook от YooKassa: {notification_data.get('event')}")
        logger.info(f"📄 Данные webhook: {json.dumps(notification_data, ensure_ascii=False, indent=2)}")

        # В тестовом режиме можно пропустить проверку подписи
        # await _verify_webhook_signature(body_bytes, yookassa_signature)

        # Обрабатываем уведомление
        payment_service = PaymentService(db)
        success = await payment_service.handle_payment_notification(notification_data)

        if success:
            logger.info("✅ Webhook успешно обработан")
            return {"status": "success"}
        else:
            logger.error("❌ Ошибка обработки webhook")
            raise HTTPException(status_code=400, detail="Ошибка обработки уведомления")

    except json.JSONDecodeError as e:
        logger.error(f"❌ Ошибка парсинга JSON webhook: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"❌ Ошибка обработки webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Ошибка: {str(e)}")


async def _verify_webhook_signature(body_bytes: bytes, signature: str) -> bool:
    """
    Проверяет подпись webhook от YooKassa
    """
    try:
        # Создаем подпись из тела запроса
        expected_signature = hmac.new(
            WEBHOOK_SECRET.encode('utf-8'),
            body_bytes,
            hashlib.sha256
        ).hexdigest()

        # Сравниваем подписи
        if not hmac.compare_digest(expected_signature, signature):
            logger.error("Неверная подпись webhook от YooKassa")
            raise HTTPException(status_code=401, detail="Invalid signature")

        return True

    except Exception as e:
        logger.error(f"Ошибка проверки подписи: {str(e)}")
        raise HTTPException(status_code=401, detail="Signature verification failed")
'''