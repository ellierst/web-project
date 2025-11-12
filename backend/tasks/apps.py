from django.apps import AppConfig
from django.db.models.signals import post_migrate

class TasksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tasks'

    def ready(self):
        """
        Виконується один раз при запуску Django
        """
        from django.utils import timezone
        from .models import Task
        import sys
        
        # Перевіряємо чи це не міграція або інша команда
        if 'runserver' in sys.argv or 'waitress-serve' in ' '.join(sys.argv) or 'gunicorn' in sys.argv[0]:

            print('\nCLEANUP AT STARTUP\n')
            
            try:
                stuck_tasks = Task.objects.filter(status='in_progress')
                count = stuck_tasks.count()

                if count > 0:
                    print(f'TASKS: Знайдено {count} завислих задач')

                    stuck_tasks.update(
                        status='failed',
                        completed_at=timezone.now()
                    )
                    
                    print(f'Оновлено {count} задач → status=failed')
                    
                    for task in stuck_tasks:
                        print(f'   Task #{task.id}: Fibonacci({task.number}) user={task.user.username}')
                else:
                    print('TASKS: Завислих задач не знайдено')

                try:
                    from background_task.models import Task as BackgroundTask, CompletedTask

                    in_progress__count = BackgroundTask.objects.count()
                    completed_count = CompletedTask.objects.count()

                    print(f'   BACKGROUND_TASK:')
                    print(f'   Progress: {in_progress__count}')
                    print(f'   Completed: {completed_count}')

                    if in_progress__count > 0:
                        BackgroundTask.objects.all().delete()
                        print(f' Видалено {in_progress__count} Progress Tasks')

                    if completed_count > 0:
                        CompletedTask.objects.all().delete()
                        print(f' Видалено {completed_count} Completed Tasks')

                except ImportError:
                    print('django-background-tasks не встановлено')
            except Exception as e:
                if 'no such table' not in str(e).lower():
                    print(f'Помилка очищення background tasks: {e}')