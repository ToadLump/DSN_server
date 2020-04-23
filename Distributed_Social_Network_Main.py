from Distributed_Social_Network_Server import DistributedSocialNetworkServer as DSNServer

if __name__ == '__main__':
    server = DSNServer(host_name='', port=8080, use_multi_threading=True, resources_dir='resources/')
    server.start()
