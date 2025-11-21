from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import json
import sys
import os
from collections import deque
from threading import Lock, Thread
import time
from datetime import datetime
import traceback

project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(project_root, 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

try:
    import django
    django.setup()
except Exception as _e:

    print(f"Django setup warning: {_e}")

from django.conf import settings

MAIN_DB_SERVER = 'http://127.0.0.1:8000'

BACKENDS = [
    {'url': 'http://127.0.0.1:8001'},
    {'url': 'http://127.0.0.1:8002'},
]

task_queue = deque()
queue_lock = Lock()

class SmartLoadBalancerHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        sys.stdout.write("%s - - [%s] %s\n" %
                         (self.address_string(),
                          self.log_date_time_string(),
                          format%args))
    
    def do_GET(self):
        if self.path == '/favicon.ico':
            self.send_response(204) 
            self.end_headers()
            return
        
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
        return self.path == '/api/tasks/' and self.command == 'POST'
    
    def is_queue_status_request(self):
        return self.path == '/api/queue-status/' and self.command == 'GET'
    
    def send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, PATCH, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
        self.send_header('Access-Control-Allow-Credentials', 'true')
    
    def proxy_request(self, method):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        headers = {}
        for key, value in self.headers.items():
            if key.lower() not in ['host', 'connection']:
                headers[key] = value

        if self.is_queue_status_request():
            self.handle_queue_status_request()
            return

        if self.is_task_creation_request():
            self.handle_task_creation(body, headers)
            return

        backend = MAIN_DB_SERVER
        
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
            print(f"Error: {e}")
    
    def handle_task_creation(self, body, headers):
        print(f"\nНОВИЙ ЗАПИТ НА СТВОРЕННЯ ЗАДАЧІ\n")
        
        try:
            task_data = json.loads(body.decode('utf-8'))
            number = task_data.get('number')
            user_id = task_data.get('user_id')
            
            if number is None or number < 0 or number > 100000:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'error': 'Invalid number. Must be between 0 and 100,000'
                }, ensure_ascii=False).encode('utf-8'))
                return
                
            with queue_lock:
                user_tasks_in_queue = [
                    t for t in task_queue
                    if json.loads(t['body'].decode('utf-8')).get('user_id') == user_id
                ]
                
                if len(user_tasks_in_queue) >= settings.MAX_TASKS_PER_USER:
                    self.send_response(429)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        'error': f'Максимальна кількість задач для користувача ({user_id}) досягнута',
                        'current_tasks': len(user_tasks_in_queue)
                    }, ensure_ascii=False).encode('utf-8'))
                    return

        except Exception as e:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Invalid request'}).encode('utf-8'))
            return

        with queue_lock:
            task_queue.append({
                'body': body,
                'headers': headers,
                'queued_at': datetime.now(),
                'number': number
            })
            queue_position = len(task_queue)
        
        wait_time = self.estimate_wait_time(queue_position)
        
        print(f"\nДАНІ ВАЛІДНІ")
        print(f"Fibonacci({number})")
        print(f"ДОДАНО В ЧЕРГУ")
        print(f"Позиція в черзі: {queue_position}")
        print(f"Очікуваний час: {wait_time}\n")
        
        self.send_response(202)
        self.send_cors_headers()
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
    
    def handle_queue_status_request(self):
        with queue_lock:
            queue_length = len(task_queue)

        if queue_length > 0:
            estimated_wait_time = self.estimate_wait_time(queue_length)
        else:
            estimated_wait_time = "0 секунд"
        
        self.send_response(200)
        self.send_cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        response_data = {
            'queue_length': queue_length,
            'estimated_wait_time': estimated_wait_time,
            'timestamp': datetime.now().isoformat()
        }
        
        self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode('utf-8'))
    
    def estimate_wait_time(self, queue_position):
        num_servers = len(BACKENDS)
        avg_time = settings.AVERAGE_TASK_TIME
        
        estimated_seconds = (queue_position / (num_servers * settings.MAX_TASKS_PER_SERVER)) * avg_time
        
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
        print(f"Помилка перевірки {server_url}: {e}")
        return None


