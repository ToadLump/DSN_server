
class DistributedSocialNetworkResponse:
    def __init__(self, http_method, path, data):
        self.http_method = http_method
        self.path = path
        self.data = data
        self.response = self.generate_response()

    def generate_response(self):
        with open(self.path, 'rb') as file:
            response = file.read()
        return response

    def get_response(self):
        return self.response
