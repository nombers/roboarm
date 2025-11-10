"""
Функции для отправки HTTP-запросов на сервер ЛИС
"""
from typing import Optional, Dict, Any
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Асинхронная версия (для использования с asyncio/aiohttp)

import aiohttp
import asyncio


async def get_tube_info_async(barcode: str, host: str = "192.168.12.80", port: int = 7117) -> Optional[Dict]:
    """
    Асинхронная версия функции для получения информации о пробирке

    Args:
        barcode: Штрихкод пробирки
        host: IP-адрес сервера
        port: Порт сервера

    Returns:
        Словарь с информацией или None

    Example:
        #>>> result = await get_tube_info_async("2806086100")
    """
    url = f"http://{host}:{port}/get_tests"

    payload = {
        "mes_type": "LA",
        "tube_barcode": barcode
    }

    headers = {
        'Content-Type': 'application/json',
        'Accept': '*/*'
    }

    try:
        # Вывод информации о запросе в консоль
        logger.info(f"Отправка запроса на {url}")
        logger.info(f"Payload: {payload}")
        logger.info(f"Headers: {headers}")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                    url=url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=20)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"Получен ответ для {barcode}: {result}")
                    return result
                else:
                    logger.error(f"Ошибка {response.status}: {await response.text()}")
                    return None

    except asyncio.TimeoutError:
        logger.error(f"Таймаут при запросе баркода {barcode}")
        return None

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return None


# Примеры использования

if __name__ == "__main__":
    # Пример 4: Асинхронный запрос
    print("\n4. Асинхронный запрос:")

    async def test_async():
        result = await get_tube_info_async("888999111")
        print(f"Асинхронный результат: {result}")


    asyncio.run(test_async())  # Раскомментируйте для запуска

    print("\n" + "=" * 60)