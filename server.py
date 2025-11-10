"""
Простой Flask сервер для сохранения матриц в определённую директорию
Запуск: python server.py
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)  # Разрешаем запросы с веб-страницы

# НАСТРОЙ ЭТУ ДИРЕКТОРИЮ - куда сохранять файлы
SAVE_DIRECTORY = r"C:\Users\konsentik\Desktop\roboaarm"  # Измени на свою папку!

# Создаём директорию если её нет
os.makedirs(SAVE_DIRECTORY, exist_ok=True)

@app.route('/')
def index():
    """Главная страница с кнопкой"""
    return send_from_directory('.', 'index.html')

@app.route('/index.html')
def home():
    """Главная страница"""
    return send_from_directory('.', 'index.html')

@app.route('/matrices.html')
def matrices():
    """Страница с матрицами"""
    return send_from_directory('.', 'matrices.html')

@app.route('/style.css')
def style():
    """Отдаём CSS"""
    return send_from_directory('.', 'style.css')

@app.route('/save_matrix', methods=['POST'])
def save_matrix():
    """API для сохранения матрицы"""
    try:
        data = request.get_json()
        content = data.get('content', '')
        filename = data.get('filename', 'matrix_data.py')
        
        # Путь для сохранения
        filepath = os.path.join(SAVE_DIRECTORY, filename)
        
        # Сохраняем файл
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return jsonify({
            'success': True,
            'message': f'Файл сохранён: {filepath}',
            'path': filepath
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

if __name__ == '__main__':
    print(f"Файлы будут сохраняться в: {SAVE_DIRECTORY}")
    print("Открой браузер: http://localhost:5000")
    app.run(debug=True, port=5000)