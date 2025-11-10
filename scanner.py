import socket
import time


class Scanner:
    """
    Класс для работы со сканером QR-кодов через TCP/IP соединение.
    """

    def __init__(self, ip: str, port: int):
        """
        Инициализация сканера.

        Args:
            ip: IP-адрес сканера
            port: Порт для подключения
        """
        self._ip = ip
        self._port = port
        self._enable_message = 'start'
        self._disable_message = 'stop'
        self._socket = None
        self.connection = False

    def connect(self) -> dict:
        """
        Подключение к сканеру.

        Returns:
            Словарь с статусом подключения и сообщением
        """
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(2)
            self._socket.connect((self._ip, self._port))
            self.connection = True
            print(f"[Scanner] Успешное подключение к {self._ip}:{self._port}")
            return {'StatusCode': True, "Response": 'Connection success'}
        except socket.timeout:
            self.connection = False
            print(f"[Scanner] Ошибка: превышено время ожидания подключения")
            return {'StatusCode': False, 'Response': 'Connection timeout'}
        except ConnectionRefusedError:
            self.connection = False
            print(f"[Scanner] Ошибка: подключение отклонено")
            return {'StatusCode': False, 'Response': 'Connection refused'}
        except Exception as e:
            self.connection = False
            print(f"[Scanner] Ошибка подключения: {str(e)}")
            return {'StatusCode': False, 'Response': f'Connection error: {str(e)}'}

    def disconnect(self) -> dict:
        """
        Отключение от сканера.

        Returns:
            Словарь с статусом отключения и сообщением
        """
        try:
            if self._socket:
                self._socket.close()
                self._socket = None
            self.connection = False
            print("[Scanner] Отключение выполнено")
            return {'StatusCode': True, 'Response': 'Disconnected'}
        except Exception as e:
            print(f"[Scanner] Ошибка при отключении: {str(e)}")
            return {'StatusCode': False, 'Response': f'Disconnection error: {str(e)}'}

    def stop_scan(self) -> None:
        """Остановка процесса сканирования."""
        if self._socket:
            self._socket.sendall(self._disable_message.encode())

    def scan(self, timeout: float = 0.2) -> str:
        """
        Выполнение сканирования QR-кодов.

        Args:
            timeout: Время ожидания ответа от сканера в секундах

        Returns:
            Строка с результатами сканирования, разделенными точкой с запятой
        """
        try:
            self._socket.sendall(self._enable_message.encode())
            time.sleep(timeout)
            self._socket.sendall(self._disable_message.encode())
            result = self._socket.recv(1024).decode('utf-8').replace('\r', '').strip()

            if not result or result == 'NoRead':
                return 'NoRead'
            return result

        except socket.timeout:
            print("[Scanner] Превышено время ожидания при сканировании")
            return 'NoRead'
        except Exception as e:
            print(f"[Scanner] Ошибка при сканировании: {str(e)}")
            return 'NoRead'