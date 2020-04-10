from urllib.parse import urlencode
from socket import *
import io


def generate_http_request(http_method, requested_file, header_fields={}, data=None):
    if requested_file[0] != '/':
        requested_file = '/' + requested_file

    http_request = "{method} {requested_file} HTTP/1.1\r\n".format(method=http_method,
                                                                   requested_file=requested_file)
    for field in header_fields:
        http_request += "{field}: {field_data}\r\n".format(field=field, field_data=header_fields[field])
    http_request += "\r\n"

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
