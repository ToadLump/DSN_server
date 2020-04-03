import os
import xml.etree.ElementTree as ET
from datetime import datetime
from io import BytesIO

import pycurl
import certifi


class DistributedSocialNetworkResponse:
    def __init__(self, http_method, path, data, port, file_locations):
        self.http_method = http_method
        self.path = path
        self.data = data
        self.file_locations = file_locations
        self.port = port

        basename = os.path.basename(self.path)
        if basename == 'update.html' and http_method == 'POST':
            self.update_status()
            self.response = self.get_unaltered_file()
        elif basename == 'friends.html':
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

            # Access friend server to access status info and profile picture
            friend_status_element = self.get_friend_status_element(ip_address)
            friend_profile_picture_path = self.update_friend_profile_picture(ip_address)

            # Add profile picture
            picture_li_element = ET.SubElement(friend_ul_element, 'li')
            picture_img_element = ET.SubElement(picture_li_element, 'img')
            picture_img_element.attrib = {'src': friend_profile_picture_path, 'alt': "profile picture"}

            # Add name element
            name_li_element = ET.SubElement(friend_ul_element, 'li')
            name_li_element.attrib = {'class': 'name'}
            name_li_element.text = friend.find('name').text

            # Add status text
            status_li_element = ET.SubElement(friend_ul_element, 'li')
            status_li_element.attrib = {'class': 'status_text'}
            status_li_element.text = friend_status_element.find('status_text').text

            # Add timestamp
            timestamp_li_element = ET.SubElement(friend_ul_element, 'li')
            timestamp_li_element.attrib = {'class': 'timestamp'}
            timestamp_li_element.text = friend_status_element.find('timestamp').text

            # Add likes count
            likes_li_element = ET.SubElement(friend_ul_element, 'li')
            likes_li_element.attrib = {'class': 'likes'}
            likes_li_element.text = "Likes: {}".format(len(list(friend_status_element.find('likes'))))
        return all_friends_ul_element

    def get_friend_status_element(self, ip_address):
        friend_statuses_xml_string = self.request_friend_data(ip_address,
                                                              self.file_locations['status_file']).decode('UTF-8')
        friend_latest_statuses_xml = ET.fromstring(friend_statuses_xml_string)
        friend_latest_status = friend_latest_statuses_xml[0]
        return friend_latest_status

    def update_friend_profile_picture(self, ip_address):
        friend_profile_picture_data = self.request_friend_data(ip_address, 'profilePicture.jpg')
        friend_profile_picture_file_path = '{friend_cache_dir}}/{ip_address}_profilePicture.jpg'\
            .format(friend_cache_dir=self.file_locations['cached_friend_data_dir'], ip_address=ip_address)
        with open(friend_profile_picture_file_path, 'wb') as file:
            file.write(friend_profile_picture_data)
        return friend_profile_picture_file_path

    def request_friend_data(self, ip_address, file_path):
        url = "http://{ip_address}:{port}/{file_path}".format(ip_address=ip_address,
                                                              port=self.port,
                                                              file_path=file_path)
        response_buffer = BytesIO()
        curl = pycurl.Curl()
        curl.setopt(pycurl.CAINFO, certifi.where())
        curl.setopt(pycurl.URL, url)
        curl.setopt(curl.WRITEFUNCTION, response_buffer.write)
        curl.perform()
        curl.close()
        friend_data = response_buffer.getvalue()
        response_buffer.close()
        return friend_data

    def get_response(self):
        return self.response
