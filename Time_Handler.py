import os
import datetime


format_string = "%a, %d %b %Y %H:%M:%S GMT"


# Conforms to the if-modified-since http standard
def get_formatted_str_of_file_modification_time(file_path):
    file_modified_timestamp = os.path.getmtime(file_path)
    file_modified_datetime = datetime.datetime.utcfromtimestamp(file_modified_timestamp)
    formatted_modified_datetime = file_modified_datetime.strftime(format_string)
    return formatted_modified_datetime


def is_file_modified_since(check_string, test_string):
    check_datetime = datetime.datetime.strptime(check_string, format_string)
    test_datetime = datetime.datetime.strptime(test_string, format_string)
    return check_datetime > test_datetime
