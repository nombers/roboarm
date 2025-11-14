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
import sys
import json

app = Flask(__name__)
CORS(app)

SAVE_DIRECTORY = r"C:\Users\konse\Desktop\wtf\roboarm"
os.makedirs(SAVE_DIRECTORY, exist_ok=True)

# Получаем контроллер
controller = get_controller()

# Глобальная переменная для хранения потока программы
program_thread = None


@app.route('/api/start_program', methods=['POST'])
def start_program():
    """Запуск основной программы"""
    global program_thread
    
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
                from main import main_async
                asyncio.run(main_async())
            except Exception as e:
                print(f"Ошибка программы: {e}")
            finally:
                controller.set_running(False)
        
        program_thread = threading.Thread(target=run_program, daemon=True)
        program_thread.start()
        
        return jsonify({'success': True, 'message': 'Программа запускается...'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/stop_program', methods=['POST'])
def stop_program():
    """Полная остановка программы"""
    try:
        if not controller.is_running():
            return jsonify({'success': False, 'message': 'Программа не запущена'})
        
        # Устанавливаем команду остановки
        controller.set_command('stop')
        controller.set_running(False)
        controller.set_paused(False)
        
        # Завершаем Python процесс (программу main.py)
        # Это заставит поток завершиться
        
        return jsonify({'success': True, 'message': 'Программа остановлена'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/pause_program', methods=['POST'])
def pause_program():
    """Приостановка программы"""
    try:
        if not controller.is_running():
            return jsonify({'success': False, 'message': 'Программа не запущена'})
        
        # Устанавливаем флаг запроса паузы
        controller.set_pause_requested()
        controller.set_command('pause')
        
        return jsonify({'success': True, 'message': 'Запрос паузы отправлен'})
    
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
        rack_id = data.get('rack_id', 0)
        
        # Подтверждаем замену штатива через контроллер
        controller.confirm_rack_replaced()
        
        return jsonify({
            'success': True,
            'message': f'Замена штатива {rack_type.upper()} #{rack_id} подтверждена'
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/robot_status', methods=['GET'])
def robot_status():
    """Статус робота"""
    # Получаем информацию о штативах из robot_data.json если есть
    rack_counts = {'ugi': 2, 'vpch': 1, 'both': 1, 'other': 1}
    
    try:
        if os.path.exists('robot_data.json'):
            with open('robot_data.json', 'r') as f:
                robot_data = json.load(f)
                rack_counts = robot_data.get('rack_counts', rack_counts)
    except:
        pass
    
    return jsonify({
        'running': controller.is_running(),
        'paused': controller.is_paused(),
        'rack_to_change': controller.get_rack_to_change(),
        'command': controller.get_command(),
        'rack_counts': rack_counts
    })


@app.route('/api/get_barcodes', methods=['GET'])
def get_barcodes():
    """Получение баркодов из штативов"""
    try:
        if os.path.exists('robot_data.json'):
            with open('robot_data.json', 'r') as f:
                robot_data = json.load(f)
                barcodes = robot_data.get('barcodes', {})
                return jsonify({'success': True, 'barcodes': barcodes})
        else:
            return jsonify({'success': False, 'message': 'Нет данных'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


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
    # Удаляем robot_state.json при запуске
    state_file = 'robot_state.json'
    if os.path.exists(state_file):
        try:
            os.remove(state_file)
            print(f"✓ Файл {state_file} удалён")
        except Exception as e:
            print(f"⚠ Не удалось удалить {state_file}: {e}")
    
    print("="*70)
    print(f"Файлы: {SAVE_DIRECTORY}")
    print("Браузер: http://localhost:5000")
    app.run(debug=True, port=5000, host='0.0.0.0')