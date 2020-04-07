import os
import xml.etree.ElementTree as ET
from datetime import datetime
from io import BytesIO
from urllib.parse import urlencode
import logging

import socket
import pycurl
import certifi

import Time_Handler


class ServerUnavailableException(Exception):
    def __str__(self):
        return "Server Not Available Right Now"


class NotFriendException(Exception):
    def __str__(self):
        return "Friendship Not Reciprocated"


class DistributedSocialNetworkResponse:
    def __init__(self, http_method, path, ip_address, data, port, file_locations):
        self.http_method = http_method
        self.path = path
        self.ip_address = ip_address
        self.data = data
        self.file_locations = file_locations
        self.port = port

        self.logger = logging.getLogger('response')
        logging.basicConfig(level=logging.INFO)

        basename = os.path.basename(self.path)
        if basename == 'update.html' and http_method == 'POST':
            self.update_status()
            self.response = self.get_unaltered_file()
        elif basename == 'friends.html':
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
            status_xml = ET.parse(self.file_locations['status_file'])
            root = status_xml.getroot()
            root.insert(0, status_element)
            status_xml.write(self.file_locations['status_file'])

    def generate_friends_html(self):
        friends_list_node = self.generate_friends_list_node()

        html_dom = ET.parse(self.path)
        root = html_dom.getroot()
        root.find(".//div[@id='friends_info']").append(friends_list_node)
        html_string = ET.tostring(root, encoding='UTF-8', method='html')
        return html_string

    def generate_friends_list_node(self):
        all_friends_ul_element = ET.Element('ul')
        friends_xml = ET.parse(self.file_locations['friends_file'])
        for friend in friends_xml.findall('friend'):
            friend_ul_element = ET.SubElement(all_friends_ul_element, 'ul')

            ip_address = friend.find('ip_address').text
            friend_server_available = True

            # Access friend server to access status info and profile picture
            try:
                friend_status_element = self.get_friend_status_element(ip_address)
                friend_profile_picture_path = self.update_friend_profile_picture(ip_address)
            except (NotFriendException, ServerUnavailableException) as e:
                friend_status_element = self.get_exception_status_element(str(e))
                friend_profile_picture_path = 'profile-blank.jpg'
                friend_server_available = False

            # Add profile picture
            picture_li_element = ET.SubElement(friend_ul_element, 'li')
            picture_img_element = ET.SubElement(picture_li_element, 'img')
            picture_img_element.attrib = {'src': friend_profile_picture_path, 'alt': "profile picture"}

            # Add name
            self.add_friend_data_li(friend, friend_ul_element, 'name')

            # Add status text
            self.add_friend_data_li(friend_status_element, friend_ul_element, 'status_text')

            if friend_server_available:
                # Add timestamp
                timestamp = self.add_friend_data_li(friend_status_element, friend_ul_element, 'timestamp')

                # Add likes count
                likes_li_element = ET.SubElement(friend_ul_element, 'li')
                likes_li_element.attrib = {'class': 'likes'}
                likes_li_element.text = "Likes: {}".format(len(list(friend_status_element.find('likes'))))

                self.add_like_button(friend_status_element, friend_ul_element, ip_address, timestamp)

        return all_friends_ul_element

    @staticmethod
    def add_friend_data_li(element_to_pull_info_from, ul_to_add_to, xpath_to_relevant_element):
        status_li_element = ET.SubElement(ul_to_add_to, 'li')
        status_li_element.attrib = {'class': xpath_to_relevant_element}
        node_text = element_to_pull_info_from.find(xpath_to_relevant_element).text
        status_li_element.text = node_text
        return node_text

    def add_like_button(self, friend_status_element, friend_ul_element, ip_address, timestamp):
        like_button_li_element = ET.SubElement(friend_ul_element, 'li')
        like_button_form_element = ET.SubElement(like_button_li_element, 'form')
        like_button_form_element.attrib = {'action': 'friends.html', 'method': 'POST'}
        like_button_hidden_ip_address_element = ET.SubElement(like_button_form_element, 'input')
        like_button_hidden_ip_address_element.attrib = {'type': 'hidden', 'name': 'ip_address', 'value': ip_address}
        like_button_hidden_timestamp_element = ET.SubElement(like_button_form_element, 'input')
        like_button_hidden_timestamp_element.attrib = {'type': 'hidden', 'name': 'timestamp', 'value': timestamp}
        like_button_button_element = ET.SubElement(like_button_form_element, 'input')
        should_disable = self.disable_if_already_liked(friend_status_element.find('likes'), ip_address)
        like_button_attributes = {'type': 'submit', 'name': 'like',
                                  'value': 'like'}
        # Disable like button if this user has already liked the status
        like_button_attributes.update(should_disable)
        like_button_button_element.attrib = like_button_attributes

    def get_friend_status_element(self, ip_address):
        friend_statuses_xml_string = self.request_friend_data(ip_address,
                                                              self.file_locations['status_file'])[0].decode('UTF-8')
        if friend_statuses_xml_string == '':
            return ''
        friend_latest_statuses_xml = ET.fromstring(friend_statuses_xml_string)
        friend_latest_status = friend_latest_statuses_xml[0]
        return friend_latest_status

    def update_friend_profile_picture(self, ip_address):
        friend_profile_picture_file_path = '{friend_cache_dir}/{ip_address}_profile_picture.jpg' \
            .format(friend_cache_dir=self.file_locations['cached_friend_data_dir'], ip_address=ip_address)

        if os.path.isfile(friend_profile_picture_file_path):
            modified_time = Time_Handler.get_formatted_str_of_file_modification_time(friend_profile_picture_file_path)
        else:
            modified_time = None

        friend_profile_picture_data, is_modified = self.request_friend_data(ip_address,
                                                                            self.file_locations['profile_picture'],
                                                                            modified_time=modified_time)
        if is_modified:
            with open(friend_profile_picture_file_path, 'wb') as file:
                file.write(friend_profile_picture_data)

        return friend_profile_picture_file_path

    def request_friend_data(self, ip_address, file_path, modified_time=None):
        url = "http://{ip_address}:{port}/{file_path}".format(ip_address=ip_address,
                                                              port=self.port,
                                                              file_path=file_path)
        response_buffer = BytesIO()
        header_buffer = BytesIO()
        curl = pycurl.Curl()
        curl.setopt(pycurl.CAINFO, certifi.where())
        curl.setopt(pycurl.URL, url)
        curl.setopt(pycurl.TIMEOUT, 1)
        if modified_time is not None:
            curl.setopt(curl.HTTPHEADER, ["If-Modified-Since: {}".format(modified_time)])
        curl.setopt(curl.WRITEFUNCTION, response_buffer.write)
        curl.setopt(curl.HEADERFUNCTION, header_buffer.write)
        try:
            curl.perform()
        except pycurl.error:
            raise ServerUnavailableException
        curl.close()
        header_data = header_buffer.getvalue()
        friend_data = response_buffer.getvalue()
        response_buffer.close()
        header_buffer.close()
        is_modified = self.check_header(header_data)
        return friend_data, is_modified

    @staticmethod
    def check_header(header):
        header_str = header.decode('UTF-8')
        if "Friendship not reciprocated" in header_str:
            raise NotFriendException
        elif "Not Modified" in header_str:
            return False
        else:
            return True

    @staticmethod
    def get_exception_status_element(status_text):
        status_node = ET.fromstring("""
        <status>
        <timestamp></timestamp>
        <status_text></status_text>
        <likes />
        </status>
        """)
        status_node.find("status_text").text = status_text
        return status_node

    def disable_if_already_liked(self, likes_element, friend_ip_address):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((friend_ip_address, self.port))
        # Get the ip address that the friend server sees this computer as
        my_ip_address = s.getsockname()[0]
        s.close()

        if self.is_ip_address_in_element(my_ip_address, likes_element):
            return {'disabled': 'disabled'}
        else:
            return {}

    @staticmethod
    def is_ip_address_in_element(ip_address, element):
        return ip_address in [ip_address_element.text for ip_address_element in element.findall('.//ip_address')]

    def inform_friend_server_about_like(self):
        # sending the data to the ip address listed, and then removing that address from the data sent
        # this is an implicit way of telling the servers which one is sending and which is receiving the like
        url = "http://{ip_address}:{port}/{file_path}".format(ip_address=self.data.pop('ip_address'),
                                                              port=self.port,
                                                              file_path='friends.html')
        curl = pycurl.Curl()
        curl.setopt(pycurl.CAINFO, certifi.where())
        curl.setopt(pycurl.URL, url)
        curl.setopt(pycurl.TIMEOUT, 1)

        post_data = self.data
        # Form data must be provided already urlencoded.
        post_fields = urlencode(post_data)
        # Sets request method to POST,
        # Content-Type header to application/x-www-form-urlencoded
        # and data to send in request body.
        curl.setopt(curl.POSTFIELDS, post_fields)
        try:
            curl.perform()
        except pycurl.error:
            self.logger.info('the server the user requested to like is unavailable')
        curl.close()

    def add_like_to_status(self):
        # Read friends file to determine which friend liked the status
        friends_xml = ET.parse(self.file_locations['friends_file'])
        liking_friend_element = friends_xml.find(".//friend[ip_address='{}']".format(self.ip_address))

        # Read status file and insert like information
        status_xml = ET.parse(self.file_locations['status_file'])
        # Uses timestamp to determine if the correct status is being liked
        liked_status = status_xml.find(".//status[timestamp='{}']".format(self.data['timestamp']))
        # Only write like into status file if it is the first like from that friend - avoids resubmitted form
        # from adding additional like before button is disabled
        if not self.is_ip_address_in_element(self.ip_address, liked_status.find('likes')):
            liked_status.find('likes').insert(0, liking_friend_element)
            status_xml.write(self.file_locations['status_file'])

    def get_response(self):
        return self.response
