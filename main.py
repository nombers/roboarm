from RobotManipulator import RobotManipulator
from scanner import Scanner
import time
import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Импортируем данные из matrix_data.py
try:
    from matrix_data import get_both_matrices, ROWS, COLS
    matrix1, matrix2 = get_both_matrices()
    MATRIX_ROWS = ROWS
    MATRIX_COLS = COLS
except ImportError:
    print("⚠ Файл matrix_data.py не найден. Используем полную матрицу 10x6.")
    matrix1 = [[1 for _ in range(6)] for _ in range(10)]
    matrix2 = [[1 for _ in range(6)] for _ in range(10)]
    MATRIX_ROWS = 10
    MATRIX_COLS = 6

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestType(Enum):
    """Типы тестов"""
    UGI = "ugi"
    VPCH = "vpch"
    UGI_VPCH = "ugi+vpch"
    GENERAL = "general"
    BUFFER = "buffer"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class TubeInfo:
    """Информация о пробирке"""
    barcode: str
    source_pallet: int  # Номер исходного паллета
    row: int
    col: int
    test_type: TestType
    destination_rack: Optional[int] = None
    destination_row: Optional[int] = None
    destination_col: Optional[int] = None


class TestMatrix:
    """Класс для управления матрицей тестов и распределением пробирок по паллетам."""

    def __init__(self, test_types: List[TestType], rack_capacity=(10, 6)):
        if not (2 <= len(test_types) <= 6):
            raise ValueError("Количество типов тестов должно быть от 2 до 6")

        self.test_types = test_types
        self.rack_rows, self.rack_cols = rack_capacity
        self.racks: Dict[TestType, List[List[Optional[TubeInfo]]]] = {}
        self.rack_positions: Dict[TestType, Tuple[int, int]] = {}

        for test_type in test_types:
            self.racks[test_type] = [[None for _ in range(self.rack_cols)]
                                     for _ in range(self.rack_rows)]
            self.rack_positions[test_type] = (0, 0)

        self.tubes: List[TubeInfo] = []
        logger.info(f"Создана матрица тестов для {len(test_types)} типов: {[t.value for t in test_types]}")

    def add_tube(self, tube: TubeInfo) -> bool:
        test_type = tube.test_type

        if test_type not in self.racks:
            logger.warning(f"Тип теста {test_type} не поддерживается")
            return False

        current_row, current_col = self.rack_positions[test_type]

        if current_row >= self.rack_rows:
            logger.warning(f"Паллет для {test_type.value} заполнен!")
            return False

        tube.destination_rack = self.test_types.index(test_type)
        tube.destination_row = current_row
        tube.destination_col = current_col

        self.racks[test_type][current_row][current_col] = tube
        self.tubes.append(tube)

        current_col += 1
        if current_col >= self.rack_cols:
            current_col = 0
            current_row += 1

        self.rack_positions[test_type] = (current_row, current_col)
        return True

    def get_tubes_by_source_pallet(self, pallet_id: int) -> List[TubeInfo]:
        return [tube for tube in self.tubes if tube.source_pallet == pallet_id]

    def print_matrix(self):
        print("\n" + "=" * 100)
        print("МАТРИЦА ТЕСТОВ - РАСПРЕДЕЛЕНИЕ ПО ПАЛЛЕТАМ НАЗНАЧЕНИЯ")
        print("=" * 100)

        for i, test_type in enumerate(self.test_types):
            print(f"\n📦 ПАЛЛЕТ НАЗНАЧЕНИЯ {i}: {test_type.value.upper()}")
            print("-" * 100)

            rack = self.racks[test_type]
            for row_idx, row in enumerate(rack):
                print(f"Ряд {row_idx:2d}: ", end="")
                for tube in row:
                    if tube is None:
                        print("[ПУСТО]".ljust(20), end=" ")
                    else:
                        print(f"{tube.barcode}(П{tube.source_pallet})".ljust(20), end=" ")
                print()

            filled = sum(1 for row in rack for tube in row if tube is not None)
            total = self.rack_rows * self.rack_cols
            print(f"Заполнено: {filled}/{total}")

        print("\n" + "=" * 100)
        print(f"ВСЕГО ПРОБИРОК: {len(self.tubes)}")
        print("=" * 100)


