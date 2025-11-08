from django.apps import AppConfig
from django.db.models.signals import post_migrate

class TasksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tasks'

    def ready(self):
        """
        Виконується один раз при запуску Django
        """
        # Імпортуємо тут щоб уникнути circular imports
        from django.utils import timezone
        from .models import Task
        import sys
        
        # Перевіряємо чи це не міграція або інша команда
        if 'runserver' in sys.argv or 'waitress-serve' in ' '.join(sys.argv) or 'gunicorn' in sys.argv[0]:
            try:
                # Знайти завислі задачі
                stuck_tasks = Task.objects.filter(
                    status__in=['pending', 'in_progress']
                )
                
                count = stuck_tasks.count()
                
                if count > 0:
                    print(f'\n{"="*60}')
                    print(f'CLEANUP: Знайдено {count} завислих задач')
                    print(f'{"="*60}')
                    
                    # Оновити статус
                    stuck_tasks.update(
                        status='failed',
                        error_message='Сервер був перезапущений. Задача скасована.',
                        completed_at=timezone.now()
                    )
                    
                    print(f'Оновлено {count} задач → status=failed')
                    
                    for task in stuck_tasks:
                        print(f'   Task #{task.id}: Fibonacci({task.number}) user={task.user.username}')
                    
                    print(f'{"="*60}\n')
                else:
                    print('\nCleanup: Завислих задач не знайдено\n')
                    
            except Exception as e:
                # Ігноруємо помилки (наприклад, якщо таблиця ще не створена)
                if 'no such table' not in str(e).lower():
                    print(f'Cleanup error: {e}')