from Agilebot.IR.A.arm import Arm
from Agilebot.IR.A.status_code import StatusCodeEnum
from Agilebot.IR.A.sdk_types import SignalType, SignalValue
from Agilebot.IR.A.sdk_classes import MotionPose
from Agilebot.IR.A.common.const import const
from Agilebot.IR.A.sdk_types import ParamType

class RobotManipulator:
    """
    Класс для управления коллаборативным роботом Agilebot.
    Предоставляет высокоуровневый интерфейс для основных операций.
    """

    def __init__(self, name: str, ip: str):
        """
        Инициализация робота.

        Args:
            name: Имя робота для идентификации
            ip: IP-адрес робота
        """
        self.name = name
        self.ip = ip
        self.connected = False
        self.arm = Arm()

    def connect(self) -> None:
        """Подключение к роботу."""
        print(f"[{self.name}] Подключение к роботу {self.ip}")
        ret = self.arm.connect(self.ip)
        assert ret == StatusCodeEnum.OK, f"Ошибка подключения к роботу: {ret}"
        self.connected = True
        print(f"[{self.name}] Подключение успешно")

    def disconnect(self) -> None:
        """Отключение от робота."""
        if self.connected:
            print(f"[{self.name}] Отключение от робота")
            self.arm.disconnect()
            self.connected = False

    def start_program(self, program_name: str) -> None:
        """
        Запуск программы на роботе.

        Args:
            program_name: Имя программы для запуска
        """
        ret = self.arm.execution.start(program_name)
        assert ret == StatusCodeEnum.OK, f"Ошибка запуска программы: {ret}"

    def pause_program(self, program_name: str) -> None:
        """
        Пауза программы на роботе.

        Args:
            program_name: Имя программы для паузы
        """
        ret = self.arm.execution.pause(program_name)
        assert ret == StatusCodeEnum.OK, f"Ошибка паузы программы: {ret}"

    def resume_program(self, program_name: str) -> None:
        """
        Возобновление программы на роботе.

        Args:
            program_name: Имя программы для возобновления
        """
        ret = self.arm.execution.resume(program_name)
        assert ret == StatusCodeEnum.OK, f"Ошибка возобновления программы: {ret}"

    def stop_program(self, program_name: str) -> None:
        """
        Остановка программы на роботе.

        Args:
            program_name: Имя программы для остановки
        """
        ret = self.arm.execution.stop(program_name)
        assert ret == StatusCodeEnum.OK, f"Ошибка остановки программы: {ret}"

    def get_string_register(self, register_id: int) -> str:
        """
        Чтение строкового регистра.

        Args:
            register_id: ID регистра

        Returns:
            Значение регистра в виде строки
        """
        string_register, ret = self.arm.string_register.read(register_id)
        assert ret == StatusCodeEnum.OK, f"Ошибка чтения строкового регистра: {ret}"
        return str(string_register.value)

    def set_string_register(self, register_id: int, string: str) -> None:
        """
        Запись значения в строковый регистр.

        Args:
            register_id: ID регистра
            string: Значение для записи
        """
        string_register, ret = self.arm.string_register.read(register_id)
        assert ret == StatusCodeEnum.OK, f"Ошибка чтения строкового регистра: {ret}"
        string_register.value = string
        ret = self.arm.string_register.write(register_id, string_register)
        assert ret == StatusCodeEnum.OK, f"Ошибка записи строкового регистра: {ret}"

    def get_number_register(self, register_id: int) -> int:
        """
        Чтение числового регистра.

        Args:
            register_id: ID регистра

        Returns:
            Значение регистра в виде числа
        """
        number_register, ret = self.arm.register.read(register_id)
        assert ret == StatusCodeEnum.OK, f"Ошибка чтения числового регистра: {ret}"
        return int(number_register.value)

    def set_number_register(self, register_id: int, number: int) -> None:
        """
        Запись значения в числовый регистр.

        Args:
            register_id: ID регистра
            number: Значение для записи
        """
        number_register, ret = self.arm.register.read(register_id)
        assert ret == StatusCodeEnum.OK, f"Ошибка чтения числового регистра: {ret}"
        number_register.value = number
        ret = self.arm.register.write(register_id, number_register)
        assert ret == StatusCodeEnum.OK, f"Ошибка записи числового регистра: {ret}"

    def get_DO(self, do_id: int) -> bool:
        """
        Чтение цифрового выхода.

        Args:
            do_id: ID цифрового выхода

        Returns:
            True если выход включен, False если выключен
        """
        do_value, ret = self.arm.digital_signals.read(SignalType.DO, do_id)
        return do_value == 1

    def set_DO(self, do_id: int, value: bool) -> None:
        """
        Установка состояния цифрового выхода.

        Args:
            do_id: ID цифрового выхода
            value: True для включения, False для выключения
        """
        signal_value = SignalValue.ON if value else SignalValue.OFF
        ret = self.arm.digital_signals.write(SignalType.DO, do_id, signal_value)

    def _wait_for_idle(self) -> None:
        """Ожидание завершения движения робота."""
        while str(self.arm.get_robot_status()[1]) != 'RobotStatusEnum.ROBOT_IDLE':
            continue