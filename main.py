from RobotManipulator import RobotManipulator
from scanner import Scanner
import time
import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
    row: int
    col: int
    test_type: TestType
    destination_rack: Optional[int] = None  # Номер паллета назначения
    destination_row: Optional[int] = None  # Ряд на паллете назначения
    destination_col: Optional[int] = None  # Столбец на паллете назначения


class TestMatrix:
    """
    Класс для управления матрицей тестов и распределением пробирок по паллетам.

    Поддерживает от 2 до 6 типов тестов, каждый тест соответствует отдельному паллету.
    """

    def __init__(self, test_types: List[TestType], rack_capacity=(10, 6)):
        """
        Args:
            test_types: Список типов тестов (от 2 до 6)
            rack_capacity: Размерность паллета (строки, столбцы)
        """
        if not (2 <= len(test_types) <= 6):
            raise ValueError("Количество типов тестов должно быть от 2 до 6")

        self.test_types = test_types
        self.rack_rows, self.rack_cols = rack_capacity

        # Создаём паллеты для каждого типа теста
        # Ключ - TestType, значение - матрица с TubeInfo или None
        self.racks: Dict[TestType, List[List[Optional[TubeInfo]]]] = {}
        self.rack_positions: Dict[TestType, Tuple[int, int]] = {}  # (текущий_ряд, текущий_столбец)

        for test_type in test_types:
            self.racks[test_type] = [[None for _ in range(self.rack_cols)]
                                     for _ in range(self.rack_rows)]
            self.rack_positions[test_type] = (0, 0)

        # Список всех пробирок
        self.tubes: List[TubeInfo] = []

        logger.info(f"Создана матрица тестов для {len(test_types)} типов: {[t.value for t in test_types]}")

    def add_tube(self, tube: TubeInfo) -> bool:
        """
        Добавляет пробирку в соответствующий паллет.

        Returns:
            True если добавлено успешно, False если паллет заполнен
        """
        test_type = tube.test_type

        if test_type not in self.racks:
            logger.warning(f"Тип теста {test_type} не поддерживается")
            return False

        # Находим свободное место на паллете
        current_row, current_col = self.rack_positions[test_type]

        # Проверяем, есть ли свободное место
        if current_row >= self.rack_rows:
            logger.warning(f"Паллет для {test_type.value} заполнен!")
            return False

        # Добавляем пробирку на паллет
        tube.destination_rack = self.test_types.index(test_type)
        tube.destination_row = current_row
        tube.destination_col = current_col

        self.racks[test_type][current_row][current_col] = tube
        self.tubes.append(tube)

        # Обновляем позицию для следующей пробирки
        current_col += 1
        if current_col >= self.rack_cols:
            current_col = 0
            current_row += 1

        self.rack_positions[test_type] = (current_row, current_col)

        logger.info(f"Пробирка {tube.barcode} → Паллет {tube.destination_rack} "
                    f"[{tube.destination_row}][{tube.destination_col}]")

        return True

    def get_tube_destination(self, barcode: str) -> Optional[Tuple[int, int, int]]:
        """
        Возвращает назначение пробирки (номер_паллета, ряд, столбец).
        """
        for tube in self.tubes:
            if tube.barcode == barcode:
                return (tube.destination_rack, tube.destination_row, tube.destination_col)
        return None

    def print_matrix(self):
        """Выводит матрицу всех паллетов."""
        print("\n" + "=" * 100)
        print("МАТРИЦА ТЕСТОВ - РАСПРЕДЕЛЕНИЕ ПО ПАЛЛЕТАМ")
        print("=" * 100)

        for i, test_type in enumerate(self.test_types):
            print(f"\n📦 ПАЛЛЕТ {i}: {test_type.value.upper()}")
            print("-" * 100)

            rack = self.racks[test_type]
            for row_idx, row in enumerate(rack):
                print(f"Ряд {row_idx:2d}: ", end="")
                for tube in row:
                    if tube is None:
                        print("[ПУСТО]".ljust(15), end=" ")
                    else:
                        print(str(tube.barcode).ljust(15), end=" ")
                print()

            # Статистика паллета
            filled = sum(1 for row in rack for tube in row if tube is not None)
            total = self.rack_rows * self.rack_cols
            print(f"Заполнено: {filled}/{total}")

        print("\n" + "=" * 100)
        print(f"ВСЕГО ПРОБИРОК: {len(self.tubes)}")
        print("=" * 100)


