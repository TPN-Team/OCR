import random

from typing import Any

from httpx import Client

from lens import (AppliedFilter, LensOverlayFilterType, LensOverlayRoutingInfo, LensOverlayServerRequest,
                  LensOverlayServerResponse, Platform, Surface,)
from utils import get_image_raw_bytes_and_dims


class GoogleLens:
    LENS_ENDPOINT: str = "https://lensfrontend-pa.googleapis.com/v1/crupload"

    HEADERS: dict[str, str]  = {
        'Host': 'lensfrontend-pa.googleapis.com',
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-protobuf',
        'X-Goog-Api-Key': 'AIzaSyDr2UxVnv_U85AbhhY8XSHSIavUW0DC-sY',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Dest': 'empty',
        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        'Accept-Encoding': 'gzip, deflate, br, zstd',
    }

    def __init__(self):
        self.client: Client = Client()

    def __del__(self):
        self.client.close()
    
    def __call__(self, img_path: str):
        
        request = LensOverlayServerRequest()

        request.objects_request.request_context.request_id.uuid = random.randint(0, 2**64 - 1)
        request.objects_request.request_context.request_id.sequence_id = 0
        request.objects_request.request_context.request_id.image_sequence_id = 0
        request.objects_request.request_context.request_id.analytics_id = random.randbytes(n=16)
        request.objects_request.request_context.request_id.routing_info = LensOverlayRoutingInfo()

        request.objects_request.request_context.client_context.platform = Platform.WEB
        request.objects_request.request_context.client_context.surface = Surface.CHROMIUM

        # request.objects_request.request_context.client_context.locale_context.language = 'vi'
        # request.objects_request.request_context.client_context.locale_context.region = 'Asia/Ho_Chi_Minh'
        request.objects_request.request_context.client_context.locale_context.time_zone = '' # not set by chromium

        request.objects_request.request_context.client_context.app_id = '' # not set by chromium

        filter = AppliedFilter()
        filter.filter_type = LensOverlayFilterType.AUTO_FILTER
        request.objects_request.request_context.client_context.client_filters.filter.append(filter)

        image_data = get_image_raw_bytes_and_dims(img_path)
        if image_data is not None:
            raw_bytes, width, height = image_data

            request.objects_request.image_data.payload.image_bytes = raw_bytes
            request.objects_request.image_data.image_metadata.width = width
            request.objects_request.image_data.image_metadata.height = height
        else:
            print(f"Error: Could not process image file '{img_path}'. Cannot populate image data in request.")

        payload = request.SerializeToString()

        res = None
        max_retries = 3
        last_exception = None
        for attempt in range(max_retries):
            try:
                res = self.client.post(
                    self.LENS_ENDPOINT,
                    content=payload,
                    headers=self.HEADERS,
                    timeout=40,
                )

                if res.status_code == 200:
                    break
                
                raise Exception(f"Request failed with status code: {res.status_code}")

            except Exception as e:
                last_exception = e
                print(f"Attempt {attempt + 1} failed. Retrying...")
                if attempt == max_retries - 1:
                    raise Exception(
                        f"Failed to upload image after {max_retries} attempts. Last error: {str(last_exception)}"
                    )
                continue

        if res != None:
            response_proto = LensOverlayServerResponse().FromString(res.content)
            response_dict: dict[str, Any] = response_proto.to_dict()

            result: str = ''
            paragraphs = response_dict.get('objectsResponse', {}).get('text', {}).get('textLayout', {}).get('paragraphs', []) 
            if not paragraphs:
                print(f"Empty OCR please check subtitle {img_path}")
            separator = '\\n '
            for index, paragraph in enumerate(paragraphs):
                if index > 0:
                    result += separator
                for line in paragraph.get('lines', []):
                    for word in line.get('words', []):
                        plain_text = word.get('plainText', '')
                        separator_text = word.get('textSeparator', '')
                        result += plain_text + separator_text        
            
            return result