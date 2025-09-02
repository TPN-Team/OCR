import warnings
from pathlib import Path

from ass import AssSubtitle
from engine import OCREngine
from utils import text_cleanup, timecode_key


class OCR_Subtitles:
    THREADS: int = 16

    def __init__(
        self, 
        output_subtitles_name: str | Path, 
        output_directory: str | Path, 
        images_dir_override: str | Path,
        ocr_engine: OCREngine,
    ) -> None:
        self.ass_dict: dict[str, AssSubtitle] = {}

        self.ocr_engine = ocr_engine

        self.images_dir, self.output_file_path = self._process_file(
            output_subtitles_name, output_directory, images_dir_override
        )
        self.completed_scans: int = 0

    def __call__(self):
        results = self.ocr_engine(self.images_dir)
        
        if not results:
            warnings.warn("No images processed or no text extracted.")
            return
                
        for img_name, text in results.items():
            self._create_subtitle(img_name, text)
        
        self._write_ass()
        
        print(f"Saved subtitles to {self.output_file_path}")

    def _process_file(
        self,
        output_subtitles_name: str | Path,
        output_directory: str | Path,
        images_dir_override: str | Path | None = None,
    ) -> tuple[Path, Path]:
        try:
            output_path = Path(output_directory).resolve()
            if images_dir_override:
                images_dir_path = Path(images_dir_override).resolve()
            else:
                images_dir_path = (Path.cwd() / "images").resolve()

            images_dir_path.mkdir(parents=True, exist_ok=True)
            output_path.mkdir(parents=True, exist_ok=True)

            counter = 0
            output_file_path: Path = output_path / f"{output_subtitles_name}.ass"
            while output_file_path.exists():
                counter += 1
                output_file_path = output_path / f"{output_subtitles_name}_{counter}.ass"

            return (images_dir_path, output_file_path)
        except (FileNotFoundError, ValueError, ImportError, IOError, Exception) as e:
            print(f"Error type: {type(e).__name__}")
            print(f"Error details: {e}")
            raise

    def _create_subtitle(self, img_name: str, text: str):
        if text is None:
            text = ""
        
        text = text_cleanup(text)

        try:
            # Parse filename for timing information
            if img_name.split("_")[0] == "top" or img_name.split("_")[0] == "bot":
                is_top = img_name.split("_")[0] == "top"
                start_hour = img_name.split("_")[1][:2]
                start_min = img_name.split("_")[2][:2]
                start_sec = img_name.split("_")[3][:2]
                start_micro = img_name.split("_")[4][:2]

                end_hour = img_name.split("__")[1].split("_")[0][:2]
                end_min = img_name.split("__")[1].split("_")[1][:2]
                end_sec = img_name.split("__")[1].split("_")[2][:2]
                end_micro = img_name.split("__")[1].split("_")[3][:2]
            else:
                # Backward compatibility
                is_top = False
                start_hour = img_name.split("_")[0][:2]
                start_min = img_name.split("_")[1][:2]
                start_sec = img_name.split("_")[2][:2]
                start_micro = img_name.split("_")[3][:3]

                end_hour = img_name.split("__")[1].split("_")[0][:2]
                end_min = img_name.split("__")[1].split("_")[1][:2]
                end_sec = img_name.split("__")[1].split("_")[2][:2]
                end_micro = img_name.split("__")[1].split("_")[3][:3]
                
        except IndexError:
            print(f"Error processing {img_name}: Filename format is incorrect.")
            return

        start_time = f"{start_hour}:{start_min}:{start_sec},{start_micro}"
        end_time = f"{end_hour}:{end_min}:{end_sec},{end_micro}"

        subtitle = AssSubtitle(start_time, end_time, text, is_top)
        self.ass_dict[img_name] = subtitle

    def _write_ass(self):
        cleaned_ass_bot = []
        cleaned_ass_top = []
        previous_subtitle_bot = None
        previous_subtitle_top = None
        for _, subtitle in sorted(self.ass_dict.items(), key=timecode_key):
            previous_subtitle = previous_subtitle_top if subtitle.is_top else previous_subtitle_bot
            cleaned_ass = cleaned_ass_top if subtitle.is_top else cleaned_ass_bot
            if not subtitle.text_content or subtitle.text_content.isspace():
                continue
            if not previous_subtitle:
                cleaned_ass.append(subtitle)
                if subtitle.is_top:
                    previous_subtitle_top = subtitle
                else:
                    previous_subtitle_bot = subtitle
                continue
            if previous_subtitle.text_content.lower() == subtitle.text_content.lower():
                merged_subtitle = AssSubtitle(
                    start_time=previous_subtitle.start_time,
                    end_time=subtitle.end_time,
                    text_content=previous_subtitle.text_content,
                    is_top=subtitle.is_top,
                )
                cleaned_ass.pop()
                cleaned_ass.append(merged_subtitle)
            else:
                cleaned_ass.append(subtitle)

            if subtitle.is_top:
                previous_subtitle_top = cleaned_ass[-1]
            else:
                previous_subtitle_bot = cleaned_ass[-1]
        try:
            with self.output_file_path.open("w", encoding="utf-8") as ass_file:
                _ = ass_file.write(AssSubtitle.ASS_HEADER)
                for subtitle in cleaned_ass_bot + cleaned_ass_top:
                    _ = ass_file.write(str(subtitle))
        except IOError as e:
            print(f"Error writing to output file {self.output_file_path}: {e}")
            raise
