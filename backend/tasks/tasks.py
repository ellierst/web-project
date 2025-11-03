from background_task import background
from django.utils import timezone
from .models import Task
import time

PROGRESS_UPDATES = 100
CANCELLATION_CHECKS = 100

@background(schedule=0)
def calculate_fibonacci_task(task_id, n):
    """Background task для обчислення чисел Фібоначчі"""
    try:
        task = Task.objects.get(id=task_id)
        task.status = 'in_progress'
        task.started_at = timezone.now()
        task.save()
        
        if n == 0:
            result = "0"
        elif n == 1:
            result = "1"
        else:
            a, b = 0, 1
            progress_interval = max(1, n // PROGRESS_UPDATES)
            cancel_check_interval = max(1, n // CANCELLATION_CHECKS)
            
            for i in range(2, n + 1):
                a, b = b, a + b
                
                time.sleep(0.5)

                # Update progress
                if i % progress_interval == 0:
                    progress = int((i / n) * 100)
                    task.refresh_from_db()
                    
                    # Check if cancelled
                    if task.status == 'cancelled':
                        return
                    
                    task.progress = min(progress, 99)
                    task.save(update_fields=['progress'])
                
                # Periodic cancellation check
                if i % cancel_check_interval == 0:
                    task.refresh_from_db()
                    if task.status == 'cancelled':
                        return
            
            result = str(b)
            
            # Format large numbers
            if len(result) > 10:
                result = f"{result[0]}.{result[1:10]}E+{len(result) - 1}"
        
        # Save result
        task.refresh_from_db()
        if task.status != 'cancelled':
            task.result = result
            task.progress = 100
            task.status = 'completed'
            task.completed_at = timezone.now()
            task.save()
        
    except Task.DoesNotExist:
        pass
    except Exception as e:
        try:
            task = Task.objects.get(id=task_id)
            task.status = 'failed'
            task.error_message = str(e)
            task.completed_at = timezone.now()
            task.save()
        except:
            pass