def get_active_positions(matrix):
    """Возвращает список активных позиций (где matrix[i][j] == 1)"""
    positions = []
    for row in range(len(matrix)):
        for col in range(len(matrix[0])):
            if matrix[row][col] == 1:
                positions.append((row, col))
    return positions


async def get_tube_info_async(barcode: str, host: str = "127.0.0.1", port: int = 7114) -> Optional[Dict]:
    """Асинхронный запрос информации о пробирке с сервера ЛИС."""
    url = f"http://{host}:{port}/get_tests"
    payload = {"mes_type": "LA", "tube_barcode": barcode}
    headers = {'Content-Type': 'application/json', 'Accept': '*/*'}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url=url, json=payload, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    result = await response.json()
                    return result
                else:
                    logger.error(f"✗ Ошибка {response.status} для {barcode}")
                    return None
    except asyncio.TimeoutError:
        logger.error(f"✗ Таймаут для {barcode}")
        return None
    except Exception as e:
        logger.error(f"✗ Ошибка для {barcode}: {e}")
        return None


def parse_test_type(response: Optional[Dict]) -> TestType:
    """Определяет тип теста из ответа сервера."""
    if not response or response.get("status") != "success":
        return TestType.ERROR

    test_codes = response.get("test_codes", [])
    if not test_codes:
        return TestType.UNKNOWN

    test_code = test_codes[0].lower()

    test_map = {
        "ugi": TestType.UGI,
        "vpch": TestType.VPCH,
        "ugi+vpch": TestType.UGI_VPCH,
        "general": TestType.GENERAL,
        "buffer": TestType.BUFFER,
        "error": TestType.ERROR,
    }
    return test_map.get(test_code, TestType.UNKNOWN)


async def process_tube_async(barcode: str, source_pallet: int, row: int, col: int,
                             test_matrix: TestMatrix, lis_host: str, lis_port: int):
    """Асинхронно обрабатывает одну пробирку."""
    response = await get_tube_info_async(barcode, lis_host, lis_port)
    test_type = parse_test_type(response)

    tube = TubeInfo(
        barcode=barcode,
        source_pallet=source_pallet,
        row=row,
        col=col,
        test_type=test_type
    )

    if test_type in test_matrix.racks:
        test_matrix.add_tube(tube)


