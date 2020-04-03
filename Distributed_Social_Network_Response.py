import os
import xml.etree.ElementTree as ET
from datetime import datetime


class DistributedSocialNetworkResponse:
    def __init__(self, http_method, path, data, port=8080):
        self.http_method = http_method
        self.path = path
        self.data = data
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

            # Read status.xml and insert new status
            status_xml = ET.parse('status.xml')
            root = status_xml.getroot()
            root.insert(0, status_element)
            status_xml.write('status.xml')

    def generate_friends_html(self):
        friends_list_node = self.generate_friends_list_node()

        html_dom = ET.parse(self.path)
        root = html_dom.getroot()
        root.find(".//div[@id='friends_info']").append(friends_list_node)
        html_string = ET.tostring(root, encoding='UTF-8', method='html')
        return html_string

    def generate_friends_list_node(self):
        all_friends_ul_element = ET.Element('ul')
        friends_xml = ET.parse('friends.xml')
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
            name_li_element.text = friend.find('name').text

            # Add status text
            status_li_element = ET.SubElement(friend_ul_element, 'li')
            status_li_element.text = friend_status_element.find('status_text').text

            # Add timestamp
            timestamp_li_element = ET.SubElement(friend_ul_element, 'li')
            timestamp_li_element.text = friend_status_element.find('timestamp').text

            # Add likes count
            likes_li_element = ET.SubElement(friend_ul_element, 'li')
            likes_li_element.text = "Likes: {}".format(len(list(friend_status_element.find('likes'))))
        return all_friends_ul_element

    def get_friend_status_element(self, ip_address):
        # FIXME: this is just a placeholder
        return ET.fromstring("""
            <status>
                <timestamp>2020-04-02 13:23:55.055120</timestamp>
                <status_text>fasdfse</status_text>
                <likes />
            </status>
        """)

    def update_friend_profile_picture(self, ip_address):
        return "cached_friend_profile_information/profilePicture.jpg"

    def get_response(self):
        return self.response