async def get_tube_info_async(barcode: str, host: str = "127.0.0.1", port: int = 7114) -> Optional[Dict]:
    """
    Асинхронный запрос информации о пробирке с сервера ЛИС.
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
        async with aiohttp.ClientSession() as session:
            async with session.post(
                    url=url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"✓ Ответ для {barcode}: {result.get('test_codes', [])}")
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
    """
    Определяет тип теста из ответа сервера.
    """
    if not response or response.get("status") != "success":
        return TestType.ERROR

    test_codes = response.get("test_codes", [])

    if not test_codes:
        return TestType.UNKNOWN

    test_code = test_codes[0].lower()

    if test_code == "ugi":
        return TestType.UGI
    elif test_code == "vpch":
        return TestType.VPCH
    elif test_code == "ugi+vpch":
        return TestType.UGI_VPCH
    elif test_code == "general":
        return TestType.GENERAL
    elif test_code == "buffer":
        return TestType.BUFFER
    elif test_code == "error":
        return TestType.ERROR
    else:
        return TestType.UNKNOWN


async def process_tube_async(barcode: str, row: int, col: int,
                             test_matrix: TestMatrix,
                             lis_host: str = "127.0.0.1",
                             lis_port: int = 7114):
    """
    Асинхронно обрабатывает одну пробирку:
    1. Отправляет запрос на сервер ЛИС
    2. Определяет тип теста
    3. Добавляет в соответствующий паллет
    """
    logger.info(f"🔍 Обработка [{row}][{col}]: {barcode}")

    # Запрос к серверу
    response = await get_tube_info_async(barcode, lis_host, lis_port)

    # Определение типа теста
    test_type = parse_test_type(response)

    # Создание объекта пробирки
    tube = TubeInfo(
        barcode=barcode,
        row=row,
        col=col,
        test_type=test_type
    )

    # Добавление в матрицу
    if test_type in test_matrix.racks:
        success = test_matrix.add_tube(tube)
        if success:
            logger.info(f"✓ {barcode} → Паллет {tube.destination_rack} "
                        f"[{tube.destination_row}][{tube.destination_col}] ({test_type.value})")
        else:
            logger.warning(f"⚠ {barcode} не добавлена - паллет {test_type.value} заполнен")
    else:
        logger.warning(f"⚠ {barcode} - неподдерживаемый тип теста: {test_type.value}")


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

        logger.info(f"📝 Регистры: X={dx}мм, Y={dy}мм, Z={dz}мм")

        cobot.start_program(program_name)
        logger.info(f"⏳ Программа '{program_name}' запущена...")

        if wait_for_robot_idle(cobot):
            logger.info("✓ Движение завершено")
            return True
        else:
            logger.warning("✗ Движение не завершилось вовремя")
            return False

    except Exception as e:
        logger.error(f"✗ Ошибка при движении: {e}")
        return False


def scan_three_tubes_to_array(scanner, target_array, row_index, max_attempts=10):
    """
    Сканирует 3 пробирки в одном ряду и записывает в массив 10x3.
    """
    attempts = 0
    tubes_scanned = 0
    tubes_to_scan = 3

    logger.info(f"Сканирование 3 столбцов в ряду {row_index}")

    while tubes_scanned < tubes_to_scan and attempts < max_attempts:
        attempts += 1

        try:
            result = scanner.scan(timeout=0.2)

            if result == 'NoRead':
                continue

            scan_data = result.split(';')
            logger.debug(f"Данные: {scan_data}")

            for i in range(min(tubes_to_scan, len(scan_data))):
                if target_array[row_index][i] == 0:
                    if scan_data[i] != 'NoRead':
                        target_array[row_index][i] = scan_data[i]
                        tubes_scanned += 1
                        logger.info(f"✓ [{row_index}][{i}]: {scan_data[i]}")

        except Exception as e:
            logger.error(f"Ошибка сканирования (попытка {attempts}): {e}")
            continue

    if tubes_scanned < tubes_to_scan:
        logger.warning(f"Отсканировано {tubes_scanned}/{tubes_to_scan}")

    return tubes_scanned


async def scan_and_request_parallel(scanner, cobot, test_matrix: TestMatrix,
                                    first_pos_x, first_pos_y, first_pos_z,
                                    x_step=20.5, y_step=60.0,
                                    lis_host="127.0.0.1", lis_port=7114):
    """
    ПАРАЛЛЕЛЬНОЕ сканирование и запросы к серверу.

    Алгоритм:
    1. Создаём очередь для асинхронных запросов
    2. Сканируем пробирку → сразу ставим запрос в очередь
    3. Робот продолжает двигаться и сканировать, пока запросы обрабатываются
    4. В конце ждём завершения всех запросов
    """
    # Массивы для сканирования
    first_pass_data = [[0 for _ in range(3)] for _ in range(10)]
    second_pass_data = [[0 for _ in range(3)] for _ in range(10)]

    # Список задач для параллельных запросов
    tasks = []

    logger.info("=" * 60)
    logger.info("НАЧАЛО ПАРАЛЛЕЛЬНОГО СКАНИРОВАНИЯ И ЗАПРОСОВ")
    logger.info("=" * 60)

    # ===== ПЕРВЫЙ ПРОХОД: КОЛОНКИ 0-2 =====
    logger.info("\n--- СКАНИРОВАНИЕ КОЛОНОК 0-2 ---")

    dx = first_pos_x
    dy = first_pos_y
    dz = first_pos_z

    if not move_robot_by_registers(cobot, dx=dx, dy=dy, dz=dz, program_name="Motion"):
        logger.error("✗ Не удалось переместиться к первой позиции")
        return first_pass_data, second_pass_data

    for row in range(10):
        logger.info(f"\nРяд {row}, колонки 0-2:")
        scan_three_tubes_to_array(scanner, first_pass_data, row)

        # Создаём задачи для всех отсканированных пробирок в этом ряду
        for col in range(3):
            barcode = first_pass_data[row][col]
            if barcode != 0 and barcode != 'NoRead':
                # Запускаем асинхронный запрос
                task = asyncio.create_task(
                    process_tube_async(barcode, row, col, test_matrix, lis_host, lis_port)
                )
                tasks.append(task)

        # Перемещаемся к следующему ряду
        if row < 9:
            dx += x_step
            if not move_robot_by_registers(cobot, dx=dx, dy=dy, dz=dz, program_name="Motion"):
                logger.error(f"✗ Ошибка перемещения к ряду {row + 1}")
                break

    # ===== ВТОРОЙ ПРОХОД: КОЛОНКИ 3-5 =====
    logger.info("\n--- СКАНИРОВАНИЕ КОЛОНОК 3-5 ---")

    dx = first_pos_x
    dy = dy + y_step

    if not move_robot_by_registers(cobot, dx=dx, dy=dy, dz=dz, program_name="Motion"):
        logger.error("✗ Не удалось переместиться ко второй позиции")
        # Ждём завершения уже запущенных задач
        await asyncio.gather(*tasks, return_exceptions=True)
        return first_pass_data, second_pass_data

    for row in range(10):
        logger.info(f"\nРяд {row}, колонки 3-5:")
        scan_three_tubes_to_array(scanner, second_pass_data, row)

        # Создаём задачи для всех отсканированных пробирок в этом ряду
        for col in range(3):
            barcode = second_pass_data[row][col]
            if barcode != 0 and barcode != 'NoRead':
                # Запускаем асинхронный запрос
                task = asyncio.create_task(
                    process_tube_async(barcode, row, col + 3, test_matrix, lis_host, lis_port)
                )
                tasks.append(task)

        # Перемещаемся к следующему ряду
        if row < 9:
            dx += x_step
            if not move_robot_by_registers(cobot, dx=dx, dy=dy, dz=dz, program_name="Motion"):
                logger.error(f"✗ Ошибка перемещения к ряду {row + 1}")
                break

    # ===== ОЖИДАНИЕ ЗАВЕРШЕНИЯ ВСЕХ ЗАПРОСОВ =====
    logger.info("\n⏳ Ожидание завершения всех запросов к серверу...")
    logger.info(f"Всего запросов: {len(tasks)}")

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Подсчёт ошибок
    errors = sum(1 for r in results if isinstance(r, Exception))
    if errors > 0:
        logger.warning(f"⚠ Ошибок при обработке: {errors}/{len(tasks)}")

    logger.info("✓ Все запросы завершены")
    logger.info("=" * 60)

    return first_pass_data, second_pass_data


def combine_arrays(first_pass, second_pass):
    """Объединяет два массива 10x3 в один массив 10x6."""
    combined = []
    for row in range(10):
        combined_row = first_pass[row] + second_pass[row]
        combined.append(combined_row)

    logger.info("✓ Массивы объединены: 10x3 + 10x3 = 10x6")
    return combined


def print_pallet_matrix(tube_matrix):
    """Выводит матрицу палеты."""
    print("\n" + "=" * 140)
    print("ИСХОДНАЯ МАТРИЦА СКАНИРОВАНИЯ 10x6")
    print("=" * 140)

    for i, row in enumerate(tube_matrix):
        print(f"Ряд {i:2d}: ", end="")
        for cell in row:
            if cell == 0:
                print("[ПУСТО]".ljust(15), end=" ")
            elif cell == 'NoRead':
                print("[ОШИБКА]".ljust(15), end=" ")
            else:
                print(str(cell).ljust(15), end=" ")
        print()

    # Статистика
    total_cells = 60
    scanned = sum(1 for row in tube_matrix for cell in row if cell != 0 and cell != 'NoRead')
    empty = sum(1 for row in tube_matrix for cell in row if cell == 0)
    errors = sum(1 for row in tube_matrix for cell in row if cell == 'NoRead')

    print("=" * 140)
    print(f"Статистика: Отсканировано: {scanned}/{total_cells} | Пусто: {empty} | Ошибки: {errors}")
    print("=" * 140)


def pickup_tube(cobot, x, y, z_safe=149, z_pickup=139, z_up=200):
    """
    Выполняет захват пробирки с помощью вакуумной присоски и поднимает её.

    Args:
        cobot: Объект робота
        x, y: Координаты пробирки в мм
        z_safe: Безопасная высота в мм
        z_pickup: Высота захвата в мм

    Returns:
        True если захват успешен, False при ошибке
    """
    logger.info(f"→ Захват пробирки на ({x:.1f}, {y:.1f})")

    # Подход над пробиркой
    dx = x
    dy = y
    dz = z_safe
    logger.info("  Подход над пробиркой")
    if not move_robot_by_registers(cobot, dx=dx, dy=dy, dz=dz, program_name="Motion"):
        return False

    # Включение вакуума
    logger.info("  🔌 Вакуум ВКЛ")
    cobot.set_DO(2, True)

    # Спуск к пробирке
    dz = z_pickup
    logger.info("  Спуск к пробирке")
    if not move_robot_by_registers(cobot, dx=dx, dy=dy, dz=dz, program_name="Motion"):
        cobot.set_DO(2, False)
        return False
    time.sleep(1.0)
    cobot.set_DO(2, False)

    # Подъём с пробиркой
    dz = z_up
    logger.info("  Подъём с пробиркой")
    if not move_robot_by_registers(cobot, dx=dx, dy=dy, dz=dz, program_name="Motion"):
        cobot.set_DO(2, False)
        return False

    logger.info("  ✓ Пробирка захвачена")
    return True


def place_tube(cobot, x, y, z_safe=200, z_drop=146):
    """
    Перемещает робота к месту назначения и размещает пробирку.

    Args:
        cobot: Объект робота
        x, y: Координаты места размещения в мм
        z_safe: Безопасная высота в мм
        z_drop: Высота размещения в мм
        stabilization_delay: Задержка для стабилизации в секундах

    Returns:
        True если размещение успешно, False при ошибке
    """
    logger.info(f"→ Размещение пробирки на ({x:.1f}, {y:.1f})")

    # Перемещение к месту назначения (на безопасной высоте)
    dx = x
    dy = y
    dz = z_safe
    logger.info("  Перемещение к месту назначения")
    if not move_robot_by_registers(cobot, dx=dx, dy=dy, dz=dz, program_name="Motion"):
        return False

    # Спуск к месту размещения
    dz = z_drop
    logger.info("  Спуск к месту размещения")
    if not move_robot_by_registers(cobot, dx=dx, dy=dy, dz=dz, program_name="Motion"):
        return False


    # Сброс остаточного вакуума
    logger.info("  💨 Сброс остаточного вакуума")
    cobot.set_DO(1, True)
    cobot.set_DO(1, False)

    logger.info("  ✓ Пробирка размещена")
    return True


def process_tubes_by_test_matrix(cobot, test_matrix: TestMatrix,
                                 source_start_position,
                                 dest_start_positions: Dict[int, Tuple[float, float, float]],
                                 tube_spacing_x=20.7,
                                 tube_spacing_y=20.7):
    """
    Обрабатывает все пробирки согласно матрице тестов.

    Args:
        cobot: Объект робота
        test_matrix: Матрица с информацией о назначении пробирок
        source_start_position: Начальная позиция исходного штатива (x, y, z)
        dest_start_positions: Словарь {номер_паллета: (x, y, z)} - начальные позиции паллетов назначения
        tube_spacing_x: Расстояние между рядами по X в мм
        tube_spacing_y: Расстояние между колонками по Y в мм
    """
    source_x, source_y, source_z = source_start_position

    print("\n" + "=" * 100)
    print("НАЧАЛО ПЕРЕМЕЩЕНИЯ ПРОБИРОК ПО МАТРИЦЕ ТЕСТОВ")
    print("=" * 100)

    processed_count = 0
    total_tubes = len(test_matrix.tubes)

    for tube in test_matrix.tubes:
        processed_count += 1
        print(f"\n[{processed_count}/{total_tubes}] Пробирка {tube.barcode} ({tube.test_type.value})")
        print(f"  Из: [{tube.row}][{tube.col}]")
        print(f"  В:  Паллет {tube.destination_rack} [{tube.destination_row}][{tube.destination_col}]")

        # Координаты источника
        pickup_x = source_x + tube.row * tube_spacing_x
        pickup_y = source_y + tube.col * tube_spacing_y

        # Координаты назначения
        dest_start = dest_start_positions.get(tube.destination_rack)
        if dest_start is None:
            logger.error(f"✗ Нет координат для паллета {tube.destination_rack}")
            continue

        dest_x = dest_start[0] + tube.destination_row * tube_spacing_x
        dest_y = dest_start[1] + tube.destination_col * tube_spacing_y
        dest_z = dest_start[2]

        try:
            # ШАГ 1: Захват пробирки с исходного штатива
            print(f"  📍 Захват с ({pickup_x:.1f}, {pickup_y:.1f})")
            if not pickup_tube(cobot, pickup_x, pickup_y, z_safe=source_z):
                print(f"  ✗ Ошибка захвата")
                continue

            # ШАГ 2: Размещение пробирки на паллет назначения
            print(f"  📍 Размещение на ({dest_x:.1f}, {dest_y:.1f})")
            if not place_tube(cobot, dest_x, dest_y):
                print(f"  ✗ Ошибка размещения")
                # Попытка отпустить пробирку в безопасном месте
                logger.warning("  ⚠ Аварийное отключение вакуума")
                cobot.set_DO(2, False)
                cobot.set_DO(1, True)
                time.sleep(0.5)
                cobot.set_DO(1, False)
                continue

            print(f"  ✓ Успешно перемещена")

        except Exception as e:
            logger.error(f"  ✗ Ошибка: {e}")
            # Аварийное отключение вакуума при ошибке
            try:
                cobot.set_DO(2, False)
                cobot.set_DO(1, True)
                time.sleep(0.5)
                cobot.set_DO(1, False)
            except:
                pass

    print("\n" + "=" * 100)
    print(f"ПЕРЕМЕЩЕНИЕ ЗАВЕРШЕНО: {processed_count}/{total_tubes}")
    print("=" * 100)

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

    # ========== КОНФИГУРАЦИЯ ==========
    # Типы тестов (от 2 до 6)
    test_types = [
        TestType.UGI,
        TestType.VPCH
    ]

    # Сервер ЛИС
    LIS_HOST = "127.0.0.1"
    LIS_PORT = 7114

    # Инициализация устройств
    scanner = Scanner(ip='192.168.124.4', port=6000)
    cobot = RobotManipulator("R1", ip="192.168.124.2")

    # Подключение
    connect_devices(scanner, cobot)
    try:
        # Создание матрицы тестов
        test_matrix = TestMatrix(test_types=test_types, rack_capacity=(10, 6))

        # Начальная позиция для сканирования
        scan_start_x = 175
        scan_start_y = 280
        scan_start_z = 200

        # Параллельное сканирование и запросы к серверу
        first_pass, second_pass = await scan_and_request_parallel(
            scanner=scanner,
            cobot=cobot,
            test_matrix=test_matrix,
            first_pos_x=scan_start_x,
            first_pos_y=scan_start_y,
            first_pos_z=scan_start_z,
            x_step=20.7,
            y_step=20.7 * 3,
            lis_host=LIS_HOST,
            lis_port=LIS_PORT
        )

        # Объединение массивов
        tube_matrix = combine_arrays(first_pass, second_pass)

        # Вывод исходной матрицы сканирования
        print_pallet_matrix(tube_matrix)

        # Вывод матрицы тестов (распределение по паллетам)
        test_matrix.print_matrix()

        # Координаты паллетов назначения
        dest_positions = {
            0: (-93, 317, 146),  # Паллет 0 - UGI
            1: (-315, 317, 146),  # Паллет 1 - VPCH
        }

        # Обработка пробирок согласно матрице тестов
        # Раскомментируйте для запуска:
        source_position = (129, 317, 148)
        process_tubes_by_test_matrix(
            cobot=cobot,
            test_matrix=test_matrix,
            source_start_position=source_position,
            dest_start_positions=dest_positions,
            tube_spacing_x=20.7,
            tube_spacing_y=20.7
        )

    except KeyboardInterrupt:
        print("\n\n⚠ Программа прервана пользователем")
    except Exception as e:
        print(f"\n\n✗ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        disconnect_devices(scanner, cobot)


def main():
    """Точка входа."""
    asyncio.run(main_async())


if __name__ == '__main__':
    main()