def wait_for_robot_idle(cobot, timeout=30, check_interval=0.1):
    """Ожидает пока робот не станет свободным (IDLE)."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            status = str(cobot.arm.get_robot_status()[1])
            if status == 'RobotStatusEnum.ROBOT_IDLE':
                return True
        except Exception as e:
            logger.error(f"Ошибка при проверке статуса: {e}")
        time.sleep(check_interval)
    logger.warning(f"Таймаут ожидания ({timeout} сек)")
    return False


def move_robot_by_registers(cobot, dx=0, dy=0, dz=0, program_name="Motion"):
    """Перемещает робота используя регистры и программу."""
    try:
        cobot.set_number_register(1, dx)
        cobot.set_number_register(2, dy)
        cobot.set_number_register(3, dz)
        cobot.start_program(program_name)
        
        if wait_for_robot_idle(cobot):
            return True
        else:
            logger.warning("✗ Движение не завершилось вовремя")
            return False
    except Exception as e:
        logger.error(f"✗ Ошибка при движении: {e}")
        return False


def scan_three_positions(scanner, cobot, x, y, z, program_name="Motion"):
    """
    Сканирует три пробирки подряд и возвращает список из трёх баркодов.
    
    Returns:
        List[str]: Список из трёх баркодов или 'NoRead' для каждой позиции
    """
    if not move_robot_by_registers(cobot, dx=x, dy=y, dz=z, program_name=program_name):
        return ['NoRead', 'NoRead', 'NoRead']
    
    try:
        result = scanner.scan(timeout=0.2)
        if result and result != 'NoRead':
            barcodes = result.split(';')
            # Дополняем до 3 элементов если нужно
            while len(barcodes) < 3:
                barcodes.append('NoRead')
            return barcodes[:3]  # Берём только первые 3
        return ['NoRead', 'NoRead', 'NoRead']
    except Exception as e:
        logger.error(f"Ошибка сканирования: {e}")
        return ['NoRead', 'NoRead', 'NoRead']


async def scan_pallet_from_matrix(scanner, cobot, test_matrix: TestMatrix,
                                  pallet_id: int, matrix,
                                  start_position: Tuple[float, float, float],
                                  x_step=20.7, y_step=20.7,
                                  lis_host="127.0.0.1", lis_port=7114,
                                  controller=None):
    """
    Сканирует паллет согласно матрице из matrix_data.py.
    Сканирует по 3 пробирки за раз (колонки 0-2, затем 3-5).
    """
    start_x, start_y, start_z = start_position
    
    logger.info("=" * 80)
    logger.info(f"СКАНИРОВАНИЕ ПАЛЛЕТА #{pallet_id}")
    logger.info("=" * 80)

    tasks = []

    # Проходим по рядам
    for row in range(len(matrix)):
        # Проверка паузы через контроллер
        if controller and not controller.check_pause():
            logger.warning("Сканирование прервано паузой")
            return
        
        # Сканируем колонки 0-2
        if any(matrix[row][col] == 1 for col in range(3)):
            x = start_x + row * x_step
            y = start_y  # Первые три колонки
            z = start_z
            
            logger.info(f"Сканирование П{pallet_id} Ряд {row}, колонки 0-2")
            barcodes_0_2 = scan_three_positions(scanner, cobot, x, y, z)
            
            # Обрабатываем каждую пробирку
            for col in range(3):
                if matrix[row][col] == 1:  # Проверяем что позиция активна в матрице
                    barcode = barcodes_0_2[col]
                    if barcode and barcode != 'NoRead':
                        logger.info(f"  ✓ [{row}][{col}]: {barcode}")
                        task = asyncio.create_task(
                            process_tube_async(barcode, pallet_id, row, col, test_matrix, lis_host, lis_port)
                        )
                        tasks.append(task)
                    else:
                        logger.warning(f"  ✗ [{row}][{col}]: NoRead (ожидалась пробирка)")
        
        # Сканируем колонки 3-5
        if any(matrix[row][col] == 1 for col in range(3, 6)):
            x = start_x + row * x_step
            y = start_y + y_step * 3  # Следующие три колонки
            z = start_z
            
            logger.info(f"Сканирование П{pallet_id} Ряд {row}, колонки 3-5")
            barcodes_3_5 = scan_three_positions(scanner, cobot, x, y, z)
            
            # Обрабатываем каждую пробирку
            for col_offset in range(3):
                col = col_offset + 3
                if matrix[row][col] == 1:  # Проверяем что позиция активна в матрице
                    barcode = barcodes_3_5[col_offset]
                    if barcode and barcode != 'NoRead':
                        logger.info(f"  ✓ [{row}][{col}]: {barcode}")
                        task = asyncio.create_task(
                            process_tube_async(barcode, pallet_id, row, col, test_matrix, lis_host, lis_port)
                        )
                        tasks.append(task)
                    else:
                        logger.warning(f"  ✗ [{row}][{col}]: NoRead (ожидалась пробирка)")

    logger.info(f"\n⏳ Ожидание завершения {len(tasks)} запросов к ЛИС...")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    errors = sum(1 for r in results if isinstance(r, Exception))
    if errors > 0:
        logger.warning(f"⚠ Ошибок при обработке: {errors}/{len(tasks)}")

    logger.info(f"✓ Паллет {pallet_id}: Сканирование завершено")
    logger.info("=" * 80)


def pickup_tube(cobot, x, y, z_safe=149, z_pickup=139, z_up=200):
    """Выполняет захват пробирки."""
    dx, dy, dz = x, y, z_safe
    if not move_robot_by_registers(cobot, dx=dx, dy=dy, dz=dz):
        return False

    cobot.set_DO(2, True)
    time.sleep(0.1)

    dz = z_pickup
    if not move_robot_by_registers(cobot, dx=dx, dy=dy, dz=dz):
        cobot.set_DO(2, False)
        return False
    
    time.sleep(1.0)
    cobot.set_DO(2, False)

    dz = z_up
    if not move_robot_by_registers(cobot, dx=dx, dy=dy, dz=dz):
        cobot.set_DO(2, False)
        return False

    return True


def place_tube(cobot, x, y, z_safe=200, z_drop=146):
    """Размещает пробирку."""
    dx, dy, dz = x, y, z_safe
    if not move_robot_by_registers(cobot, dx=dx, dy=dy, dz=dz):
        return False

    dz = z_drop
    if not move_robot_by_registers(cobot, dx=dx, dy=dy, dz=dz):
        return False

    cobot.set_DO(1, True)
    time.sleep(0.1)
    cobot.set_DO(1, False)
    return True


def move_to_pause_position(cobot, pause_position: Tuple[float, float, float]):
    """Перемещает робота в позицию паузы для замены штатива."""
    x, y, z = pause_position
    logger.info(f"→ Перемещение в позицию паузы: ({x}, {y}, {z})")
    if move_robot_by_registers(cobot, dx=x, dy=y, dz=z):
        logger.info("✓ Робот в позиции паузы")
        return True
    else:
        logger.error("✗ Ошибка перемещения в позицию паузы")
        return False


def wait_for_rack_replacement(rack_id: int, rack_type: str = "назначения", controller=None):
    """
    Останавливает программу и ждёт замены штатива.
    Если передан controller, использует его для ожидания замены через веб.
    Иначе ждёт Enter в консоли.
    """
    if controller:
        # Определяем тип штатива для веб-интерфейса
        rack_type_web = 'both' if 'и' in rack_type else rack_type.split()[0].lower()
        
        print("\n" + "="*100)
        print(f"⚠ ШТАТИВ {rack_type.upper()} #{rack_id} ЗАПОЛНЕН - ТРЕБУЕТСЯ ЗАМЕНА")
        print("="*100)
        print("Замените штатив через веб-интерфейс или нажмите Enter здесь...")
        print("="*100)
        
        # Используем контроллер для ожидания
        if controller.wait_for_rack_replacement(rack_type_web):
            print("✓ Продолжаем работу")
            print("="*100 + "\n")
            return True
        else:
            print("✗ Таймаут замены штатива")
            return False
    else:
        # Старый способ через input()
        print("\n" + "="*100)
        print(f"⚠ ШТАТИВ {rack_type.upper()} #{rack_id} ЗАПОЛНЕН - ТРЕБУЕТСЯ ЗАМЕНА")
        print("="*100)
        print(f"1. Извлеките заполненный штатив {rack_type} #{rack_id}")
        print(f"2. Установите новый пустой штатив {rack_type} #{rack_id}")
        print(f"3. Нажмите Enter для продолжения...")
        print("="*100)
        
        input()
        
        print("✓ Продолжаем работу")
        print("="*100 + "\n")
        return True


def sort_pallet_from_matrix(cobot, test_matrix: TestMatrix,
                            source_pallet_id: int,
                            source_position: Tuple[float, float, float],
                            dest_positions: Dict[int, Tuple[float, float, float]],
                            pause_position: Tuple[float, float, float] = None,
                            rack_capacity: int = 60,
                            tube_spacing_x=20.7, tube_spacing_y=20.7,
                            controller=None):
    """
    Сортирует пробирки с одного паллета согласно матрице тестов.
    
    Args:
        pause_position: Позиция робота во время замены штатива (x, y, z)
        rack_capacity: Максимальная вместимость штатива назначения (по умолчанию 60)
        controller: RobotController для проверки команд из веб-интерфейса
    """
    source_x, source_y, source_z = source_position
    tubes = test_matrix.get_tubes_by_source_pallet(source_pallet_id)

    if not tubes:
        logger.warning(f"На паллете {source_pallet_id} нет пробирок для сортировки")
        return

    print(f"\n{'='*100}")
    print(f"СОРТИРОВКА ПАЛЛЕТА #{source_pallet_id} ({len(tubes)} пробирок)")
    print('='*100)

    # Счётчики заполнения штативов назначения
    rack_fill_count = {}

    for i, tube in enumerate(tubes, 1):
        # Проверка паузы через контроллер
        if controller and not controller.check_pause():
            logger.warning("Сортировка прервана паузой")
            return
        
        print(f"\n[{i}/{len(tubes)}] {tube.barcode} ({tube.test_type.value})")
        print(f"  Из: П{tube.source_pallet} [{tube.row}][{tube.col}]")
        print(f"  В:  П{tube.destination_rack} [{tube.destination_row}][{tube.destination_col}]")

        # Проверяем не заполнен ли штатив назначения
        dest_rack_id = tube.destination_rack
        if dest_rack_id not in rack_fill_count:
            rack_fill_count[dest_rack_id] = 0
        
        # Если штатив заполнен - пауза для замены
        if rack_fill_count[dest_rack_id] >= rack_capacity:
            logger.info(f"Штатив назначения {dest_rack_id} заполнен ({rack_fill_count[dest_rack_id]} пробирок)")
            
            # Перемещаемся в позицию паузы
            if pause_position:
                move_to_pause_position(cobot, pause_position)
            
            # Ждём замены штатива
            if not wait_for_rack_replacement(dest_rack_id, "назначения", controller):
                logger.error("Замена штатива не подтверждена, прерываем сортировку")
                return
            
            # Сбрасываем счётчик
            rack_fill_count[dest_rack_id] = 0
            logger.info("Счётчик штатива сброшен, продолжаем работу")

        pickup_x = source_x + tube.row * tube_spacing_x
        pickup_y = source_y + tube.col * tube_spacing_y

        dest_start = dest_positions.get(tube.destination_rack)
        if dest_start is None:
            logger.error(f"✗ Нет координат для паллета назначения {tube.destination_rack}")
            continue

        dest_x = dest_start[0] + tube.destination_row * tube_spacing_x
        dest_y = dest_start[1] + tube.destination_col * tube_spacing_y

        try:
            if not pickup_tube(cobot, pickup_x, pickup_y, z_safe=source_z):
                print(f"  ✗ Ошибка захвата")
                continue

            if not place_tube(cobot, dest_x, dest_y):
                print(f"  ✗ Ошибка размещения")
                cobot.set_DO(2, False)
                cobot.set_DO(1, True)
                time.sleep(0.5)
                cobot.set_DO(1, False)
                continue

            print(f"  ✓ Успешно")
            
            # Увеличиваем счётчик успешно размещённых пробирок
            rack_fill_count[dest_rack_id] += 1

        except Exception as e:
            logger.error(f"  ✗ Ошибка: {e}")
            try:
                cobot.set_DO(2, False)
                cobot.set_DO(1, True)
                time.sleep(0.5)
                cobot.set_DO(1, False)
            except:
                pass

    print(f"\n{'='*100}")
    print(f"ПАЛЛЕТ #{source_pallet_id} ОБРАБОТАН: {len(tubes)} пробирок")
    print('='*100)


def connect_devices(scanner, cobot):
    """Подключение к устройствам."""
    try:
        print("Подключение к устройствам...")
        cobot.connect()
        scanner.connect()
        print("✓ Все устройства подключены\n")
    except Exception as e:
        print(f"✗ Критическая ошибка подключения: {e}")
        exit(1)


def disconnect_devices(scanner, cobot):
    """Отключение от устройств."""
    print("\nОтключение от устройств...")
    try:
        cobot.disconnect()
    except Exception as e:
        print(f"Ошибка отключения робота: {e}")
    try:
        scanner.disconnect()
    except Exception as e:
        print(f"Ошибка отключения сканера: {e}")
    print("Отключение завершено")


async def main_async():
    """Основная асинхронная функция программы."""
    
    # ========== ИНТЕГРАЦИЯ С ROBOT_CONTROLLER ==========
    from robot_controller import get_controller
    controller = get_controller()
    
    # Устанавливаем что программа запущена
    controller.set_running(True)
    
    logger.info("Программа запущена через robot_controller")

    # ========== КОНФИГУРАЦИЯ ==========
    
    # Типы тестов
    test_types = [
        TestType.UGI,
        TestType.VPCH,
    ]

    # Сервер ЛИС
    LIS_HOST = "127.0.0.1"
    LIS_PORT = 7114

    # Конфигурация паллетов
    # matrix1 и matrix2 загружаются из matrix_data.py
    source_pallets_config = [
        {
            'id': 0,
            'matrix': matrix1,  # ← Используем данные из matrix_data.py
            'scan_position': (175, 280, 200),
            'sort_position': (129, 317, 148),
        }
        # {
        #     'id': 1,
        #     'matrix': matrix2,  # ← Используем данные из matrix_data.py
        #     'scan_position': (175, 500, 200),
        #     'sort_position': (129, 537, 148),
        # },
    ]

    # Паллеты назначения
    dest_positions = {
        0: (-93, 317, 146),   # УГИ
        1: (-315, 317, 146),  # ВПЧ
    }

    # Позиция паузы для замены штатива (робот встаёт в эту позицию)
    PAUSE_POSITION = (-512, 310, 195)  # ← Измени на свою позицию
    
    # Вместимость штатива назначения (по умолчанию 10x6 = 60)
    RACK_CAPACITY = 60

    # Шаги между пробирками
    X_STEP = 20.7
    Y_STEP = 20.7

    # Вывод информации о матрицах
    print("\n" + "=" * 80)
    print("КОНФИГУРАЦИЯ ИЗ matrix_data.py")
    print("=" * 80)
    for config in source_pallets_config:
        active = sum(sum(row) for row in config['matrix'])
        total = len(config['matrix']) * len(config['matrix'][0])
        print(f"Паллет {config['id']}: {active}/{total} активных позиций")
    print("=" * 80)

    # Инициализация устройств
    scanner = Scanner(ip='192.168.124.4', port=6000)
    cobot = RobotManipulator("R1", ip="192.168.124.2")

    connect_devices(scanner, cobot)
    
    try:
        test_matrix = TestMatrix(test_types=test_types, rack_capacity=(10, 6))

        # ========== ФАЗА 1: СКАНИРОВАНИЕ ==========
        print("\n" + "=" * 100)
        print("ФАЗА 1: СКАНИРОВАНИЕ ВСЕХ ПАЛЛЕТОВ")
        print("=" * 100)

        for pallet_config in source_pallets_config:
            pallet_id = pallet_config['id']
            pallet_matrix = pallet_config['matrix']
            scan_pos = pallet_config['scan_position']

            await scan_pallet_from_matrix(
                scanner=scanner,
                cobot=cobot,
                test_matrix=test_matrix,
                pallet_id=pallet_id,
                matrix=pallet_matrix,
                start_position=scan_pos,
                x_step=X_STEP,
                y_step=Y_STEP,
                lis_host=LIS_HOST,
                lis_port=LIS_PORT,
                controller=controller
            )

        test_matrix.print_matrix()

        # ========== ФАЗА 2: СОРТИРОВКА ==========
        print("\n" + "=" * 100)
        print("ФАЗА 2: СОРТИРОВКА ПАЛЛЕТОВ")
        print("=" * 100)

        for pallet_config in source_pallets_config:
            pallet_id = pallet_config['id']
            sort_pos = pallet_config['sort_position']

            sort_pallet_from_matrix(
                cobot=cobot,
                test_matrix=test_matrix,
                source_pallet_id=pallet_id,
                source_position=sort_pos,
                dest_positions=dest_positions,
                pause_position=PAUSE_POSITION,
                rack_capacity=RACK_CAPACITY,
                tube_spacing_x=X_STEP,
                tube_spacing_y=Y_STEP,
                controller=controller
            )

        print("\n" + "=" * 100)
        print("✓ ВСЕ ПАЛЛЕТЫ ОБРАБОТАНЫ УСПЕШНО!")
        print("=" * 100)

    except KeyboardInterrupt:
        print("\n\n⚠ Программа прервана пользователем")
    except Exception as e:
        print(f"\n\n✗ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        controller.set_running(False)
        disconnect_devices(scanner, cobot)


def main():
    """Точка входа."""
    asyncio.run(main_async())


if __name__ == '__main__':
    main()