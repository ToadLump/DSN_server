import os
import shutil
import xml.etree.ElementTree as ET

from Distributed_Social_Network_Response import DistributedSocialNetworkResponse as DSN_response
from basic_HTTP_server import Server


# Extends the server written for the tutorials
class DistributedSocialNetworkServer(Server):

    def __init__(self, host_name, port, use_multi_threading=False):
        super().__init__(host_name, port, use_multi_threading)
        self.header_statuses["Not Friend"] = "HTTP/1.1 572 Friendship not reciprocated"
        self.file_locations = {
            'friends_file': 'friends.xml',
            'status_file': 'status.xml',
            'profile_picture': 'profilePicture.jpg',
            'cached_friend_data_dir': 'cached_friend_profile_information'
        }

        # Delete cached info so that it forces a refresh
        self.delete_cached_friend_info()

    def delete_cached_friend_info(self):
        if not os.path.isdir(self.file_locations['cached_friend_data_dir']):
            os.mkdir(self.file_locations['cached_friend_data_dir'])
        for filename in os.listdir(self.file_locations['cached_friend_data_dir']):
            file_path = os.path.join(self.file_locations['cached_friend_data_dir'], filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                self.logger.debug('Failed to delete %s. Reason: %s' % (file_path, e))

    # Overrode method to introduce a new response for if the server refuses the connection because the user is not
    # on the friends list
    def get_response_status(self, path, request_valid, address, header_fields):
        response_status = super().get_response_status(path, request_valid, address, header_fields)
        if self.is_not_friend(address):
            response_status = 'Not Friend'
        return response_status

    def is_not_friend(self, address):
        friends_xml = ET.parse(self.file_locations['friends_file'])
        if address in [friend.find('ip_address').text for friend in friends_xml.findall('friend')]\
                or address == '127.0.0.1':
            return False
        return True

    def determine_response_body(self, http_method, requested_path, ip_address, data):
        return DSN_response(http_method,
                            requested_path,
                            ip_address,
                            data,
                            self.serverPort,
                            self.file_locations).get_response()
