from requests.models import Response
import logging
import os

def check_response(response: Response) -> Response:
    # Check validity of request
    if not 200 <= response.status_code < 300:
        raise Exception(f"Request failed with status code {response.status_code}: {response.text}")
    return response

def get_logger(dir, filename):
    # Remove existing log if exists 
    filename = os.path.join(dir,filename)
    if filename in os.listdir(dir):
        os.system(f"rm '{filename}'")
    # Configure logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # Configure filehander for >> `filename.txt`
    file_handler = logging.FileHandler(filename)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

if __name__=="__main__":
    pass


