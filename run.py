import argparse
import re
from argparse import BooleanOptionalAction
from pathlib import Path
from shutil import rmtree

from engine import Engine
from ocr import OCR_Subtitles
from utils import engine_type, float_range
from vsf import VideoSubFinder


def create_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="A tool to OCR subtitles from video files, supporting both single-file and batch processing modes."
    )
    _ = parser.add_argument(
        "-o",
        "--output_dir",
        type=str,
        default="outputs",
        help="The path to output directory. Default: outputs",
    )

    _ = parser.add_argument(
        "--img_dir",
        type=str,
        default=None,
        help="The full path of directory contain extracted images, when specify this will skip image extract step.",
    )

    _ = parser.add_argument(
        "-e",
        "--engine",
        type=engine_type,
        default="vapoursynth",
        help=("Select the processing engine. " f"Choices (case-insensitive): {', '.join([e.value for e in Engine])}"),
    )

    vpy_param_group = parser.add_argument_group(title="VapourSynth")
    _ = vpy_param_group.add_argument(
        "--output-name",
        type=str,
        default=None,
        dest="output_subtitles",
        metavar="<outputname>",
        help="Base name for output subtitle files. In batch mode, episode numbers will be appended.",
    )
    _ = vpy_param_group.add_argument(
        "clean",
        nargs="?",
        metavar="<clean>",
        help="In single-file mode: path to the clean source video. "
        + "In batch mode: regex pattern for matching clean files, with episode number as group 1.",
    )

    _ = vpy_param_group.add_argument(
        "hardsub",
        nargs="?",
        metavar="<hardsub>",
        help="In single-file mode: path to the hardsub source video. "
        + "In batch mode: regex pattern for matching hardsub files, with episode number as group 1.",
    )

    _ = vpy_param_group.add_argument(
        "--batch", action="store_true", help="Enable batch processing mode to handle multiple episodes"
    )

    _ = vpy_param_group.add_argument(
        "--directory",
        type=str,
        metavar="<dir>",
        default=".",
        help="Directory containing video files for batch processing",
    )

    _ = vpy_param_group.add_argument(
        "--clean-offset",
        default=0,
        type=int,
        dest="offset_clean",
        metavar="<frames>",
        help="Frame offset for clean video. Default: 0",
    )

    _ = vpy_param_group.add_argument(
        "--hardsub-offset",
        default=0,
        type=int,
        dest="offset_sub",
        metavar="<frames>",
        help="Frame offset for hardsub video. Default: 0",
    )

    vsf_param_group = parser.add_argument_group(title="VideoSubFinder")
    _ = vsf_param_group.add_argument(
        "-vsf",
        "--vsf_exe_path",
        type=str,
        default=None,
        help="The full path of VideoSubFinderWXW. Default: from PATH (Much have .exe suffix in Windows).",
    )
    _ = vsf_param_group.add_argument(
        "-i",
        "--video_dir",
        type=str,
        default=None,
        help="The path of video or the path of video directory.",
    )
    _ = vsf_param_group.add_argument(
        "--clear_dirs",
        action=BooleanOptionalAction,
        default=True,
        help="Enable or disable clear Folders (remove all images), performed before any other steps. Default: True.",
    )
    _ = vsf_param_group.add_argument(
        "--run_search",
        action=BooleanOptionalAction,
        default=True,
        help="Enable or disable run Search (find frames with hardcoded text (hardsub) on video). Default: True.",
    )
    _ = vsf_param_group.add_argument(
        "--create_cleared_text_images",
        action=BooleanOptionalAction,
        default=False,
        help="Enable or disable create Cleared Text Images. Default: False.",
    )
    _ = vsf_param_group.add_argument(
        "--open_video_opencv",
        action=BooleanOptionalAction,
        default=True,
        help="Enable or disable open video by OpenCV (default). Default: True.",
    )
    _ = vsf_param_group.add_argument(
        "--open_video_ffmpeg",
        action=BooleanOptionalAction,
        default=False,
        help="Enable or disable open video by FFMPEG.",
    )
    _ = vsf_param_group.add_argument("--use_cuda", action=BooleanOptionalAction, default=False, help="use cuda")
    _ = vsf_param_group.add_argument(
        "--start_time",
        type=str,
        default="0:00:00:000",
        help="start time, default = 0:00:00:000 (in format hour:min:sec:milisec).",
    )
    _ = vsf_param_group.add_argument(
        "--end_time",
        type=str,
        default=None,
        help="end time, default = video length",
    )
    _ = vsf_param_group.add_argument(
        "-te",
        "--top_video_image_percent_end",
        type=float_range(0, 1.0),
        default=0.2,
        help="top video image percent offset from image bottom, can be in range [0.0,1.0], default = 1.0.",
    )
    _ = vsf_param_group.add_argument(
        "-be",
        "--bottom_video_image_percent_end",
        type=float_range(0, 1.0),
        default=0.0,
        help="bottom video image percent offset from image bottom, can be in range [0.0,1.0], default = 0.0.",
    )
    _ = vsf_param_group.add_argument(
        "-le",
        "--left_video_image_percent_end",
        type=float_range(0, 1.0),
        default=0.0,
        help="left video image percent end, can be in range [0.0,1.0], default = 0.0.",
    )
    _ = vsf_param_group.add_argument(
        "-re",
        "--right_video_image_percent_end",
        type=float_range(0, 1.0),
        default=1.0,
        help="right video image percent end, can be in range [0.0,1.0], default = 1.0.",
    )
    _ = vsf_param_group.add_argument(
        "-gs",
        "--general_settings",
        default=None,
        help="general settings (path to general settings *.cfg file, default = [VideoSubFinderWXW PATH]/settings/general.cfg).",
    )
    _ = vsf_param_group.add_argument(
        "-nthr",
        "--num_threads",
        type=int,
        default=-1,
        help="number of threads used for Run Search.",
    )
    _ = vsf_param_group.add_argument(
        "-nocrthr",
        "--num_ocr_threads",
        type=int,
        default=-1,
        help="number of threads used for Create Cleared TXT Images.",
    )
    _ = vsf_param_group.add_argument(
        "--use_filter_color",
        type=str,
        default=None,
        help="Define Use Filter Colors.",
    )
    _ = vsf_param_group.add_argument(
        "--moderate_threshold",
        type=float_range(0.25, 0.6),
        default=0.25,
        help="Define moderate_threshold. Default: 0.25.",
    )
    _ = vsf_param_group.add_argument(
        "--moderate_threshold_for_scaled_image",
        type=float_range(0.1, 0.6),
        default=0.25,
        help="Define moderate_threshold_for_scaled_image [0.1 - moderate_threshold]. Default: 0.25.",
    )
    _ = vsf_param_group.add_argument(
        "--image_scale_for_clear_image",
        type=int,
        default=4,
        help="Define image scale for clear image. Default: 2.",
    )
    _ = vsf_param_group.add_argument(
        "--use_ILA_images_for_getting_txt_symbols_areas",
        action=BooleanOptionalAction,
        default=False,
        help="Enable or disable use ILA images for getting txt symbols areas. Default: False.",
    )
    _ = vsf_param_group.add_argument(
        "--use_ILA_images_before_clear_txt_images_from_borders",
        action=BooleanOptionalAction,
        default=False,
        help="Enable or disable use ILA images before clear txt images from borders. Default: False.",
    )
    _ = vsf_param_group.add_argument(
        "--use_ILA_images_for_clear_txt_images",
        action=BooleanOptionalAction,
        default=True,
        help="Enable or disable use ILA images for clear txt images. Default: True.",
    )
    _ = vsf_param_group.add_argument(
        "--clear_txt_images_by_main_color",
        action=BooleanOptionalAction,
        default=True,
        help="Enable or disable clear txt images by main color. Default: True.",
    )
    _ = vsf_param_group.add_argument(
        "--video_gamma",
        type=float_range(0.0, 1.0),
        default=1.0,
        help="Define video_gamma [0.0 - 1.0]. Default: 1.0.",
    )
    return parser


