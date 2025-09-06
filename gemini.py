import base64
import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from warnings import warn

from openai import OpenAI
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn

from engine import OCREngine
from progress import BatchSpeedColumn
from utils import collect_images, timecode_key


class Gemini(OCREngine):
    OUTPUT_PROMT = """
IMPORTANT: Respond with a single JSON array. Each element in the array must be a JSON object with two keys. Don't merge any subtitles you extract, give 1 input image is 1 subtitles. You dont need to care about image name.
1. "image_order": Order of input image start from 1.
2. "extracted_text": The extracted subtitle text as a string. If no subtitle is found, this must be "".
Example response for 3 images, where the second image has no subtitles (you cant detect) and the third has two lines:
```json
[
  {
    "image_order": 1,
    "extracted_text": "This is the subtitle from the first image."
  },
  {
    "image_order": 2,
    "extracted_text": ""
  },
  {
    "image_order": 3,
    "extracted_text": "This is a subtitle\\nwith two lines."
  }
]
```
Do not include any explanatory text or markdown formatting outside of the main JSON array.
"""
    DEFAULT_PROMT = """
You are an intelligent OCR agent specializing in subtitle extraction. Your task is to analyze a series of pre-cropped images from video frames and accurately identify and extract ONLY the subtitle text.
hese images may contain other text that is part of the video scene (e.g., signs, logos, on-screen graphics). You must differentiate between subtitle text and scene text. Subtitle text typically has a consistent style and placement within the cropped area.
For each image, provide the extracted subtitle text. If an image contains no subtitle text, or if you cannot confidently identify any text as a subtitle, return an empty string for the "text" field.
"""

    def __init__(
        self, 
        model_name: str = "gemini-2.5-flash", 
        batch_size: int = 50,
        max_workers: int = 3,
        promt: str = None,
        max_retries: int = 5,
        retry_delay: float = 2.0
    ):
        try:            
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError(
                    "Gemini API key not found. Please set GEMINI_API_KEY or GOOGLE_API_KEY "
                    "environment variable or provide api_key parameter."
                )
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
            self.model_name = model_name
            self.batch_size = batch_size
            self.max_workers = max_workers
            self.console = Console()
            self.promt =  (self.DEFAULT_PROMT if not promt else promt) + "\n\n" + self.OUTPUT_PROMT

            self.max_retries = max_retries
            self.retry_delay = retry_delay

        except ImportError:
            raise ImportError("google-genai package is required for GeminiOCREngine"
                              "Try pip install google-genai")
    
    @property
    def engine_name(self) -> str:
        return f"Gemini Batch ({self.model_name}, batch_size={self.batch_size})"
    
    def __call__(self, images_dir: Path) -> Dict[str, str]:
        images = collect_images(images_dir)
        
        if not images:
            warn(f"No images found in {images_dir}")
            return {}
        
        results = {}
        
        batches = [images[i:i + self.batch_size] for i in range(0, len(images), self.batch_size)]
        
        with Progress(
            TextColumn(f"[progress.description]{{task.description}} ({self.engine_name})"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total} batches"),
            TextColumn("{task.percentage:>3.0f}%"),
            BatchSpeedColumn(),
            TimeRemainingColumn(),
            console=self.console,
        ) as progress:
            task = progress.add_task(f"Processing {len(images)} images in batches", total=len(batches))

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_batch = {
                    executor.submit(self._process_batch, batch, batch_idx + 1): (batch_idx, batch)
                    for batch_idx, batch in enumerate(batches)
                }

                for future in as_completed(future_to_batch):
                    batch_idx, batch = future_to_batch[future]
                    
                    try:
                        batch_results = future.result()
                        
                        results.update(batch_results)
                            
                    except Exception as e:
                        self.console.print(f"[red]Batch {batch_idx + 1} failed: {e}[/red]")
                        for img_path in batch:
                            results[img_path.name] = ""

                    progress.update(task, advance=1)
        
        return dict(sorted(results.items(), key=timecode_key))
    
    def _encode_image(self, image_path: Path) -> Optional[str]:
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            self.console.print(f"[red]Failed to encode {image_path.name}: {e}[/red]")
            return None
        
    def _encode_images(self, img_paths: List[Path]) -> List[Tuple[str, str]]:
        encoded_images = []
        
        for path in img_paths:
            encoded = self._encode_image(path)
            if encoded is not None:
                encoded_images.append((encoded, path.name))
    
        return encoded_images
    
    def _process_batch(self, img_paths: List[Path], batch_num: int) -> Dict[str, str]:
        encoded_images = []
        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    jitter = random.uniform(0.5, 1.5)
                    total_delay = self.retry_delay * jitter
                    
                    self.console.print(f"[yellow]Batch {batch_num} - Retry {attempt}/{self.max_retries} after {total_delay:.1f}s delay[/yellow]")
                    time.sleep(total_delay)
                
                if not encoded_images:
                    encoded_images: Dict[str, str] = self._encode_images(img_paths)
                            
                metadata = f"Number of input images: {len(encoded_images)}\n"
                full_prompt = metadata + self.promt

                content = [
                    {
                        "type": "text",
                        "text": full_prompt
                    }
                ]

                image_names: List[str] = []
                for n, (encoded_image, image_name) in enumerate(encoded_images, 1):
                    content.append({
                        "type": "text",
                        "text": f"Image {n}:"
                    })
                    image_format = "jpeg"
                    if image_name.lower().endswith(('.png',)):
                        image_format = "png"
                    elif image_name.lower().endswith(('.webp',)):
                        image_format = "webp"
                    
                    image_names.append(image_name)
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/{image_format};base64,{encoded_image}"
                        }
                    })
                                
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": content
                        }
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.3
                )
                    
                response_content = response.choices[0].message.content
                    
                if "high load" in response_content.lower():
                    raise Exception("Gemini API reported high load")
                
                if "quota exceeded" in response_content.lower():
                    raise Exception("API quota exceeded")
                
                parsed_results = self._parse_json_response(response_content)
                results = {}
                if len(parsed_results) != len(img_paths):
                    raise Exception("Model return missmatch array, result maybe wrong.")
                if isinstance(parsed_results, list):
                    for item in parsed_results:
                        image_order = item.get('image_order')
                        extracted_text = item.get('extracted_text', '')

                        if image_order is not None and 1 <= image_order <= len(img_paths):
                            image_name = image_names[image_order - 1]
                            results[image_name] = extracted_text
                        else:
                            warn(f"Invalid image_order: {image_order}")
                
                    for image_name in image_names:
                        if image_name not in results:
                            warn(f"No result found for image: {image_name}")

                if attempt > 0:
                    self.console.print(f"[green]Batch {batch_num} - Retry {attempt} succeeded![/green]")
                return results
                
            except Exception as e:
                if attempt == self.max_retries:
                    self.console.print(f"[red]Batch {batch_num} - Final attempt failed: {e}[/red]")
                    return {path: "" for path in img_paths}
                else:
                    self.console.print(f"[yellow]Batch {batch_num} - Attempt {attempt + 1} failed: {e}[/yellow]")
                    continue

    def _parse_json_response(self, raw_response: str) -> List[Dict]:
        # direct parsing
        try:
            result = json.loads(raw_response)
            if isinstance(result, list):
                return result
            elif isinstance(result, dict) and 'results' in result:
                return result['results']
            else:
                raise json.JSONDecodeError(f"Unexpected JSON structure: {type(result)}", raw_response, 0)
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON response: {raw_response[:500]}...")
            return None