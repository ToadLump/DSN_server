# Here is a skeleton code you may use as a starting point.
# This is a very basic HTTP server which listens on port 8080,
# and serves the same response messages regardless of the browser's request.
# It runs on python v3
# Usage: execute this program, open your browser (preferably chrome) and type http://servername:8080
# e.g. if server.py and browser are running on the same machine, then use http://localhost:8080
# Import the required libraries
from socket import *
import multiprocessing as mp
import os.path
import mimetypes


class Server:
    header_statuses = {"OK": "HTTP/1.1 200 OK",
                       "Not Found": "HTTP/1.1 404 Not Found",
                       "Not For You": "HTTP/1.1 571 Not For You",
                       "Bad Request": "HTTP/1.1 400 Bad Request"}

    def __init__(self, host_name, port, use_multiprocessing=False):
        import logging
        self.logger = logging.getLogger('server')
        logging.basicConfig(level=logging.INFO)

        self.use_multiprocessing = use_multiprocessing
        self.num_processes = mp.cpu_count()

        self.serverPort = port
        self.host_name = host_name
        self.server_socket = socket(AF_INET, SOCK_STREAM)

    def start(self):
        self.logger.info((self.host_name, self.serverPort))
        # Bind the server socket to the port
        self.server_socket.bind((self.host_name, self.serverPort))

        # Start listening for new connections
        self.server_socket.listen(1)

        self.logger.info('The server is ready to receive messages')

        if self.use_multiprocessing:
            self.handle_with_multiprocessing()
        else:
            self.handle_with_single_processing()

    def handle_with_single_processing(self):
        while True:
            connection, address = self.server_socket.accept()
            self.logger.debug("Got connection")
            self.respond_to_request(connection)

    def handle_with_multiprocessing(self):
        while True:
            connection, address = self.server_socket.accept()
            self.logger.debug("Got connection")
            process = mp.Process(target=self.respond_to_request, args=(connection,))
            process.daemon = True
            process.start()
            self.logger.debug("Started process %r", process)

    def respond_to_request(self, connection_socket):
        # Retrieve the message sent by the client
        request = connection_socket.recv(1024)

        # Stops issues from empty requests
        if request == '':
            return

        import logging
        logger = logging.getLogger(str(os.getpid()))
        logging.basicConfig(level=logging.INFO)
        logger.debug('starting connection: {}'.format(str(connection_socket)))

        decoded_request = request.decode()
        requested_path, request_valid = self.determine_requested_path(decoded_request)
        response_status = self.get_response_status(requested_path, request_valid)
        if response_status == 'OK':
            should_send_body = True
        else:
            should_send_body = False

        logger.debug('file requested: {}'.format(requested_path))
        header_response = self.generate_header(response_status, requested_path)

        # Send HTTP response back to the client
        try:
            connection_socket.send(header_response.encode())
            if should_send_body:
                self.send_response_body(requested_path, connection_socket)
        except OSError:
            logger.error('send interrupted')

        # Close the connection
        connection_socket.close()
        logger.debug('closed connection: {}'.format(str(connection_socket)))

    @staticmethod
    def determine_requested_path(request_header):
        first_line = request_header.partition('\n')[0]
        first_line_split = first_line.split(' ')
        if first_line_split[0] != 'GET':
            return '', False
        path = first_line_split[1]
        path = path[1:]
        if path == '':
            path = 'index.html'
        return path, True

    @staticmethod
    def get_response_status(path, request_valid):
        if not request_valid:
            return 'Bad Request'
        if os.path.exists(path):
            if os.path.isdir(path):
                path += 'index.html'
            if os.path.isfile(path):
                requested_dir = os.path.dirname(os.path.abspath(path))
                my_base_dir = os.path.dirname(os.path.abspath('index.html'))
                if requested_dir.find(my_base_dir) == 0:
                    return 'OK'
                else:
                    return 'Not For You'
        else:
            return 'Not Found'

    def generate_header(self, response_status, path):
        status_line = self.header_statuses[response_status] + '\r\n'
        if response_status == 'OK':
            mime_type = mimetypes.guess_type(os.path.basename(path))[0]
            additional_header_lines = "Content-Type: " + mime_type + '\r\n'
        else:
            additional_header_lines = ''
        return status_line + additional_header_lines + '\r\n'

    @staticmethod
    def send_response_body(path, connection_socket):
        with open(path, 'rb') as file:
            connection_socket.send(file.read())


processes = []
if __name__ == '__main__':
    server = Server('', 8080, use_multiprocessing=False)
    server.start()
