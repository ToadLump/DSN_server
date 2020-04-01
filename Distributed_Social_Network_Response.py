import os
import xml.etree.ElementTree as ET
from datetime import datetime


class DistributedSocialNetworkResponse:
    def __init__(self, http_method, path, data):
        self.http_method = http_method
        self.path = path
        self.data = data

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
        return self.get_unaltered_file()

    def get_response(self):
        return self.response
