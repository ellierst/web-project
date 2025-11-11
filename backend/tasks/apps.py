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
            
            print(f'\n{"="*70}')
            print('🧹 CLEANUP AT STARTUP')
            print(f'{"="*70}\n')
            
            try:
                # ============================================
                # 1. ОЧИЩЕННЯ ВАШИХ TASK МОДЕЛЕЙ
                # ============================================
                stuck_tasks = Task.objects.filter(
                    status__in=['pending', 'in_progress']
                )
                
                count = stuck_tasks.count()
                
                if count > 0:
                    print(f'📋 TASKS (your models):')
                    print(f'   Знайдено {count} завислих задач')
                    
                    # Оновити статус
                    stuck_tasks.update(
                        status='failed',
                        error_message='Сервер був перезапущений. Задача скасована.',
                        completed_at=timezone.now()
                    )
                    
                    print(f'   ✅ Оновлено {count} задач → status=failed')
                    
                    for task in stuck_tasks:
                        print(f'      Task #{task.id}: Fibonacci({task.number}) user={task.user.username}')
                    print()
                else:
                    print(f'📋 TASKS (your models): Завислих задач не знайдено\n')
                
                # ============================================
                # 2. ОЧИЩЕННЯ BACKGROUND TASK ТАБЛИЦЬ
                # ============================================
                try:
                    from background_task.models import Task as BackgroundTask, CompletedTask
                    
                    # Рахуємо що є
                    pending_count = BackgroundTask.objects.count()
                    completed_count = CompletedTask.objects.count()
                    
                    print(f'🔧 BACKGROUND_TASK (internal queue):')
                    print(f'   BackgroundTask: {pending_count}')
                    print(f'   CompletedTask: {completed_count}')
                    
                    if pending_count > 0 or completed_count > 0:
                        # Видаляємо ВСІ старі background tasks
                        if pending_count > 0:
                            BackgroundTask.objects.all().delete()
                            print(f'   ✅ Видалено {pending_count} BackgroundTask')
                        
                        if completed_count > 0:
                            CompletedTask.objects.all().delete()
                            print(f'   ✅ Видалено {completed_count} CompletedTask')
                        print()
                    else:
                        print(f'   ✅ Черга чиста\n')
                        
                except ImportError:
                    print('⚠️ django-background-tasks не встановлено\n')
                except Exception as e:
                    if 'no such table' not in str(e).lower():
                        print(f'⚠️ Помилка очищення background tasks: {e}\n')
                
                print(f'{"="*70}')
                print('✅ CLEANUP COMPLETED')
                print(f'{"="*70}\n')
                    
            except Exception as e:
                # Ігноруємо помилки (наприклад, якщо таблиця ще не створена)
                if 'no such table' not in str(e).lower():
                    print(f'❌ Cleanup error: {e}\n')
                    print(f'{"="*70}\n')