from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import json
import sys
from collections import deque
from threading import Lock, Thread
import time
import traceback

# Список серверів
BACKENDS = [
    {'url': 'http://127.0.0.1:8001', 'busy': False},
    {'url': 'http://127.0.0.1:8002', 'busy': False},
]

# Черга очікування завдань
task_queue = deque()
queue_lock = Lock()

class SmartLoadBalancerHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        sys.stdout.write("%s - - [%s] %s\n" %
                         (self.address_string(),
                          self.log_date_time_string(),
                          format%args))
    
    def do_GET(self):
        self.proxy_request('GET')
    
    def do_POST(self):
        self.proxy_request('POST')
    
    def do_PUT(self):
        self.proxy_request('PUT')
    
    def do_DELETE(self):
        self.proxy_request('DELETE')
    
    def do_PATCH(self):
        self.proxy_request('PATCH')
    
    def is_task_creation_request(self):
        """Перевірка чи це запит на створення задачі"""
        return self.path == '/api/tasks/' and self.command == 'POST'
    
    def check_server_busy(self, server_url):
        """Перевірити чи сервер зараз обчислює задачу"""
        try:
            response = requests.get(
                f"{server_url}/api/server-status/",
                timeout=3
            )
            if response.status_code == 200:
                data = response.json()
                is_busy = data.get('busy', False)
                active = data.get('active_tasks', 0)
                return is_busy, active
            return False, 0
        except Exception as e:
            print(f"Помилка перевірки {server_url}: {e}")
            return False, 0
    
    def find_free_server(self):
        servers = ["http://127.0.0.1:8001", "http://127.0.0.1:8002"]
        best_server = None
        min_tasks = float('inf')

        for server in servers:
            try:
                r = requests.get(f"{server}/api/server-status/", timeout=1)
                data = r.json()
                if data["active_tasks"] < min_tasks:
                    best_server = server
                    min_tasks = data["active_tasks"]
            except Exception as e:
                print(f"Помилка з {server}: {e}")
                continue

        return best_server
    
    def proxy_request(self, method):
        # Читаємо тіло запиту
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else None
        
        # Копіюємо headers
        headers = {}
        for key, value in self.headers.items():
            if key.lower() not in ['host', 'connection']:
                headers[key] = value
        
        # Спеціальна логіка для створення задач
        if self.is_task_creation_request():
            self.handle_task_creation(body, headers)
            return
        
        # Для інших запитів - перший сервер
        backend = BACKENDS[0]['url']
        
        try:
            response = requests.request(
                method=method,
                url=backend + self.path,
                data=body,
                headers=headers,
                timeout=300,
                allow_redirects=False
            )
            
            self.send_response(response.status_code)
            for key, value in response.headers.items():
                if key.lower() not in ['content-encoding', 'transfer-encoding', 'connection']:
                    self.send_header(key, value)
            self.end_headers()
            self.wfile.write(response.content)
            
            print(f"[{method}] {self.path} -> {backend} [{response.status_code}]")
            
        except Exception as e:
            self.send_error(502, f"Bad Gateway: {str(e)}")
            print(f"Error: {e}")
    
    def handle_task_creation(self, body, headers):
        """Обробка створення задачі з інтелектуальним розподілом"""
        
        print(f"\n{'='*60}")
        print(f"НОВИЙ ЗАПИТ НА СТВОРЕННЯ ЗАДАЧІ")
        print(f"{'='*60}")
        
        # Крок 1: Шукаємо вільний сервер
        free_server = self.find_free_server()
        
        if free_server:
            # Є вільний сервер - відправляємо задачу
            print(f"Відправляємо задачу на {free_server}")
            self.send_task_to_server(free_server, body, headers)
        else:
            # Всі сервери зайняті - додаємо в чергу
            with queue_lock:
                task_queue.append({
                    'body': body,
                    'headers': headers,
                })
                queue_position = len(task_queue)
            
            print(f"   Задача додана в чергу очікування")
            print(f"   Позиція в черзі: {queue_position}")
            print(f"   Загальна довжина черги: {queue_position}")
            
            # Відповідаємо клієнту що задача в черзі
            self.send_response(202)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            response_data = {
                'status': 'queued',
                'message': f'Всі сервери зайняті. Задача в черзі очікування.',
                'queue_position': queue_position,
                'queue_length': queue_position
            }
            
            self.wfile.write(json.dumps(response_data).encode())
        
        print(f"{'='*60}\n")
    
    def send_task_to_server(self, server_url, body, headers):
        """Відправити задачу на конкретний сервер"""
        try:
            response = requests.post(
                f"{server_url}/api/tasks/",
                data=body,
                headers=headers,
                timeout=30
            )
            
            self.send_response(response.status_code)
            for key, value in response.headers.items():
                if key.lower() not in ['content-encoding', 'transfer-encoding', 'connection']:
                    self.send_header(key, value)
            self.end_headers()
            self.wfile.write(response.content)
            
            if response.status_code == 201:
                # Отримуємо ID задачі з відповіді
                try:
                    task_data = response.json()
                    task_id = task_data.get('id', '?')
                    print(f"   ЗАДАЧА #{task_id} УСПІШНО ПРИЙНЯТА")
                    print(f"   Сервер: {server_url}")
                    print(f"   Статус: [{response.status_code}]")
                except:
                    print(f"ЗАДАЧА УСПІШНО ПРИЙНЯТА [{response.status_code}]")
            else:
                print(f"Відповідь сервера: [{response.status_code}]")
                
        except Exception as e:
            self.send_error(502, f"Server Error: {str(e)}")
            print(f"Помилка відправки на {server_url}: {e}")


