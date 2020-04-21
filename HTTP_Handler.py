from urllib.parse import urlencode
from socket import *
import io


def generate_http_request(http_method, requested_file, header_fields=None, data=None):
    if header_fields is None:
        header_fields = {}
    if requested_file[0] != '/':
        requested_file = '/' + requested_file

    http_request = f"{http_method} {requested_file} HTTP/1.1\r\n"
    if header_fields is not None:
        for field in header_fields:
            http_request += f"{field}: {header_fields[field]}\r\n"

    http_request += "\r\n"

    # prepare post data
    if data is not None:
        http_request += urlencode(data)

    return http_request


def send_http_request(http_request, ip_address, port):
    send_socket = socket(AF_INET, SOCK_STREAM)
    address_info = getaddrinfo(ip_address, port, AF_UNSPEC, SOCK_STREAM)
    send_socket.settimeout(1)
    try:
        send_socket.connect(address_info[0][4])
        send_socket.sendall(http_request.encode())
    except OSError as e:
        send_socket.close()
        raise e
    return send_socket


def retrieve_http_response(receive_socket):
    bytes_buffer = io.BytesIO()
    max_bytes_per_receive = 1024
    while True:
        received_data = receive_socket.recv(max_bytes_per_receive)
        bytes_buffer.write(received_data)
        # Assumes the socket will be closed by the other side
        if len(received_data) == 0:
            break
    receive_socket.close()
    response = bytes_buffer.getvalue()
    bytes_buffer.close()
    header, _, data = response.partition(b'\r\n\r\n')
    return header, data


def parse_response_header(header):
    header_str = header.decode('UTF-8')

    first_line, _, header_fields_str = header_str.partition('\r\n')
    http_version, _, code_info = first_line.partition(' ')
    status_code, _, status_text = code_info.partition(' ')

    header_fields = _extract_header_fields(header_fields_str)

    return {'code': status_code, 'text': status_text, 'http_version': http_version}, header_fields


def _extract_header_fields(header_fields_str):
    header_fields = {}
    for header_field_str in header_fields_str.split('\r\n'):
        label, _, value = header_field_str.partition(': ')
        header_fields[label] = value
    return header_fields
