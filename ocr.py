import concurrent.futures
from pathlib import Path
from threading import Lock
from typing import Literal, override

from rich.console import Console
from rich.progress import BarColumn, Progress, ProgressColumn, Task, TaskID, TextColumn, TimeRemainingColumn
from rich.text import Text

from gglens import GoogleLens


class OCRSpeedColumn(ProgressColumn):
    """Progress rendering."""
    
    @override
    def render(self, task: Task) -> Text:
        """Render bar."""

        return Text(f"{task.speed or 0:.02f} images/s")


class AssSubtitle:
    def __init__(self, start_time: str, end_time: str, text_content: str, is_top: bool=False):
        self.start_time: str = start_time
        self.end_time: str = end_time
        self.text_content: str = text_content
        self.style_name: str = "Top" if is_top else "Default"
        self.is_top: bool = is_top

    def convert_timestamp(self, s: str):
        h, m, rest = s.split(":")
        s, ms = rest.split(",")
        return f"{h}:{m}:{s}.{ms}"

    @override
    def __str__(self):
        return f"Dialogue: 0,{self.convert_timestamp(self.start_time)},{self.convert_timestamp(self.end_time)},{self.style_name},,0,0,0,,{self.text_content}\n"
        

class OCR_Subtitles:
    THREADS: int = 16
    IMAGE_EXTENSIONS: tuple[Literal['*.jpeg'], Literal['*.jpg'], Literal['*.png'], Literal['*.bmp'], Literal['*.gif']] = ("*.jpeg", "*.jpg", "*.png", "*.bmp", "*.gif")

    def __init__(self, output_subtitles_name: str, output_directory: str, images_dir_override: str) -> None:
        self.images: list[str] = []
        self.ass_dict: dict[int, AssSubtitle] = {}
        self.scan_lock: Lock = Lock()
        self.lens: GoogleLens = GoogleLens()
        self.images_dir, self.output_file_path = self._process_file(output_subtitles_name, output_directory, images_dir_override)
        self.completed_scans: int = 0

    def __call__(self):
        self.completed_scans = 0
        for extension in self.IMAGE_EXTENSIONS:
            paths = self.images_dir.rglob(extension)
            string_paths = [str(p) for p in paths]
            self.images.extend(string_paths)

        total_images = len(self.images)

        console = Console()
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TextColumn("{task.percentage:>3.0f}%"),
            OCRSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task: TaskID = progress.add_task("OCR images", total=total_images)
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.THREADS) as executor:
                future_to_image = {
                    executor.submit(self._process_image, Path(image), index + 1): image
                    for index, image in enumerate(self.images)
                }
                for future in concurrent.futures.as_completed(future_to_image):
                    image = future_to_image[future]
                    try:
                        future.result()
                    except Exception as exc:
                        console.print(f"[red]{image} generated an exception: {exc}[/red]")
                    else:
                        with self.scan_lock:
                            self.completed_scans += 1
                            progress.update(task, advance=1)
        self._write_ass()

    def _process_file(
        self,
        output_subtitles_name: str,
        output_directory: str,
        images_dir_override: str | None = None, 
    ) -> tuple[str, str]:
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
        

    def _process_image(self, image: Path, line: int):
        img_filename = str(image.absolute())
        img_name = str(image.name)

        try:
            text = self.lens(img_filename)
        except Exception as e:
            print(f"Error processing {img_name}: {e}")
            text = ""
            is_top = False
        if text is None:
            text = ""

        try:
            # Case filename = top/bot_time
            if img_name.split("_")[0] == "top" or img_name.split("_")[0] == "bot":
                is_top = img_name.split("_")[0] == "top"
                start_hour = img_name.split("_")[1][:2]
                start_min = img_name.split("_")[2][:2]
                start_sec = img_name.split("_")[3][:2]
                start_micro = img_name.split("_")[4][:3]

                end_hour = img_name.split("__")[1].split("_")[0][:2]
                end_min = img_name.split("__")[1].split("_")[1][:2]
                end_sec = img_name.split("__")[1].split("_")[2][:2]
                end_micro = img_name.split("__")[1].split("_")[3][:3]
            # Case filename = time. Backward compatibility
            else:
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
            print(
                f"Error processing {img_name}: Filename format is incorrect. Please ensure the correct format is used."
            )
            return

        start_time = f"{start_hour}:{start_min}:{start_sec},{start_micro}"
        end_time = f"{end_hour}:{end_min}:{end_sec},{end_micro}"

        subtitle: AssSubtitle = AssSubtitle(start_time, end_time, text, is_top)
        self.ass_dict[line] = subtitle

    def _write_ass(self):
        cleaned_ass_bot = []
        cleaned_ass_top = []
        previous_subtitle_bot = None
        previous_subtitle_top = None
        for _, subtitle in sorted(self.ass_dict.items()):
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
        ass_header = """[Script Info]
ScriptType: v4.00+
PlayDepth: 0
ScaledBorderAndShadow: Yes
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,60,&H00FFFFFF,&H00000000,&H4D000000,&H81000000,-1,0,0,0,100,100,0,0,1,3,0,2,60,60,40,1
Style: Top,Arial,60,&H00FFFFFF,&H00000000,&H4D000000,&H81000000,-1,0,0,0,100,100,0,0,1,3,0,8,60,60,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        try:
            
            with self.output_file_path.open("w", encoding="utf-8") as ass_file:
                _ = ass_file.write(ass_header)
                for subtitle in cleaned_ass_bot + cleaned_ass_top:
                    _ = ass_file.write(str(subtitle))
        except IOError as e:
            print(f"Error writing to output file {self.output_file_path}: {e}")
            raise