def find_least_loaded_server():
    available_servers = []

    for backend in BACKENDS:
        server_url = backend['url']
        status = get_server_status(server_url)
        if status:
            active_tasks = status.get('in_progress', 0)
            available_slots = status.get('available_slots', 0)
            if available_slots > 0:
                available_servers.append((server_url, active_tasks))

    if not available_servers:
        return None

    server_url, _ = min(available_servers, key=lambda x: x[1])
    return server_url


def queue_processor():
    print("\nQueue Processor")
    
    check_counter = 0

    while True:
        try:
            if not task_queue:
                time.sleep(0.5)
                continue
            check_counter += 1

            if check_counter % 15 == 0:
                with queue_lock:
                    queue_len = len(task_queue)
                print(f"Queue Processor працює... (в черзі: {queue_len})")
            
            with queue_lock:
                if not task_queue:
                    continue

                print(f"   Задач в черзі: {len(task_queue)}\n")
                
                print("\n СТАН СЕРВЕРІВ:")
                server_statuses = {}
                for i, backend in enumerate(BACKENDS, 1):
                    server_url = backend['url']
                    status = get_server_status(server_url)
                    
                    if status:
                        server_statuses[server_url] = status
                        in_progress = status['in_progress']
                        available = status['available_slots']
                        
                        print(f"Сервер {i} ({server_url}):")
                        print(f"В процесі: {in_progress}/{settings.MAX_TASKS_PER_SERVER}")
                        print(f"Доступно слотів: {available}")
                        print(f"Статус: {'зайнятий' if status['busy'] else 'вільний'}")

                if task_queue:
                    task = task_queue[0]
                    
                    print(f"\nЗадача в черзі:")
                    print(f"Fibonacci({task['number']})")
                    
                    free_server = find_least_loaded_server()
                    
                    if free_server:
                        task_queue.popleft()
                        remaining = len(task_queue)

                        print(f"Сервер: {free_server}")
                        print(f"Залишилось в черзі: {remaining}")
                        
                        try:
                            response = requests.post(
                                f"{free_server}/api/tasks/",
                                data=task['body'],
                                headers=task['headers'],
                                timeout=30
                            )
                            
                            if response.status_code == 201:
                                task_data = response.json()
                                task_id = task_data.get('id', '?')
                                print(f"Задача #{task_id} успішно створена на {free_server}")
                            else:
                                print(f"Помилка створення задачі: [{response.status_code}]")
                                print(f"Відповідь: {response.text}")
                                
                        except Exception as e:
                            print(f"Помилка відправки задачі: {e}")
                            task_queue.appendleft(task)
                    
                    else:
                        print(f"\nВСІ СЕРВЕРИ ЗАЙНЯТІ")
                        print(f"8001: {server_statuses.get(BACKENDS[0]['url'], {}).get('in_progress', '?')}/2 задач")
                        print(f"8002: {server_statuses.get(BACKENDS[1]['url'], {}).get('in_progress', '?')}/2 задач")
                        print(f"Задача залишається в черзі, очікує звільнення...\n")
                
                
        except Exception as e:
            print(f"Помилка в Queue Processor: {e}")
            traceback.print_exc()


if __name__ == '__main__':
    PORT = 3000
    print(f"LOAD BALANCER")
    print(f"URL: http://localhost:{PORT}")
    print(f"\nBACKEND СЕРВЕРИ:")
    for i, backend in enumerate(BACKENDS, 1):
        print(f"   {i+1}. {backend['url']}")
    print(f"Максимум задач на сервер: {settings.MAX_TASKS_PER_SERVER}")
    print(f"Середній час виконання: {settings.AVERAGE_TASK_TIME}с")
    print(f"{'='*70}\n")

    print("Запуск Queue Processor...")
    queue_thread = Thread(target=queue_processor, daemon=True)
    queue_thread.start()
    time.sleep(1)

    print("\nРобота запущена\n")
    
    try:
        server = HTTPServer(('0.0.0.0', PORT), SmartLoadBalancerHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\nLoad Balancer зупинено!")
        print(f"Задач залишилось в черзі: {len(task_queue)}")
        server.shutdown()