def process_vsf(video_list: list[Path], output_dir: str, vsf: VideoSubFinder):

    print("Extracting subtitle images with VideoSubFinder (takes quite a long time) ...")
    video_num = len(video_list)
    for i, one_video in enumerate(video_list):
        print(f"[{i+1}/{video_num}] Starting to extract {one_video} key frame")

        save_name = Path(one_video).stem
        save_dir = Path(output_dir) / save_name
        save_vsf_dir = save_dir / "VSF_Results"

        try:
            vsf(one_video, save_vsf_dir)
        except Exception as e:
            print(f"Extract {one_video} error, {e}, skip")
            continue

        print(f"[{i + 1}/{video_num}] Starting to run {one_video} ocr")

        images_dir = Path(save_vsf_dir) / "RGBImages"
        if vsf.txtimage:
            images_dir = Path(save_vsf_dir) / "TXTImages"

        ocr = OCR_Subtitles(output_subtitles_name=save_name, output_directory=save_dir, images_dir_override=images_dir)
        ocr()

    return


def process_episode_vpy(
    output_subtitles_name: str,
    output_directory: str,
    offset_clean: int,
    offset_sub: int,
    clean_path: str | Path | None = None,
    sub_path: str | Path | None = None,
) -> None:

    from filter import Filter

    if not clean_path or not sub_path:
        raise ValueError("clean_path and sub_path arguments are required when do_filter is True.")

    save_name = Path(sub_path).stem
    if output_subtitles_name is not None:
        save_name = output_subtitles_name
    save_dir = Path(output_directory) / save_name
    save_img_dir = save_dir / "images"

    engine = OCR_Subtitles(save_name, save_dir, save_img_dir)

    if engine.images_dir.exists() and any(engine.images_dir.iterdir()):
        print(f"Removing existing images directory: {engine.images_dir}")
        try:
            rmtree(engine.images_dir)
        except OSError as e:
            print(f"Warning: Failed to remove directory {engine.images_dir}. Error: {e}")
    engine.images_dir.mkdir(parents=True, exist_ok=True)

    filter = Filter(clean_path, offset_clean, sub_path, offset_sub, engine.images_dir)
    filter.filter_videos()

    engine()


