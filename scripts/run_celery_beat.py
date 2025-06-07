"""Скрипт для запуска Celery beat"""
import os
import sys

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
os.chdir(project_root)

def run_celery_beat():
    """Запуск Celery beat"""
    os.system("celery -A app.tasks.celery_tasks beat --loglevel=info")

if __name__ == "__main__":
    run_celery_beat()