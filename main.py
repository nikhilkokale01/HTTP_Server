import os
import socket
import mimetypes
from urllib.parse import urlparse, parse_qs

class HTTPRequest:
    def __init__(self, data):
        self.method = None
        self.uri = None
        self.http_version = '1.1' 
        self.headers = {}
        self.post_data = {}  
        self.parse(data)

    def parse(self, data):
        lines = data.split(b'\r\n')
        request_line = lines[0] 
        words = request_line.split(b' ') 
        self.method = words[0].decode() 
        if len(words) > 1:
            self.uri = words[1].decode() 
            parsed_url = urlparse(self.uri)
            self.uri = parsed_url.path
            self.query_params = parse_qs(parsed_url.query)
        if len(words) > 2:
            self.http_version = words[2]


        # Parse headers
        for line in lines[1:]:
            if not line:
                break
            header, value = line.split(b':', 1)
            self.headers[header.decode().strip()] = value.decode().strip()

        # Parse POST data if it exists
        if self.method == 'POST':
            self.parse_post_data(lines[-1])

    def parse_post_data(self, post_data):
        if post_data:
            post_params = post_data.split(b'&')
            for param in post_params:
                key, value = param.split(b'=')
                key = key.decode()
                value = value.decode()
                if key not in self.post_data:
                    self.post_data[key] = [value]
                else:
                    self.post_data[key].append(value)

class TCPServer:
    def __init__(self, host='127.0.0.1', port=8888):
        self.host = host
        self.port = port

    def start(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.host, self.port))
        s.listen(5)
        print("Listening at", s.getsockname())
        while True:
            conn, addr = s.accept()
            print("Connected by", addr)
            data = conn.recv(1024) 
            response = self.handle_request(data)
            conn.sendall(response)                                                          
            conn.close()

    def handle_request(self, data):
        return data

class HTTPServer(TCPServer):
    headers = {
        'Server': 'CrudeServer',
        'Content-Type': 'text/html',
    }

    status_codes = {
        200: 'OK',
        400:'Bad Request',
        404: 'Not Found',
        501: 'Not Implemented',
        
    }


    
    # Dictionary to store submitted data
    student_data = {}

    def handle_request(self, data):
        try:
            request = HTTPRequest(data)
            handler = getattr(self, 'handle_%s' % request.method, self.HTTP_501_handler)
            response = handler(request)
        except ValueError:
            response = self.handle_bad_request()

        return response

    
    def response_line(self, status_code):
        reason = self.status_codes[status_code]
        response_line = 'HTTP/1.1 %s %s\r\n' % (status_code, reason)
        return response_line.encode() 

    def response_headers(self, extra_headers=None):
        headers_copy = self.headers.copy() 
        if extra_headers:
            headers_copy.update(extra_headers)
        headers = ''
        for h in headers_copy:
            headers += '%s: %s\r\n' % (h, headers_copy[h])
        return headers.encode() 

    def handle_OPTIONS(self, request):
        response_line = self.response_line(200)
        extra_headers = {'Allow': 'OPTIONS, GET, POST'}
        response_headers = self.response_headers(extra_headers)
        blank_line = b'\r\n'
        return b''.join([response_line, response_headers, blank_line])
    


    def handle_GET(self,request):
        path = request.uri.strip('/') 
        if not path:
            path = 'index.html'

        try:
            with open(path, 'rb') as f:
                response_body = f.read()
                response_line = self.response_line(200)
                content_type = mimetypes.guess_type(path)[0] or 'text/html'
                extra_headers = {'Content-Type': content_type}
                response_headers = self.response_headers(extra_headers)
                blank_line = b'\r\n'
                response = b''.join([response_line, response_headers, blank_line, response_body])

        except FileNotFoundError:
            response_line = self.response_line(404)
            response_headers = self.response_headers()
            response_body = b'<h1>404 Not Found</h1>'
            blank_line = b'\r\n'
            response = b''.join([response_line, response_headers, blank_line, response_body])

        return response 
    
    def handle_POST(self, request):
        path = request.uri.strip('/')
        if path == 'submit':
            if 'name' in request.post_data and 'mis' in request.post_data:
                name = request.post_data['name'][0]
                mis = request.post_data['mis'][0]

                if name and mis:
                    
                    self.student_data[name] = mis
                    response_line = self.response_line(200)  # Created
                    response_headers = self.response_headers()
                    
                    response_body = f'<h1>Student data submitted successfully. Name: {name.replace("+", " ")}, MIS: {mis}</h1>'.encode()

                else:
                    response_line = self.response_line(400)  # Bad Request
                    response_headers = self.response_headers()
                    response_body = b'<h1>400 Bad Request: "name" and "mis" parameters cannot be empty</h1>'
    
                

            
            else:
                response_line = self.response_line(400)  # Bad Request
                response_headers = self.response_headers()
                response_body = b'<h1>400 Bad Request: Missing "name" or "mis" parameter</h1>'
        else:
            response_line = self.response_line(404)
            response_headers = self.response_headers()
            response_body = b'<h1>404 Not Found</h1>'

        blank_line = b'\r\n'
        response = b''.join([response_line, response_headers, blank_line, response_body])
        return response
    
    def handle_DELETE(self, request):
        path = request.uri.strip('/')
        
        if os.path.exists(path) and not os.path.isdir(path):
            # Check if the resource (text file) exists
            os.remove(path)
            response_line = self.response_line(200)  # OK
            response_headers = self.response_headers()
            blank_line = b'\r\n'
            response_body = f'<h1>Resource {path} deleted successfully</h1>'.encode()
        else:
            # Resource not found
            response_line = self.response_line(404)  # Not Found
            response_headers = self.response_headers()
            response_body = b'<h1>404 Not Found</h1>'

        # Construct and return the response
        return b"".join([response_line, response_headers, blank_line, response_body])
    
    def handle_404(self, request):
        response_line = self.response_line(404)
        response_headers = self.response_headers()
        response_body = b'<h1>404 Not Found</h1>'
        blank_line = b'\r\n'
        response = b''.join([response_line, response_headers, blank_line, response_body])
        return response
    

    def handle_400(self):
        response_line = self.response_line(400)
        response_headers = self.response_headers()
        blank_line = b'\r\n'
        response_body = b'<h1>400 Bad Request: Invalid HTTP request</h1>'
        return b"".join([response_line, response_headers, blank_line, response_body])
    
    def HTTP_501_handler(self, request):
        response_line = self.response_line(status_code=501)
        response_headers = self.response_headers()
        blank_line = b'\r\n'
        response_body = b'<h1>501 Not Implemented</h1>'
        return b"".join([response_line, response_headers, blank_line, response_body])
    
    

if __name__ == '__main__':
    server = HTTPServer()
    server.start()
