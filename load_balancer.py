from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import itertools
import sys

# Список backend серверів (round-robin - по черзі)
BACKENDS = itertools.cycle([
    'http://127.0.0.1:8001',
    'http://127.0.0.1:8002',
])

class LoadBalancerHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        """Кастомний лог для кращої читабельності"""
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
    
    def proxy_request(self, method):
        # Вибираємо наступний сервер
        backend = next(BACKENDS)
        url = backend + self.path
        
        # Читаємо тіло запиту
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else None
        
        # Копіюємо headers
        headers = {}
        for key, value in self.headers.items():
            if key.lower() not in ['host', 'connection']:
                headers[key] = value
        
        try:
            # Проксуємо запит
            response = requests.request(
                method=method,
                url=url,
                data=body,
                headers=headers,
                timeout=300,  # 5 хвилин для довгих задач
                allow_redirects=False
            )
            
            # Відправляємо відповідь клієнту
            self.send_response(response.status_code)
            
            # Копіюємо response headers
            for key, value in response.headers.items():
                if key.lower() not in ['content-encoding', 'transfer-encoding', 'connection']:
                    self.send_header(key, value)
            
            self.end_headers()
            self.wfile.write(response.content)
            
            # Лог
            print(f"✅ [{method}] {self.path} -> {backend} [{response.status_code}]")
            
        except requests.exceptions.ConnectionError:
            self.send_error(502, f"Backend server unavailable: {backend}")
            print(f"❌ Backend {backend} не відповідає!")
            
        except Exception as e:
            self.send_error(502, f"Bad Gateway: {str(e)}")
            print(f"❌ Error: {e}")

if __name__ == '__main__':
    PORT = 8000  # Використовуємо порт 8000 (не потрібні права адміністратора)
    
    print("=" * 60)
    print("🚀 Load Balancer запущено!")
    print("=" * 60)
    print(f"📍 URL: http://localhost:{PORT}")
    print(f"🔄 Backend серверів: 2")
    print(f"   - http://127.0.0.1:8001")
    print(f"   - http://127.0.0.1:8002")
    print(f"⚖️  Метод: Round Robin (по черзі)")
    print("=" * 60)
    print("Натисніть Ctrl+C для зупинки\n")
    
    try:
        server = HTTPServer(('0.0.0.0', PORT), LoadBalancerHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Load Balancer зупинено!")
        server.shutdown()