def queue_processor():
    """Фоновий процес для обробки черги"""
    print("Queue Processor ЗАПУЩЕНО!\n")
    
    check_counter = 0
    
    while True:
        try:
            time.sleep(3)  # Перевіряємо чергу кожні 3 секунди
            check_counter += 1
            
            # Показуємо що процесор живий
            if check_counter % 10 == 0:
                print(f"Queue Processor працює... (перевірок: {check_counter})")
            
            with queue_lock:
                if not task_queue:
                    continue
                
                print(f"\n{'='*60}")
                print(f"QUEUE PROCESSOR: Перевірка черги")
                print(f"   Задач в черзі: {len(task_queue)}")
                print(f"{'='*60}")
                
                # Шукаємо вільний сервер
                free_server = None
                for i, backend in enumerate(BACKENDS):
                    try:
                        response = requests.get(
                            f"{backend['url']}/api/server-status/",
                            timeout=3
                        )
                        if response.status_code == 200:
                            data = response.json()
                            is_busy = data.get('busy', False)
                            active = data.get('active_tasks', 0)

                            print(f"   {backend['url']}: {'ЗАЙНЯТИЙ' if is_busy else 'ВІЛЬНИЙ'} ({active} задач)")
                            
                            if not is_busy:
                                free_server = backend['url']
                                break
                    except Exception as e:
                        print(f"  Помилка перевірки {backend['url']}: {e}")
                
                # Якщо знайшли вільний сервер - обробляємо задачу з черги
                if free_server and task_queue:
                    task = task_queue.popleft()
                    remaining = len(task_queue)
                    
                    print(f"\n ОБРОБКА ЗАДАЧІ З ЧЕРГИ")
                    print(f"   Відправляємо на: {free_server}")
                    print(f"   Залишилось в черзі: {remaining}")
                    
                    try:
                        response = requests.post(
                            f"{free_server}/api/tasks/",
                            data=task['body'],
                            headers=task['headers'],
                            timeout=30
                        )
                        
                        if response.status_code == 201:
                            print(f"Задача з черги УСПІШНО оброблена! [{response.status_code}]")
                        else:
                            print(f"Задача оброблена з помилкою: [{response.status_code}]")
                            
                    except Exception as e:
                        print(f"Помилка обробки задачі з черги: {e}")
                        # Повертаємо задачу в чергу
                        task_queue.append(task)
                        print(f"   Задача повернута в чергу")
                else:
                    if task_queue:
                        print(f"Всі сервери ще зайняті. Чекаємо...")
                
                print(f"{'='*60}\n")
                
        except Exception as e:
            print(f"КРИТИЧНА ПОМИЛКА в Queue Processor: {e}")
            traceback.print_exc()


if __name__ == '__main__':
    PORT = 8000

    print(f"URL: http://localhost:{PORT}")
    print(f"Backend серверів: {len(BACKENDS)}")
    for i, backend in enumerate(BACKENDS, 1):
        print(f"   {i}. {backend['url']}")
    print("\nЗапуск компонентів...\n")
    
    # Запускаємо Queue Processor у фоні
    print("Запуск Queue Processor...")
    queue_thread = Thread(target=queue_processor, daemon=True)
    queue_thread.start()
    time.sleep(0.5)
    
    print("Запуск HTTP сервера...")
    print("\n" + "=" * 70)
    print("ВСЕ ГОТОВО! Очікую запитів...")
    print("=" * 70)
    
    try:
        server = HTTPServer(('0.0.0.0', PORT), SmartLoadBalancerHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n" + "=" * 70)
        print("Load Balancer зупинено!")
        print(f"Задач в черзі: {len(task_queue)}")
        print("=" * 70)
        server.shutdown()