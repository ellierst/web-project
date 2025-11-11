from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import json
import sys
from collections import deque
from threading import Lock, Thread
import time
from datetime import datetime, timedelta
import traceback

AVERAGE_TASK_TIME = 30 
MAX_TASKS_PER_SERVER = 2  # Максимум 2 задачі in_progress на сервері

# Список серверів
BACKENDS = [
    {'url': 'http://127.0.0.1:8001'},
    {'url': 'http://127.0.0.1:8002'},
]

# ЧЕРГА ОЧІКУВАННЯ - тут зберігаються ВСІ задачі до розподілу
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

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()
    
    def is_task_creation_request(self):
        """Перевірка чи це запит на створення задачі"""
        return self.path == '/api/tasks/' and self.command == 'POST'
    
    def send_cors_headers(self):
        """Додає CORS заголовки до відповіді"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, PATCH, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
        self.send_header('Access-Control-Allow-Credentials', 'true')
    
    def proxy_request(self, method):
        # Читаємо тіло запиту
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else None
        
        # Копіюємо headers
        headers = {}
        for key, value in self.headers.items():
            if key.lower() not in ['host', 'connection']:
                headers[key] = value
        
        # Спеціальна логіка для створення задач - ДОДАЄМО В ЧЕРГУ
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
            self.send_cors_headers()

            for key, value in response.headers.items():
                if key.lower() not in ['content-encoding', 'transfer-encoding', 'connection']:
                    self.send_header(key, value)
            self.end_headers()
            self.wfile.write(response.content)
            
        except Exception as e:
            self.send_error(502, f"Bad Gateway: {str(e)}")
            print(f"❌ Error: {e}")
    
    def handle_task_creation(self, body, headers):
        """
        Фронт надсилає запит на створення задачі
        Load Balancer додає її в ЧЕРГУ (не створює відразу в БД!)
        """
        
        print(f"\n{'='*70}")
        print(f"📥 НОВИЙ ЗАПИТ НА СТВОРЕННЯ ЗАДАЧІ")
        print(f"{'='*70}")
        
        # Перевіряємо валідність даних
        try:
            task_data = json.loads(body.decode('utf-8'))
            number = task_data.get('number')
            
            if number is None or number < 0 or number > 1000000:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'error': 'Invalid number. Must be between 0 and 1,000,000'
                }, ensure_ascii=False).encode('utf-8'))
                return
                
        except Exception as e:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Invalid request'}).encode('utf-8'))
            return
        
        # Додаємо задачу в ЧЕРГУ
        with queue_lock:
            task_queue.append({
                'body': body,
                'headers': headers,
                'queued_at': datetime.now(),
                'number': number
            })
            queue_position = len(task_queue)
        
        wait_time = self.estimate_wait_time(queue_position)
        
        print(f"✅ ДАНІ ВАЛІДНІ")
        print(f"📊 Fibonacci({number})")
        print(f"⏳ ДОДАНО В ЧЕРГУ")
        print(f"   Позиція в черзі: {queue_position}")
        print(f"   Очікуваний час: {wait_time}")
        print(f"{'='*70}\n")
        
        # Відповідаємо фронту що задача прийнята і в черзі
        self.send_response(202)
        self.send_cors_headers()  # 202 Accepted
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        response_data = {
            'status': 'queued',
            'message': 'Задача прийнята і додана в чергу обробки',
            'queue_position': queue_position,
            'queue_length': queue_position,
            'estimated_wait_time': wait_time,
            'queued_at': datetime.now().isoformat(),
            'number': number
        }
        
        self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode('utf-8'))
    
    def estimate_wait_time(self, queue_position):
        """Розрахувати приблизний час очікування"""
        num_servers = len(BACKENDS)
        avg_time = AVERAGE_TASK_TIME
        
        estimated_seconds = (queue_position / (num_servers * MAX_TASKS_PER_SERVER)) * avg_time
        
        if estimated_seconds < 60:
            return f"{int(estimated_seconds)} секунд"
        elif estimated_seconds < 3600:
            minutes = int(estimated_seconds / 60)
            return f"{minutes} хвилин"
        else:
            hours = int(estimated_seconds / 3600)
            minutes = int((estimated_seconds % 3600) / 60)
            return f"{hours} год {minutes} хв"


def get_server_status(server_url):
    """Отримати статус сервера"""
    try:
        response = requests.get(
            f"{server_url}/api/server-status/",
            timeout=3
        )
        if response.status_code == 200:
            data = response.json()
            return {
                'busy': data.get('busy', False),
                'in_progress': data.get('in_progress_tasks', 0),
                'available_slots': data.get('available_slots', 0),
            }
        return None
    except Exception as e:
        print(f"⚠️ Помилка перевірки {server_url}: {e}")
        return None


def find_free_server():
    """
    Знайти сервер з вільним слотом
    Перевіряє по порядку: 8001, потім 8002
    """
    for backend in BACKENDS:
        server_url = backend['url']
        status = get_server_status(server_url)
        
        if status and not status['busy'] and status['available_slots'] > 0:
            return server_url

        time.sleep(1)
    return None


def queue_processor():
    """
    ГОЛОВНИЙ ПРОЦЕСОР ЧЕРГИ
    Витягує задачі з черги і розподіляє по серверах
    """
    print("🔄 Queue Processor ЗАПУЩЕНО!")
    print("📋 Алгоритм:")
    print("   1. Витягує задачу з черги")
    print("   2. Перевіряє 8001 - якщо < 2 задач → відправляє")
    print("   3. Якщо 8001 зайнятий → перевіряє 8002")
    print("   4. Якщо обидва зайняті → задача залишається в черзі")
    print("   5. Повторює кожні 2 секунди\n")
    
    check_counter = 0
    
    while True:
        try:
            time.sleep(2)
            check_counter += 1
            
            # Показуємо що процесор живий
            if check_counter % 15 == 0:
                with queue_lock:
                    queue_len = len(task_queue)
                print(f"💓 Queue Processor працює... (перевірок: {check_counter}, в черзі: {queue_len})")
            
            with queue_lock:
                if not task_queue:
                    continue
                
                print(f"\n{'='*70}")
                print(f"🔍 ОБРОБКА ЧЕРГИ")
                print(f"   Задач в черзі: {len(task_queue)}")
                print(f"{'='*70}")
                
                # Перевіряємо стан серверів
                print("\n📊 СТАН СЕРВЕРІВ:")
                server_statuses = {}
                for i, backend in enumerate(BACKENDS, 1):
                    server_url = backend['url']
                    status = get_server_status(server_url)
                    
                    if status:
                        server_statuses[server_url] = status
                        in_progress = status['in_progress']
                        available = status['available_slots']
                        
                        print(f"   Сервер {i} ({server_url}):")
                        print(f"      In Progress: {in_progress}/{MAX_TASKS_PER_SERVER}")
                        print(f"      Доступно слотів: {available}")
                        print(f"      Статус: {'🔴 ЗАЙНЯТИЙ' if status['busy'] else '🟢 ВІЛЬНИЙ'}")
                
                # Витягуємо ПЕРШУ задачу з черги (не видаляємо поки не відправимо!)
                if task_queue:
                    task = task_queue[0]  # Дивимось на першу, але не видаляємо
                    
                    print(f"\n📦 НАСТУПНА ЗАДАЧА В ЧЕРЗІ:")
                    print(f"   Fibonacci({task['number']})")
                    print(f"   У черзі з: {task['queued_at'].strftime('%H:%M:%S')}")
                    
                    # Шукаємо вільний сервер (спочатку 8001, потім 8002)
                    free_server = find_free_server()
                    
                    if free_server:
                        # Знайшли вільний сервер!
                        task_queue.popleft()  # ТЕПЕР видаляємо з черги
                        remaining = len(task_queue)
                        
                        print(f"\n✅ ВІДПРАВКА ЗАДАЧІ")
                        print(f"   Сервер: {free_server}")
                        print(f"   Залишилось в черзі: {remaining}")
                        
                        try:
                            # Відправляємо задачу на бекенд для створення в БД
                            response = requests.post(
                                f"{free_server}/api/tasks/",
                                data=task['body'],
                                headers=task['headers'],
                                timeout=30
                            )
                            
                            if response.status_code == 201:
                                task_data = response.json()
                                task_id = task_data.get('id', '?')
                                print(f"✅ Задача #{task_id} успішно створена на {free_server}")
                                print(f"   Статус: IN_PROGRESS")
                                time.sleep(2)
                            else:
                                print(f"⚠️ Помилка створення задачі: [{response.status_code}]")
                                print(f"   Відповідь: {response.text}")
                                
                        except Exception as e:
                            print(f"❌ Помилка відправки задачі: {e}")
                            # Повертаємо задачу на початок черги
                            task_queue.appendleft(task)
                            print(f"   ↩️ Задача повернута на початок черги")
                    
                    else:
                        # Всі сервери зайняті - задача залишається в черзі
                        print(f"\n⏳ ВСІ СЕРВЕРИ ЗАЙНЯТІ")
                        print(f"   8001: {server_statuses.get(BACKENDS[0]['url'], {}).get('in_progress', '?')}/2 задач")
                        print(f"   8002: {server_statuses.get(BACKENDS[1]['url'], {}).get('in_progress', '?')}/2 задач")
                        print(f"   Задача залишається в черзі, очікує звільнення...")
                
                print(f"{'='*70}\n")
                
        except Exception as e:
            print(f"🔥 КРИТИЧНА ПОМИЛКА в Queue Processor: {e}")
            traceback.print_exc()


if __name__ == '__main__':
    PORT = 8000

    print(f"\n{'='*70}")
    print(f"🚀 SMART LOAD BALANCER (QUEUE MASTER)")
    print(f"{'='*70}")
    print(f"🌐 URL: http://localhost:{PORT}")
    print(f"\n🔧 BACKEND СЕРВЕРИ:")
    for i, backend in enumerate(BACKENDS, 1):
        print(f"   {i}. {backend['url']}")
    print(f"\n⚙️ НАЛАШТУВАННЯ:")
    print(f"   Максимум задач на сервер: {MAX_TASKS_PER_SERVER}")
    print(f"   Середній час виконання: {AVERAGE_TASK_TIME}с")
    print(f"\n📋 ПРИНЦИП РОБОТИ:")
    print(f"   1. Фронт → Load Balancer: запит на створення задачі")
    print(f"   2. Load Balancer перевіряє дані → додає в чергу")
    print(f"   3. Queue Processor витягує з черги → шукає вільний сервер")
    print(f"   4. Знайшов вільний → створює задачу в БД на цьому сервері")
    print(f"   5. Не знайшов → задача залишається в черзі")
    print(f"{'='*70}\n")
    
    # Запускаємо Queue Processor у фоні
    print("🔄 Запуск Queue Processor...")
    queue_thread = Thread(target=queue_processor, daemon=True)
    queue_thread.start()
    time.sleep(1)
    
    print("🌐 Запуск HTTP сервера...")
    print("\n" + "=" * 70)
    print("✅ ВСЕ ГОТОВО! Очікую запитів...")
    print("=" * 70 + "\n")
    
    try:
        server = HTTPServer(('0.0.0.0', PORT), SmartLoadBalancerHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n" + "=" * 70)
        print("🛑 Load Balancer зупинено!")
        print(f"📊 Задач залишилось в черзі: {len(task_queue)}")
        print("=" * 70)
        server.shutdown()