# backend/tasks/management/commands/process_tasks.py

import os
import time
from django.core.management.base import BaseCommand
from tasks.models import Task
from tasks.tasks import calculate_fibonacci_task
from django.utils import timezone

class Command(BaseCommand):
    help = 'Запускає pending задачі на цьому сервері (django-background-tasks)'

    def handle(self, *args, **options):
        server_port = os.getenv('SERVER_PORT')
        if not server_port:
            self.stdout.write(self.style.ERROR("SERVER_PORT не встановлено!"))
            return

        server_url = f"http://127.0.0.1:{server_port}"
        self.stdout.write(self.style.SUCCESS(f"Воркер запущений на {server_url}"))

        while True:
            try:
                # Шукаємо найстарішу pending задачу на цьому сервері
                task = Task.objects.filter(
                    status='pending',
                    server_url=server_url
                ).order_by('created_at').first()

                if task:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Запускаю задачу #{task.id} | Fibonacci({task.number})"
                        )
                    )

                    # ВАЖЛИВО: Переводимо в in_progress ДО запуску
                    task.status = 'in_progress'
                    task.save()
                    print(f"Задача #{task.id} → in_progress")  # лог для перевірки
                    
                    # Запускаємо через django-background-tasks (НЕ .delay!)
                    calculate_fibonacci_task(task.id, task.number)

                else:
                    time.sleep(1)

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Помилка воркера: {e}"))
                time.sleep(5)