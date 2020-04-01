from basic_HTTP_server import Server
from Distributed_Social_Network_Response import DistributedSocialNetworkResponse as DSN_response

if __name__ == '__main__':
    server = Server('', 8080, DSN_response, use_multiprocessing=False)
    server.start()
