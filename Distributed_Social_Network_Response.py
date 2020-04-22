import os
import xml.etree.ElementTree as ET
from datetime import datetime
import logging
import socket
import threading

import Time_Handler
import HTTP_Handler


class ServerUnavailableException(Exception):
    def __str__(self):
        return "Server Not Available Right Now"


class NotFriendException(Exception):
    def __str__(self):
        return "Friendship Not Reciprocated"


class FriendHasNoStatusException(Exception):
    def __str__(self):
        return "Friend Has Not Defined a Status"


class DistributedSocialNetworkResponse:
    logger = logging.getLogger('response')
    logging.basicConfig(level=logging.INFO)

    def __init__(self, http_method, path, ip_address, data, port, file_locations, resources_dir):
        self.http_method = http_method
        self.path = path
        self.ip_address = ip_address
        self.data = data
        self.file_locations = file_locations
        self.resources_dir = resources_dir
        self.port = port

        # If requested file is a special case: handle it, otherwise return unaltered file
        basename = os.path.basename(self.path)
        if basename == self.file_locations['update_html'] and http_method == 'POST':
            self.update_status()
            self.response = self.get_unaltered_file()
        elif basename == self.file_locations['friends_html']:
            if http_method == 'POST':
                if 'ip_address' in self.data:
                    self.inform_friend_server_about_like()
                    self.response = self.generate_friends_html()
                else:
                    self.add_like_to_status()
                    # this response will not get used
                    self.response = b''
            else:
                self.response = self.generate_friends_html()
        else:
            self.response = self.get_unaltered_file()

    def get_unaltered_file(self):
        with open(self.path, 'rb') as file:
            response = file.read()
        return response

    def update_status(self):
        # Ensure no empty statuses are added
        if self.data['status'] != '':
            # Create New Status element
            status_element = ET.Element('status')
            timestamp_element = ET.SubElement(status_element, 'timestamp')
            timestamp_element.text = str(datetime.now())
            status_text_element = ET.SubElement(status_element, 'status_text')
            status_text_element.text = self.data['status']
            ET.SubElement(status_element, 'likes')

            # Read status file and insert new status
            status_xml_path = f"{self.resources_dir}{self.file_locations['status_xml']}"
            status_xml = ET.parse(status_xml_path)
            root = status_xml.getroot()
            root.insert(0, status_element)
            status_xml.write(status_xml_path)

    def generate_friends_html(self):
        # generate a ul list of information from each friend
        friends_list_node = self.generate_friends_list_node()
        html_dom = ET.parse(self.path)
        root = html_dom.getroot()

        # Put friends list element into the html document
        root.find(".//div[@id='friends_info']").append(friends_list_node)
        html_string = ET.tostring(root, encoding='UTF-8', method='html')
        return html_string

    def generate_friends_list_node(self):
        # Element that will contain all information from all friends
        all_friends_ul_element = ET.Element('ul')

        # Determine all friends and create a new ul with information from each
        friends_xml = ET.parse(f"{self.resources_dir}{self.file_locations['friends_xml']}")

        # Decided to use threading because otherwise the user might have to wait a long time to load the friends page
        # if multiple friends were offline and the connections were timing out
        threads = []
        for friend in friends_xml.findall('friend'):
            friend_ul_element = ET.SubElement(all_friends_ul_element, 'ul')
            populate_friend_data_thread = threading.Thread(target=self.populate_friend_ul_element,
                                                           args=(friend, friend_ul_element))
            threads.append(populate_friend_data_thread)
            populate_friend_data_thread.start()

        for thread in threads:
            thread.join()

        return all_friends_ul_element

    def populate_friend_ul_element(self, friend, friend_ul_element):
        ip_address = friend.find('ip_address').text

        # Access friend server to get status info and profile picture
        friend_data_available, friend_online, friend_profile_picture_path, friend_status_element = \
            self.access_friend_server(ip_address)

        # Add profile picture
        picture_li_element = ET.SubElement(friend_ul_element, 'li')
        picture_img_element = ET.SubElement(picture_li_element, 'img')
        picture_img_element.attrib = {'src': friend_profile_picture_path, 'alt': "profile picture"}

        # Add name
        self.add_friend_data_li(friend, friend_ul_element, 'name')

        # Add status text
        self.add_friend_data_li(friend_status_element, friend_ul_element, 'status_text')

        self.add_friend_server_status_li(friend_ul_element, friend_online, friend_data_available)

        if friend_data_available:
            # Add timestamp
            timestamp = self.add_friend_data_li(friend_status_element, friend_ul_element, 'timestamp')

            # Add likes count
            likes_li_element = ET.SubElement(friend_ul_element, 'li')
            likes_li_element.attrib = {'class': 'likes'}
            likes_li_element.text = f"Likes: {len(list(friend_status_element.find('likes')))}"

            # Add like button
            self.add_like_button(friend_status_element, friend_ul_element, ip_address, timestamp, friend_online)

    def access_friend_server(self, ip_address):
        try:
            friend_status_element, friend_online = self.get_friend_status_element(ip_address)
            friend_profile_picture_path = self.update_friend_profile_picture(ip_address, friend_online)
            friend_data_available = True
        except (NotFriendException, ServerUnavailableException, FriendHasNoStatusException) as e:
            DistributedSocialNetworkResponse.logger.debug(e)
            friend_status_element = self.get_exception_status_element(str(e))
            friend_profile_picture_path = 'profile-blank.jpg'
            friend_data_available = False
            if isinstance(e, ServerUnavailableException):
                friend_online = False
            else:
                friend_online = True
        return friend_data_available, friend_online, friend_profile_picture_path, friend_status_element

    @staticmethod
    def add_friend_server_status_li(friend_ul_element, friend_online, friend_data_available):
        online_status = {
            False: 'offline',
            True: 'online'
        }
        data_available = {
            False: 'no data available',
            True: 'data available'
        }
        li_element = ET.SubElement(friend_ul_element, 'li')
        li_element.attrib = {'class': online_status[friend_online]}
        li_element.text = f"friend {online_status[friend_online]} - {data_available[friend_data_available]}"

    @staticmethod
    def add_friend_data_li(element_to_pull_info_from, ul_to_add_to, xpath_to_relevant_element):
        status_li_element = ET.SubElement(ul_to_add_to, 'li')
        status_li_element.attrib = {'class': xpath_to_relevant_element}
        node_text = element_to_pull_info_from.find(xpath_to_relevant_element).text
        status_li_element.text = node_text
        return node_text

    def add_like_button(self, friend_status_element, friend_ul_element, ip_address, timestamp, friend_online):
        like_button_li_element = ET.SubElement(friend_ul_element, 'li')
        like_button_form_element = ET.SubElement(like_button_li_element, 'form')
        like_button_form_element.attrib = {'action': self.file_locations['friends_html'], 'method': 'POST'}

        # These hidden elements are used to ensure the correct friend is notified about the like, and that the friend
        # can identify which status was liked
        like_button_hidden_ip_address_element = ET.SubElement(like_button_form_element, 'input')
        like_button_hidden_ip_address_element.attrib = {'type': 'hidden', 'name': 'ip_address', 'value': ip_address}
        like_button_hidden_timestamp_element = ET.SubElement(like_button_form_element, 'input')
        like_button_hidden_timestamp_element.attrib = {'type': 'hidden', 'name': 'timestamp', 'value': timestamp}

        like_button_button_element = ET.SubElement(like_button_form_element, 'input')
        should_disable = self.disable_button_if_already_liked(friend_status_element.find('likes'),
                                                              ip_address,
                                                              friend_online)
        like_button_attributes = {'type': 'submit', 'name': 'like',
                                  'value': 'like'}
        # Disable like button if this user has already liked the status or friend server is offline
        like_button_attributes.update(should_disable)
        like_button_button_element.attrib = like_button_attributes

    def get_friend_status_element(self, ip_address):
        cached_friend_status_path, cached_friend_status_path_in_resources = self.get_paths(ip_address, "status.xml")
        cache_modified_time = self.get_modification_time(cached_friend_status_path_in_resources)
        friend_online, friend_statuses_xml_string_encoded, is_modified = \
            self.request_friend_statuses(cache_modified_time, ip_address)

        if is_modified:
            # Cache the new information
            friend_statuses_xml_string = friend_statuses_xml_string_encoded.decode()
            friend_latest_statuses_xml = ET.fromstring(friend_statuses_xml_string)
            try:
                friend_latest_status = friend_latest_statuses_xml[0]
                ET.ElementTree(friend_latest_status).write(cached_friend_status_path_in_resources)
            except IndexError:
                raise FriendHasNoStatusException
        else:
            # Use the cached information
            friend_latest_status = ET.parse(cached_friend_status_path_in_resources).getroot()
        return friend_latest_status, friend_online

    def request_friend_statuses(self, cache_modified_time, ip_address):
        try:
            friend_statuses_xml_string_encoded, is_modified = \
                self.request_friend_data(ip_address,
                                         self.file_locations['status_xml'],
                                         modified_time=cache_modified_time)
            friend_online = True
        except ServerUnavailableException as e:
            # If no cached version, pass error along
            if cache_modified_time is None:
                raise e
            # Otherwise, use cached version
            else:
                friend_statuses_xml_string_encoded = None
                friend_online = False
                is_modified = False
        return friend_online, friend_statuses_xml_string_encoded, is_modified

    def update_friend_profile_picture(self, ip_address, friend_online):
        friend_picture_file_path, friend_picture_file_path_in_resources = self.get_paths(ip_address, "picture.jpg")
        modified_time = self.get_modification_time(friend_picture_file_path_in_resources)

        if friend_online:
            friend_profile_picture_data, is_modified = self.request_friend_data(ip_address,
                                                                                self.file_locations['profile_picture'],
                                                                                modified_time=modified_time)
        else:
            friend_profile_picture_data = None
            is_modified = False

        if is_modified:
            with open(friend_picture_file_path_in_resources, 'wb') as file:
                file.write(friend_profile_picture_data)

        return friend_picture_file_path

    def get_paths(self, ip_address, name):
        path = f"{self.file_locations['cached_friend_data_dir']}/{ip_address}_{name}"
        path_in_resources = f"{self.resources_dir}{path}"
        return path, path_in_resources

    @staticmethod
    def get_modification_time(path):
        if os.path.isfile(path):
            modified_time = Time_Handler.get_formatted_str_of_file_modification_time(path)
        else:
            modified_time = None
        return modified_time

    def request_friend_data(self, ip_address, file_path, modified_time=None):
        header_fields = {}
        if modified_time is not None:
            header_fields["If-Modified-Since"] = modified_time
        http_request = HTTP_Handler.generate_http_request('GET', file_path, header_fields)
        try:
            active_socket = HTTP_Handler.send_http_request(http_request, ip_address, self.port)
            header, friend_data = HTTP_Handler.retrieve_http_response(active_socket)
        except (socket.timeout, ConnectionRefusedError):
            raise ServerUnavailableException
        is_modified = self.check_header_for_modification_and_problems(header)
        return friend_data, is_modified

    @staticmethod
    def check_header_for_modification_and_problems(header):
        status, header_fields = HTTP_Handler.parse_response_header(header)
        if "572" == status['code']:
            raise NotFriendException
        elif "304" == status['code']:
            # File has not been modified
            return False
        else:
            # File has been modified
            return True

    @staticmethod
    def get_exception_status_element(status_text):
        # This provides a blank status used if an exception occurs while attempting to get friend data
        status_node = ET.fromstring("""
        <status>
        <timestamp></timestamp>
        <status_text></status_text>
        <likes />
        </status>
        """)
        status_node.find("status_text").text = status_text
        return status_node

    def disable_button_if_already_liked(self, likes_element, friend_ip_address, friend_online):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((friend_ip_address, self.port))

        # Get the ip address that the friend server sees this computer as
        my_ip_address = s.getsockname()[0]
        s.close()

        if self.is_ip_address_in_element(my_ip_address, likes_element) or not friend_online:
            return {'disabled': 'disabled'}
        else:
            return {}

    @staticmethod
    def is_ip_address_in_element(ip_address, element):
        return ip_address in [ip_address_element.text for ip_address_element in element.findall('.//ip_address')]

    def inform_friend_server_about_like(self):
        file_path = self.file_locations['friends_html']

        # sending the data to the ip address listed, and then removing that address from the data sent
        # this is an implicit way of telling the servers which one is sending and which is receiving the like
        friend_ip_address = self.data.pop('ip_address')
        http_request = HTTP_Handler.generate_http_request('POST', file_path, data=self.data)
        try:
            active_socket = HTTP_Handler.send_http_request(http_request, friend_ip_address, self.port)
            HTTP_Handler.retrieve_http_response(active_socket)
        except socket.timeout:
            DistributedSocialNetworkResponse.logger.info('the server the user requested to like is unavailable')

    def add_like_to_status(self):
        # Read friends file to determine which friend liked the status
        friends_xml_path_in_resources = f"{self.resources_dir}{self.file_locations['friends_xml']}"
        friends_xml = ET.parse(friends_xml_path_in_resources)
        liking_friend_element = friends_xml.find(f".//friend[ip_address='{self.ip_address}']")

        # Read status file and insert like information
        status_xml_path_in_resources = f"{self.resources_dir}{self.file_locations['status_xml']}"
        status_xml = ET.parse(status_xml_path_in_resources)

        # Uses timestamp to determine if the correct status is being liked
        liked_status = status_xml.find(f".//status[timestamp='{self.data['timestamp']}']")

        # Only write like into status file if it is the first like from that friend - avoids resubmitted form
        # from adding additional likes before button is disabled
        if not self.is_ip_address_in_element(self.ip_address, liked_status.find('likes')):
            liked_status.find('likes').insert(0, liking_friend_element)
            status_xml.write(status_xml_path_in_resources)

    def get_response(self):
        return self.response
