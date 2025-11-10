"""
Flask сервер для управления роботом через robot_controller
Запуск: python server.py
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from robot_controller import get_controller
import os
import threading
import time

app = Flask(__name__)
CORS(app)

SAVE_DIRECTORY = r"C:\Users\konsentik\Desktop\wtf\roboarm"
os.makedirs(SAVE_DIRECTORY, exist_ok=True)

# Получаем контроллер
controller = get_controller()

# НАСТРОЙ ПОЗИЦИИ РОБОТА!
POSITIONS = {
    'start': (0, 300, 250),
    'pause': (0, 400, 300),
    'rack_ugi': (-93, 317, 250),
    'rack_vpch': (-315, 317, 250),
}


def move_robot_to_position(cobot, position_name):
    """Перемещает робота в заданную позицию"""
    try:
        if position_name not in POSITIONS:
            return False
        
        x, y, z = POSITIONS[position_name]
        cobot.set_number_register(1, x)
        cobot.set_number_register(2, y)
        cobot.set_number_register(3, z)
        cobot.start_program("Motion")
        time.sleep(2)
        return True
    except Exception as e:
        print(f"Ошибка перемещения: {e}")
        return False


@app.route('/api/start_program', methods=['POST'])
def start_program():
    """Запуск основной программы"""
    try:
        if controller.is_running():
            return jsonify({'success': False, 'message': 'Программа уже запущена'})
        
        # Сбрасываем состояние
        controller.reset()
        controller.set_command('start')
        
        # Запускаем в отдельном потоке
        def run_program():
            try:
                import asyncio
                from main_with_matrix_config import main_async
                asyncio.run(main_async())
            except Exception as e:
                print(f"Ошибка программы: {e}")
            finally:
                controller.set_running(False)
        
        thread = threading.Thread(target=run_program, daemon=True)
        thread.start()
        
        return jsonify({'success': True, 'message': 'Программа запускается...'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/pause_program', methods=['POST'])
def pause_program():
    """Приостановка программы"""
    try:
        if not controller.is_running():
            return jsonify({'success': False, 'message': 'Программа не запущена'})
        
        # Устанавливаем паузу через контроллер
        controller.set_paused(True)
        controller.set_command('pause')
        
        return jsonify({'success': True, 'message': 'Программа будет приостановлена'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/resume_program', methods=['POST'])
def resume_program():
    """Возобновление программы"""
    try:
        if not controller.is_running():
            return jsonify({'success': False, 'message': 'Программа не запущена'})
        
        if not controller.is_paused():
            return jsonify({'success': False, 'message': 'Программа не на паузе'})
        
        # Снимаем паузу
        controller.set_paused(False)
        controller.set_command('resume')
        
        return jsonify({'success': True, 'message': 'Программа возобновлена'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/change_rack', methods=['POST'])
def change_rack():
    """Смена штатива - уведомляет программу что штатив заменён"""
    try:
        data = request.get_json()
        rack_type = data.get('type', 'ugi')
        
        # Подтверждаем замену штатива через контроллер
        controller.confirm_rack_replaced()
        
        return jsonify({
            'success': True,
            'message': f'Замена штатива {rack_type.upper()} подтверждена'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/robot_status', methods=['GET'])
def robot_status():
    """Статус робота"""
    return jsonify({
        'running': controller.is_running(),
        'paused': controller.is_paused(),
        'rack_to_change': controller.get_rack_to_change(),
        'command': controller.get_command()
    })


# ═══════════════════════════════════════════════════════════════
# ВЕБ-ИНТЕРФЕЙС
# ═══════════════════════════════════════════════════════════════

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/index.html')
def home():
    return send_from_directory('.', 'index.html')

@app.route('/matrices.html')
def matrices():
    return send_from_directory('.', 'matrices.html')

@app.route('/style.css')
def style():
    return send_from_directory('.', 'style.css')

@app.route('/save_matrix', methods=['POST'])
def save_matrix():
    """Сохранение матрицы"""
    try:
        data = request.get_json()
        content = data.get('content', '')
        filename = data.get('filename', 'matrix_data.py')
        
        filepath = os.path.join(SAVE_DIRECTORY, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return jsonify({
            'success': True,
            'message': f'Файл сохранён: {filepath}',
            'path': filepath
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


if __name__ == '__main__':
    print("="*70)
    print(f"Файлы: {SAVE_DIRECTORY}")
    print("Браузер: http://localhost:5000")
    print("="*70)
    print("\n⚙️ НАСТРОЙ ПОЗИЦИИ В КОДЕ:")
    for name, pos in POSITIONS.items():
        print(f"  {name}: {pos}")
    print("="*70)
    app.run(debug=True, port=5000, host='0.0.0.0')