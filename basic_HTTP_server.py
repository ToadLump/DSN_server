from socket import *
import multiprocessing as mp
import os.path
import mimetypes
import urllib.parse
import logging

import Time_Handler
import HTTP_Handler


class Server:
    header_statuses = {"OK": "HTTP/1.1 200 OK",
                       "Not Found": "HTTP/1.1 404 Not Found",
                       "Not For You": "HTTP/1.1 571 Not For You",
                       "Bad Request": "HTTP/1.1 400 Bad Request",
                       "Not Modified": "HTTP/1.1 304 Not Modified"}

    logger = logging.getLogger('server')
    logging.basicConfig(level=logging.INFO)

    accepted_http_methods = ['GET', 'HEAD', 'POST']

    def __init__(self, host_name, port, use_multiprocessing=False):
        self.use_multiprocessing = use_multiprocessing
        self.num_processes = mp.cpu_count()

        self.serverPort = port
        self.host_name = host_name
        self.server_socket = socket(AF_INET, SOCK_STREAM)

    def start(self):
        Server.logger.info((self.host_name, self.serverPort))
        # Bind the server socket to the port
        self.server_socket.bind((self.host_name, self.serverPort))

        # Start listening for new connections
        self.server_socket.listen(1)

        Server.logger.info('The server is ready to receive messages')

        if self.use_multiprocessing:
            self.handle_with_multiprocessing()
        else:
            self.handle_with_single_processing()

    def handle_with_single_processing(self):
        while True:
            connection, address = self.server_socket.accept()
            Server.logger.debug("Got connection")
            self.respond_to_request(connection, address)

    def handle_with_multiprocessing(self):
        while True:
            connection, address = self.server_socket.accept()
            Server.logger.debug("Got connection")
            process = mp.Process(target=self.respond_to_request, args=(connection, address))
            process.daemon = True
            process.start()
            Server.logger.debug("Started process %r", process)

    def respond_to_request(self, connection_socket, address):
        # Retrieve the message sent by the client
        request = connection_socket.recv(1024)

        # Stops issues from empty requests
        if request == '':
            return

        Server.logger.debug('starting connection: {}'.format(str(connection_socket)))

        decoded_request = request.decode()
        http_method, requested_path, request_valid, header_fields = \
            self.parse_header(decoded_request.partition('\r\n\r\n')[0])
        response_status = self.get_response_status(requested_path, request_valid, address[0], header_fields)
        if response_status == 'OK' and http_method != 'HEAD':
            should_send_body = True
        else:
            should_send_body = False

        # Get data sent along with POST request
        data = self.determine_data_if_post_request(http_method, decoded_request, connection_socket)

        Server.logger.debug('file requested: {}'.format(requested_path))
        header_response = self.generate_header(response_status, requested_path)

        # Send HTTP response back to the client
        try:
            connection_socket.send(header_response.encode())
            if should_send_body:
                connection_socket.send(self.determine_response_body(http_method,
                                                                    requested_path,
                                                                    address[0],
                                                                    data))
        except OSError:
            Server.logger.error('send interrupted')

        # Close the connection
        connection_socket.close()
        Server.logger.debug('closed connection: {}'.format(str(connection_socket)))

    def determine_response_body(self, http_method, requested_path, ip_address, data):
        with open(requested_path, 'rb') as file:
            response = file.read()
        return response

    @staticmethod
    def determine_data_if_post_request(http_method, decoded_request, connection_socket):
        if http_method == 'POST':
            data_string = decoded_request.partition('\r\n\r\n')[2]
            if data_string == '':
                # Data was not received, try again. Safari browser requires this.
                data_string = connection_socket.recv(1024).decode()
            data = {}
            for data_element in data_string.split('&'):
                split_data_element = data_element.split('=')
                data[urllib.parse.unquote_plus(split_data_element[0])] = \
                    urllib.parse.unquote_plus(split_data_element[1])
            return data
        else:
            return ''

    @staticmethod
    def parse_header(request_header):
        lines = request_header.split('\r\n')
        first_line = lines[0]
        first_line_split = first_line.split(' ')
        method = first_line_split[0]
        try:
            path = first_line_split[1]
            path = path[1:]
        except IndexError:
            return method, '', False, {}
        if path == '':
            path = 'index.html'

        header_fields = {}
        try:
            for line in lines[1:]:
                line_parts = line.partition(': ')
                header_fields[line_parts[0]] = line_parts[2]
        except IndexError:
            Server.logger.error("failure parsing header fields")
        return method, path, True, header_fields

    def get_response_status(self, path, request_valid, address, header_fields):
        if not request_valid:
            return 'Bad Request'
        if os.path.exists(path):
            if os.path.isdir(path):
                path += 'index.html'
            if os.path.isfile(path):
                requested_dir = os.path.dirname(os.path.abspath(path))
                my_base_dir = os.path.dirname(os.path.abspath('index.html'))
                if requested_dir.find(my_base_dir) == 0:
                    if 'If-Modified-Since' in header_fields and not Time_Handler.is_file_modified_since(
                        Time_Handler.get_formatted_str_of_file_modification_time(path),
                        header_fields['If-Modified-Since']
                    ):
                        return 'Not Modified'
                    else:
                        return 'OK'
                else:
                    return 'Not For You'
        else:
            return 'Not Found'

    def generate_header(self, response_status, path):
        status_line = self.header_statuses[response_status] + '\r\n'
        if response_status in ['OK', 'Not Modified']:
            mime_type = mimetypes.guess_type(os.path.basename(path))[0]
            additional_header_lines = "Content-Type: " + mime_type + '\r\n'
            additional_header_lines += "Last-Modified: " +\
                                       Time_Handler.get_formatted_str_of_file_modification_time(path) + '\r\n'
            # html may be generated dynamically, should not be cached for this server
            if 'html' in mime_type or 'xml' in mime_type:
                additional_header_lines += "Cache-Control: no-store\r\n"
        else:
            additional_header_lines = ''
        return status_line + additional_header_lines + '\r\n'