def batch_process_vpy(output_directory: str, clean_dir: str, sub_dir: str, offset_clean: int, offset_sub: int) -> None:
    print("Batch mode!")
    ep_regex = r"(.*?)(\d{2,3}).*"
    episodes: dict[str, dict[str, Path]] = {}

    clean_video_list = Path(clean_dir).glob("*.*")
    sub_video_list = Path(sub_dir).glob("*.*")

    for f in clean_video_list:
        file_name = Path(f).name
        clean_match = re.search(ep_regex, file_name)
        if clean_match:
            episode = clean_match.group(2)
            if episode not in episodes:
                episodes[episode] = {"clean": f}
            elif "clean" not in episodes[episode]:
                episodes[episode]["clean"] = f

    for f in sub_video_list:
        file_name = Path(f).name
        sub_match = re.search(ep_regex, file_name)
        if sub_match:
            episode = sub_match.group(2)
            if episode not in episodes:
                episodes[episode] = {"hardsub": f}
            elif "hardsub" not in episodes[episode]:
                episodes[episode]["hardsub"] = f

    print(f"Find {len(episodes)} episodes")

    for episode, files in sorted(episodes.items()):
        if "clean" in files and "hardsub" in files:
            print(f"Processing episode {episode}")
            output_subtitles_name = Path(files["hardsub"]).stem
            process_episode_vpy(
                output_subtitles_name=output_subtitles_name,
                output_directory=output_directory,
                offset_clean=offset_clean,
                offset_sub=offset_sub,
                clean_path=files["clean"],
                sub_path=files["hardsub"],
            )
        else:
            print(f"Skipping episode {episode} - missing clean or hardsub file")


def main():
    parser = create_arg_parser()
    args = parser.parse_args()

    engine = Engine(args.engine)
    output_dir: str = args.output_dir

    if args.img_dir:
        subtitle_name = args.output_subtitles
        if args.output_subtitles is None:
            subtitle_name = "output_subtitles"
        ocr = OCR_Subtitles(subtitle_name, output_dir, args.img_dir)
        ocr()
        return

    if engine == Engine.VIDEOSUBFINDER:

        video_formats = [".mp4", ".avi", ".mov", ".mkv"]

        vsf = VideoSubFinder(**vars(args))

        video_path = args.video_dir
        if video_path is None:
            parser.error("--video-dir is required when using VideoSubFinnder engine")

        if Path(video_path).is_dir():
            video_list = Path(video_path).rglob("*.*")
            video_list = [v.absolute() for v in video_list if v.suffix.lower() in video_formats]
        else:
            video_list = [Path(video_path)]

        process_vsf(video_list, output_dir, vsf)

    elif engine == Engine.VAPOURSYNTH:
        video_formats = [".mp4", ".avi", ".mov", ".mkv"]
        clean: str = args.clean
        sub: str = args.hardsub
        if not args.clean or not args.hardsub:
            parser.error("The 'clean' and 'sub' arguments are required when use VapourSynth engine.")
            return
        if Path(clean).is_dir() and Path(sub).is_dir():
            batch_process_vpy(
                output_directory=output_dir,
                clean_dir=args.clean,
                sub_dir=args.hardsub,
                offset_clean=args.offset_clean,
                offset_sub=args.offset_sub,
            )
        else:
            process_episode_vpy(
                output_subtitles_name=args.output_subtitles,
                output_directory=output_dir,
                offset_clean=args.offset_clean,
                offset_sub=args.offset_sub,
                sub_path=args.hardsub,
                clean_path=args.clean,
            )

    print("Done")


if __name__ == "__main__":
    main()
