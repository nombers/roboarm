"""
Тестовый HTTP-сервер для эмуляции ответов ЛИС
Возвращает рандомные типы тестов: pcr-1 (УГИ), pcr-2 (ВПЧ), pcr (Разное)
"""
from aiohttp import web
import random
import logging
from datetime import datetime
import asyncio

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
            delay = random.choice([0, 0, 0, 1])
            if delay > 0:
                await asyncio.sleep(delay)

            # Случайный выбор типа ответа
            response_type = random.choice([
                "pcr-1",           # только УГИ
                "pcr-2",           # только ВПЧ
                "pcr-1+pcr-2",     # УГИ + ВПЧ
                "pcr"              # разное
            ])

            # Формирование правильного ответа
            if response_type == "pcr-1":
                response_data = {
                    "status": "success",
                    "tube_barcode": barcode,
                    "test_codes": ["pcr-1"],
                    "tests": [{"code": "pcr-1", "name": "УГИ"}]
                }
            elif response_type == "pcr-2":
                response_data = {
                    "status": "success",
                    "tube_barcode": barcode,
                    "test_codes": ["pcr-2"],
                    "tests": [{"code": "pcr-2", "name": "ВПЧ"}]
                }
            elif response_type == "pcr-1+pcr-2":
                response_data = {
                    "status": "success",
                    "tube_barcode": barcode,
                    "test_codes": ["pcr-1", "pcr-2"],
                    "tests": [
                        {"code": "pcr-1", "name": "УГИ"},
                        {"code": "pcr-2", "name": "ВПЧ"}
                    ]
                }
            else:  # pcr
                response_data = {
                    "status": "success",
                    "tube_barcode": barcode,
                    "test_codes": ["pcr"],
                    "tests": [{"code": "pcr", "name": "Разное"}]
                }

            logger.info(
                f"Ответ #{self.request_count}: тип={response_type}, "
                f"тесты={response_data.get('test_codes', 'N/A')}"
            )

            return web.json_response(response_data, status=200)

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