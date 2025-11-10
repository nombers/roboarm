"""
Тестовый HTTP-сервер для эмуляции ответов ЛИС
Возвращает рандомные типы тестов: УГИ, ВПЧ, УГИ+ВПЧ, общий анализ, буфер, ошибки
Логика похожа на TCP-сервер с протоколом обмена сообщениями
"""
from aiohttp import web
import random
import logging
from datetime import datetime
import asyncio

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TestLISServer:
    """Класс тестового сервера ЛИС"""

    def __init__(self):
        self.request_count = 0

    async def handle_get_tests(self, request):
        """Обработчик POST-запроса /get_tests"""
        self.request_count += 1

        try:
            data = await request.json()
            barcode = data.get("tube_barcode", "")
            mes_type = data.get("mes_type", "")

            logger.info(f"Запрос #{self.request_count}: barcode={barcode}, mes_type={mes_type}")

            if not barcode:
                return web.json_response({
                    "status": "error",
                    "error_code": "MISSING_BARCODE",
                    "message": "Не указан штрихкод"
                }, status=400)

            # Имитация задержки
            delay = random.choice([0, 0, 0, 1, 2])
            if delay > 0:
                logger.info(f"Имитация задержки: {delay} сек")
                await asyncio.sleep(delay)

            # Случайный выбор типа ответа
            response_type = random.choice([
                "ugi", "vpch"
            ])

            # Формирование правильного ответа
            if response_type == "ugi":
                response_data = {
                    "status": "success",
                    "tube_barcode": barcode,
                    "test_codes": ["ugi"],
                    "tests": [{"code": "УГИ", "name": "Урогенитальные инфекции"}]
                }
                status = 200
            elif response_type == "vpch":
                response_data = {
                    "status": "success",
                    "tube_barcode": barcode,
                    "test_codes": ["vpch"],
                    "tests": [{"code": "ВПЧ", "name": "Вирус папилломы человека"}]
                }
                status = 200
            elif response_type == "ugi+vpch":
                response_data = {
                    "status": "success",
                    "tube_barcode": barcode,
                    "test_codes": ["ugi+vpch"],
                    "tests": [
                        {"code": "УГИ", "name": "Урогенитальные инфекции + Вирус папилломы человека"}
                    ]
                }
                status = 200
            elif response_type == "general":
                response_data = {
                    "status": "success",
                    "tube_barcode": barcode,
                    "test_codes": ["general"],
                    "tests": [{"code": "ОАК", "name": "Общий анализ крови"}]
                }
                status = 200
            elif response_type == "buffer":
                response_data = {
                    "status": "success",
                    "tube_barcode": barcode,
                    "test_codes": ["buffer"],
                    "message": "Пробирка в обработке"
                }
                status = 200
            else:  # error
                response_data = {
                    "status": "success",
                    "tube_barcode": barcode,
                    "test_codes": ["error"],
                    "message": "Пробирка не найдена в системе"
                }
                status = 200

            logger.info(
                f"Ответ #{self.request_count}: тип={response_type}, статус={status}, "
                f"тесты={response_data.get('test_codes', 'N/A')}"
            )

            return web.json_response(response_data, status=status)

        except Exception as e:
            logger.error(f"Ошибка обработки запроса: {e}")
            return web.json_response({
                "status": "error",
                "error_code": "SERVER_ERROR",
                "message": str(e)
            }, status=500)

        except Exception as e:
            logger.error(f"Ошибка обработки запроса: {e}")
            return web.json_response({
                "status": "error",
                "error_code": "SERVER_ERROR",
                "message": str(e)
            }, status=500)

    async def handle_health(self, request):
        """Проверка работоспособности сервера"""
        return web.json_response({
            "status": "ok",
            "server": "Test LIS Server",
            "requests_processed": self.request_count,
            "timestamp": datetime.now().isoformat()
        })

def create_app():
    """Создание приложения aiohttp"""
    server = TestLISServer()
    app = web.Application()

    # Маршруты
    app.router.add_post('/get_tests', server.handle_get_tests)
    app.router.add_get('/health', server.handle_health)

    return app


if __name__ == '__main__':
    print("=" * 70)
    print("ТЕСТОВЫЙ СЕРВЕР ЛИС")
    print("=" * 70)
    print("\nЗапуск на http://0.0.0.0:7114")
    print("=" * 70)


    app = create_app()
    web.run_app(app, host='0.0.0.0', port=7114)
