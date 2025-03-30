import os
import subprocess
from pathlib import Path

from utils import get_in_path

cur_dir = Path(__file__).resolve().parent

class VideoSubFinder:
    def __init__(
        self,
        vsf_exe_path: str | None = None,
        clear_dirs: bool = True,
        run_search: bool = True,
        create_cleared_text_images: bool = False,
        open_video_opencv: bool = True,
        open_video_ffmpeg: bool = False,
        use_cuda: bool = False,
        start_time: str | None = None,
        end_time: str | None = None,
        top_video_image_percent_end: float = 0.2,
        bottom_video_image_percent_end: float = 0.0,
        left_video_image_percent_end: float = 0.0,
        right_video_image_percent_end: float = 1.0,
        general_settings: str | None = None,
        num_threads: int = -1,
        num_ocr_threads: int = -1,
        use_filter_color: str | None = None,
        moderate_threshold: float = 0.25,
        moderate_threshold_for_scaled_image: float = 0.25,
        image_scale_for_clear_image: int = 1,
        use_ILA_images_before_clear_txt_images_from_borders: bool = False,
        use_ILA_images_for_getting_txt_symbols_areas: bool = False,
        use_ILA_images_for_clear_txt_images: bool = True,
        clear_txt_images_by_main_color: bool = True,
        video_gamma: float = 1,
        **kwargs,
    ):
        []
        if vsf_exe_path is None:
            self.exe_path = get_in_path("VideoSubFinderWXW")
        else:
            self.exe_path = vsf_exe_path

        if self.exe_path is None or not os.access(self.exe_path, os.X_OK):
            raise ValueError("VSF Exe path must not be None.")
        
        self.txtimage = create_cleared_text_images

        param_dict = {
            "clear_dirs": clear_dirs,
            "run_search": run_search,
            "create_cleared_text_images": create_cleared_text_images,
            "open_video_opencv": open_video_opencv,
            "open_video_ffmpeg": open_video_ffmpeg,
            "use_cuda": use_cuda,
            "start_time": start_time,
            "end_time": end_time,
            "top_video_image_percent_end": top_video_image_percent_end,
            "bottom_video_image_percent_end": bottom_video_image_percent_end,
            "left_video_image_percent_end": left_video_image_percent_end,
            "right_video_image_percent_end": right_video_image_percent_end,
            "general_settings": general_settings,
            "num_threads": num_threads,
            "num_ocr_threads": num_ocr_threads,
        }

        run_list = [self.exe_path]
        for k, v in param_dict.items():
            if v is None or str(v) == "False":
                continue

            if str(v) == "True":
                run_list.append(f"--{str(k)}")
            else:
                run_list.extend([f"--{k}", str(v)])
        
        if general_settings is None:
            general_cfg_dict = {
                "use_filter_color": use_filter_color,
                "moderate_threshold": moderate_threshold,
                "moderate_threshold_for_scaled_image": moderate_threshold_for_scaled_image,
                "image_scale_for_clear_image": image_scale_for_clear_image,
                "use_ILA_images_for_getting_txt_symbols_areas": use_ILA_images_for_getting_txt_symbols_areas,
                "use_ILA_images_before_clear_txt_images_from_borders": use_ILA_images_before_clear_txt_images_from_borders,
                "use_ILA_images_for_clear_txt_images": use_ILA_images_for_clear_txt_images,
                "clear_txt_images_by_main_color": clear_txt_images_by_main_color,
                "video_gamma": video_gamma,
            }
            for k, v in general_cfg_dict.items():
                if v is None:
                    run_list.extend([f"/{k}", ""])

                value = str(int(v)) if isinstance(v, bool) else str(v) 
                run_list.extend([f"/{k}", value])

        self.run_list = run_list

    def __call__(self, video_path: str, output_dir: str) -> str:
        self.run_list.extend(["--input_video", video_path, "--output_dir", output_dir])

        # print(self.run_list)
        try:
            subprocess.run(
                self.run_list,
                check=False,
            )
            return output_dir
        except Exception as e:
            raise e


class VSFError(Exception):
    pass
