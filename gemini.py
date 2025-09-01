import os
from pathlib import Path
from typing import Dict, List
import json

from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn

from warnings import warn

from progress import BatchSpeedColumn

from utils import collect_images, timecode_key


class Gemini:
    OUTPUT_PROMT = """
IMPORTANT: Respond with a single JSON array. Each element in the array must be a JSON object with two keys.
1. "image_order": The zero-based index of the image in the input sequence.
2. "extracted_text": The extracted subtitle text as a string. If no subtitle is found, this must be "".
Example response for 3 images, where the second image has no subtitles (you cant detect) and the third has two lines:
```json
[
  {
    "image_order": 0,
    "extracted_text": "This is the subtitle from the first image."
  },
  {
    "image_order": 1,
    "extracted_text": ""
  },
  {
    "image_order": 2,
    "extracted_text": "This is a subtitle\\nwith two lines."
  }
]
```
Do not include any explanatory text or markdown formatting outside of the main JSON array.
"""
    DEFAULT_PROMT = """
You are an intelligent OCR agent specializing in subtitle extraction. Your task is to analyze a series of pre-cropped images from video frames and accurately identify and extract ONLY the subtitle text.
These images may contain other text that is part of the video scene (e.g., signs, logos, on-screen graphics). You must differentiate between subtitle text and scene text. Subtitle text typically has a consistent style and placement within the cropped area.
For each image, provide the extracted subtitle text. Preserve original line breaks within the subtitle text, using the '\\n' character. If an image contains no subtitle text, or if you cannot confidently identify any text as a subtitle, return an empty string for the "text" field.
Sometime it will have duplicate result, dont touch just return result of OCR.
"""

    def __init__(
        self, 
        model_name: str = "gemini-2.5-flash", 
        batch_size: int = 100,
        promt: str = None
    ):
        try:
            from google import genai
            
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError(
                    "Gemini API key not found. Please set GEMINI_API_KEY or GOOGLE_API_KEY "
                    "environment variable or provide api_key parameter."
                )
            
            self.client = genai.Client(api_key=api_key)
            self.model_name = model_name
            self.batch_size = batch_size
            self.console = Console()
            self.promt = (self.DEFAULT_PROMT if not promt else promt) + "\n\n" + self.OUTPUT_PROMT

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
            
            for batch_idx, batch in enumerate(batches):
                self.console.print(f"[blue]Processing batch {batch_idx + 1}/{len(batches)} ({len(batch)} images)[/blue]")
                batch_results = self._process_batch([str(img) for img in batch])
                
                for img_path in batch:
                    img_name = img_path.name
                    results[img_name] = batch_results.get(str(img_path), "")
                
                progress.update(task, advance=1)
        
        return dict(sorted(results.items(), key=timecode_key))

    
    def _process_batch(self, img_paths: List[str]) -> Dict[str, str]:
        try:
            import PIL.Image
            
            images = []
            valid_paths = []
        
            for path in img_paths:
                try:
                    img = PIL.Image.open(path)
                    images.append(img)
                    valid_paths.append(path)
                except Exception as e:
                    print(f"Error loading image {path}: {e}")
            
            if not images:
                return {}
        
            
            contents = images + [f"Number of input image={len(valid_paths)}"] + [self.promt]
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config={
                    "temperature": 0.3,
                    # "top_p": 0.95,
                    # "top_k": 40,
                    "response_mime_type": "application/json",
                    "thinking_config": {
                        "include_thoughts": False,
                        "thinking_budget": 0
                    }
                }
            )
            try:
                parsed_results = self._parse_json_response(response.text)
                results = {}

                if len(parsed_results) != len(valid_paths):
                    warn("Model return missmatch array, result maybe wrong.")
                if isinstance(parsed_results, list):
                    for item in parsed_results:
                        image_order = item.get('image_order')
                        extracted_text = item.get('extracted_text', '')

                        img_path = valid_paths[image_order]
                        results[img_path] = extracted_text
                
                return results
                
            except Exception as e:
                print(f"Error parsing batch response: {e}")
                return {path: "" for path in valid_paths}
                
        except Exception as e:
            print(f"Error processing batch: {e}")
            return {path: "" for path in img_paths}
    
    def _parse_json_response(self, raw_response: str) -> List[Dict]:
        # direct parsing
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError:
            pass
        
        print(f"Failed to parse JSON response: {raw_response[:500]}...")
        return []