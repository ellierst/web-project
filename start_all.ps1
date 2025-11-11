# start_all.ps1 — запускати з C:\Users\ells\Desktop\prog\web-project
Set-Location "C:\Users\ells\Desktop\prog\web-project"

$env:DJANGO_SETTINGS_MODULE = "backend.settings"

# Backend 8001
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:SERVER_PORT='8001'; python backend/manage.py runserver 127.0.0.1:8001"

# Backend 8002
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:SERVER_PORT='8002'; python backend/manage.py runserver 127.0.0.1:8002"

Start-Sleep -Seconds 5

# Worker 8001
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:SERVER_PORT='8001'; python backend/manage.py process_tasks"

# Worker 8002
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:SERVER_PORT='8002'; python backend/manage.py process_tasks"

Start-Sleep -Seconds 3

# Load Balancer
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python load_balancer.py"

Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location 'frontend'; python -m http.server 3000"