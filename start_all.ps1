
Set-Location "C:\Users\ells\Desktop\prog\web-project"

$env:DJANGO_SETTINGS_MODULE = "backend.settings"

# Backend MAIN 8000 (авторизація, основні операції, фронтенд)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python backend/manage.py runserver 127.0.0.1:8000"

Start-Sleep -Seconds 3

# Backend 8001 (обробка задач #1)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:SERVER_PORT='8001'; python backend/manage.py runserver 127.0.0.1:8001"

# Backend 8002 (обробка задач #2)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:SERVER_PORT='8002'; python backend/manage.py runserver 127.0.0.1:8002"

Start-Sleep -Seconds 5

# Worker 8001 (обробник задач Фібоначчі для сервера 8001)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:SERVER_PORT='8001'; python backend/manage.py process_tasks"

# Worker 8002 (обробник задач Фібоначчі для сервера 8002)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$env:SERVER_PORT='8002'; python backend/manage.py process_tasks"

Start-Sleep -Seconds 3

# Load Balancer на порту 3000 (розподіл задач в чергу)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python load_balancer.py"

Write-Host "`n===== VCI SERVERY ZAPUSHCHENI! =====" -ForegroundColor Green
Write-Host "Frontend:      http://localhost:8000/" -ForegroundColor Cyan
Write-Host "Load Balancer: http://localhost:3000" -ForegroundColor Cyan
Write-Host "Backend API:   http://localhost:8000/api/" -ForegroundColor Cyan
Write-Host "Backend 8001:  http://localhost:8001/api/" -ForegroundColor Cyan
Write-Host "Backend 8002:  http://localhost:8002/api/" -ForegroundColor Cyan
Write-Host "====================================`n" -ForegroundColor Green