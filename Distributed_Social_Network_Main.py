from Distributed_Social_Network_Server import DistributedSocialNetworkServer as DSNServer

if __name__ == '__main__':
    server = DSNServer('', 8080, use_multiprocessing=False)
    server.start()
