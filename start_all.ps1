Set-Location "C:\Users\ells\Desktop\prog\web-project"
$env:DJANGO_SETTINGS_MODULE = "backend.settings"

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Users\ells\Desktop\prog\web-project; python manage.py runserver 127.0.0.1:8000"
Start-Sleep -Seconds 3

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Users\ells\Desktop\prog\web-project; `$env:SERVER_PORT='8001'; python manage.py runserver 127.0.0.1:8001"

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Users\ells\Desktop\prog\web-project; `$env:SERVER_PORT='8002'; python manage.py runserver 127.0.0.1:8002"
Start-Sleep -Seconds 5

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Users\ells\Desktop\prog\web-project; `$env:SERVER_PORT='8001'; python manage.py process_tasks"

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Users\ells\Desktop\prog\web-project; `$env:SERVER_PORT='8002'; python manage.py process_tasks"
Start-Sleep -Seconds 3

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\Users\ells\Desktop\prog\web-project; python load_balancer.py"