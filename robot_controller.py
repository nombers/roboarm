"""
Модуль управления состоянием робота.
Обеспечивает синхронизацию между веб-интерфейсом и основной программой.
"""
import json
import os
import time
from threading import Lock

STATE_FILE = 'robot_state.json'

class RobotController:
    """Контроллер состояния робота с синхронизацией"""
    
    def __init__(self):
        self.lock = Lock()
        self.state = {
            'command': 'idle',  # idle, start, pause, stop, change_rack
            'running': False,
            'paused': False,
            'rack_to_change': None,  # 'ugi', 'vpch', 'both'
            'current_pallet': 0,
            'rack_replaced': False,  # Флаг что штатив заменён
            'pause_requested': False,  # Новый флаг для запроса паузы
        }
        self.load_state()
    
    def load_state(self):
        """Загрузка состояния из файла"""
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, 'r') as f:
                    self.state = json.load(f)
        except:
            pass
    
    def save_state(self):
        """Сохранение состояния в файл"""
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump(self.state, f)
        except:
            pass
    
    def get_command(self):
        """Получить текущую команду"""
        with self.lock:
            self.load_state()
            return self.state.get('command', 'idle')
    
    def set_command(self, command):
        """Установить команду"""
        with self.lock:
            self.state['command'] = command
            self.save_state()
    
    def is_running(self):
        """Проверка запущена ли программа"""
        with self.lock:
            self.load_state()
            return self.state.get('running', False)
    
    def set_running(self, value):
        """Установить статус запуска"""
        with self.lock:
            self.state['running'] = value
            self.save_state()
    
    def is_paused(self):
        """Проверка на паузу"""
        with self.lock:
            self.load_state()
            return self.state.get('paused', False)
    
    def is_pause_requested(self):
        """Проверка запроса паузы (ещё не обработан)"""
        with self.lock:
            self.load_state()
            return self.state.get('pause_requested', False)
    
    def set_pause_requested(self):
        """Установить флаг запроса паузы"""
        with self.lock:
            self.state['pause_requested'] = True
            self.save_state()
    
    def clear_pause_request(self):
        """Очистить флаг запроса паузы"""
        with self.lock:
            self.state['pause_requested'] = False
            self.save_state()
    
    def set_paused(self, value):
        """Установить паузу"""
        with self.lock:
            self.state['paused'] = value
            if value:
                self.state['pause_requested'] = False
            self.save_state()
    
    def get_rack_to_change(self):
        """Какой штатив нужно заменить"""
        with self.lock:
            self.load_state()
            return self.state.get('rack_to_change', None)
    
    def set_rack_to_change(self, rack_type):
        """Установить штатив для замены"""
        with self.lock:
            self.state['rack_to_change'] = rack_type
            self.state['rack_replaced'] = False
            self.save_state()
    
    def is_rack_replaced(self):
        """Проверка заменён ли штатив"""
        with self.lock:
            self.load_state()
            return self.state.get('rack_replaced', False)
    
    def confirm_rack_replaced(self):
        """Подтвердить замену штатива"""
        with self.lock:
            self.state['rack_replaced'] = True
            self.state['rack_to_change'] = None
            self.save_state()
    
    def wait_for_pause_clear(self, timeout=300):
        """Ждать снятия паузы"""
        start_time = time.time()
        while self.is_paused() and (time.time() - start_time < timeout):
            time.sleep(0.5)
        return not self.is_paused()
    
    def wait_for_rack_replacement(self, rack_type, timeout=600):
        """Ждать замены штатива"""
        self.set_rack_to_change(rack_type)
        start_time = time.time()
        
        print("\n" + "="*100)
        print(f"⚠ ТРЕБУЕТСЯ ЗАМЕНА ШТАТИВА: {rack_type.upper()}")
        print("="*100)
        print("Замените штатив через веб-интерфейс или нажмите Enter здесь...")
        print("="*100)
        
        # Ждём замены через веб или Enter в консоли
        while not self.is_rack_replaced() and (time.time() - start_time < timeout):
            time.sleep(0.5)
        
        if self.is_rack_replaced():
            print("✓ Штатив заменён, продолжаем работу")
            return True
        else:
            print("✗ Таймаут ожидания замены штатива")
            return False
    
    def check_pause(self, cobot=None, pause_position=None):
        """
        Проверить паузу и обработать её.
        
        Args:
            cobot: Ссылка на робота для перемещения
            pause_position: Позиция паузы (x, y, z)
        
        Returns:
            True если продолжаем, False если ошибка
        """
        # Если был запрос паузы - обработаем его
        if self.is_pause_requested():
            print("\n⏸ ЗАПРОС ПАУЗЫ - перемещение в позицию паузы...")
            
            # Двигаем робота в позицию паузы
            if cobot and pause_position:
                try:
                    from main import move_robot_by_registers
                    x, y, z = pause_position
                    if move_robot_by_registers(cobot, dx=x, dy=y, dz=z):
                        print("✓ Робот в позиции паузы")
                    else:
                        print("✗ Ошибка перемещения в позицию паузы")
                except Exception as e:
                    print(f"✗ Ошибка при перемещении: {e}")
            
            # Теперь ставим на паузу
            self.set_paused(True)
            print("⏸ Программа на паузе...")
        
        # Если на паузе - ждём
        if self.is_paused():
            if self.wait_for_pause_clear():
                print("▶ Продолжаем работу")
                return True
            else:
                print("✗ Таймаут паузы")
                return False
        
        return True
    
    def reset(self):
        """Сброс состояния"""
        with self.lock:
            self.state = {
                'command': 'idle',
                'running': False,
                'paused': False,
                'rack_to_change': None,
                'current_pallet': 0,
                'rack_replaced': False,
                'pause_requested': False,
            }
            self.save_state()


# Глобальный экземпляр контроллера
controller = RobotController()


def get_controller():
    """Получить глобальный контроллер"""
    return controller
