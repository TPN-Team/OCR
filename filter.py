from os import rename
from pathlib import Path
from typing import List, Tuple

import vapoursynth as vs
import vskernels
from vsmasktools import HardsubLine
from vspreview.api import is_preview
from vstools import depth, get_depth, get_render_progress, get_w, iterate, set_output

core = vs.core


class Filter:
    def __init__(
        self, clean_path: str | Path, clean_offset: int, hardsub_path: str | Path, sub_offset: int, images_dir: Path
    ):
        self.clean_path: str | Path = clean_path
        self.clean_offset: int = clean_offset
        self.hardsub_path: str | Path = hardsub_path
        self.sub_offset: int = sub_offset
        self.images_dir: Path = images_dir

    def filter_videos(self):
        clean = core.lsmas.LWLibavSource(self.clean_path)[self.clean_offset :]
        hardsub = core.lsmas.LWLibavSource(self.hardsub_path)[self.sub_offset :]

        if hardsub.height > 720:
            hardsub = vskernels.Bilinear.scale(hardsub, width=get_w(720, hardsub), height=720)
        if clean.width != hardsub.width or clean.height != hardsub.height:
            clean = vskernels.Bilinear.scale(clean, hardsub.width, hardsub.height)

        if get_depth(clean) != get_depth(hardsub):
            clean = depth(clean, get_depth(hardsub))

        sub_height = hardsub.height - (hardsub.height / 5)
        sub_vert = 20

        bot_clean = clean.std.Crop(bottom=sub_vert, top=sub_height)
        bot_hardsub = hardsub.std.Crop(bottom=sub_vert, top=sub_height)

        top_clean = clean.std.Crop(bottom=sub_height, top=sub_vert)
        top_hardsub = hardsub.std.Crop(bottom=sub_height, top=sub_vert)

        bot_subtitles = self._get_subtitles(bot_clean, bot_hardsub)
        top_subtitles = self._get_subtitles(top_clean, top_hardsub)

        def merge_props(n, f):
            top_f = f[0]
            bot_f = f[1]
            sub_f = f[2].copy()
            for prop in top_f.props:
                sub_f.props[f"top{prop}"] = top_f.props[prop]
            for prop in bot_f.props:
                sub_f.props[f"bot{prop}"] = bot_f.props[prop]
            return sub_f

        blank = hardsub.std.BlankClip(format=hardsub.format.id, keep=True)
        mergeProps = blank.std.ModifyFrame(merge_props, clips=[top_subtitles, bot_subtitles, blank])

        if is_preview():
            set_output(
                top_subtitles.text.FrameProps(props=["_SceneChangePrev", "_SceneChangeNext", "PlaneStatsAverage"]),
                "top",
            )
            set_output(
                bot_subtitles.text.FrameProps(props=["_SceneChangePrev", "_SceneChangeNext", "PlaneStatsAverage"]),
                "bot",
            )
            set_output(hardsub.text.FrameProps(), "sub")
            set_output(clean.text.FrameProps(), "clean")
            return

        scene_changes = self._get_scene_changes(mergeProps, bot_subtitles, top_subtitles)
        self._rename_images(scene_changes, hardsub.fps_num, hardsub.fps_den)

    def _get_subtitles(self, clean: vs.VideoNode, hardsub: vs.VideoNode) -> vs.VideoNode:
        mask = HardsubLine().get_mask(hardsub, clean)
        # Use mask for better detection
        scd = mask.misc.SCDetect(0.02).std.PlaneStats()
        mask = iterate(mask, core.std.Maximum, 15)
        blank = hardsub.std.BlankClip(format=hardsub.format.id, keep=True)
        merge = blank.std.MaskedMerge(hardsub, mask)
        return merge.std.CopyFrameProps(scd)

    def _get_scene_changes(
        self, clip: vs.VideoNode, bot_clip: vs.VideoNode, top_clip: vs.VideoNode
    ) -> List[Tuple[int, int, str]]:
        with get_render_progress(title="Detecting scene changes...", total=clip.num_frames) as progress:
            scene_changes = []
            current_start = {"top": None, "bot": None}

            for n in range(clip.num_frames):
                f = clip.get_frame(n)
                for location in ["top", "bot"]:
                    if f.props[f"{location}PlaneStatsAverage"] < 0.02:
                        continue
                    elif f.props[f"{location}_SceneChangePrev"] == 1:
                        current_start[location] = n
                    elif f.props[f"{location}_SceneChangeNext"] == 1 and current_start[location] is not None:
                        source_clip = bot_clip if location == "bot" else top_clip
                        scene_changes.append((current_start[location], n, location))

                        crop_value = int(source_clip.width / 3)
                        crop_value = crop_value if crop_value % 2 == 0 else crop_value - 1
                        crop = source_clip.acrop.AutoCrop(top=0, bottom=0, left=crop_value, right=crop_value)
                        crop = vskernels.Point.scale(crop, format=vs.RGB24, matrix_in_s="709")

                        images = crop.imwri.Write(
                            imgformat="JPEG", filename=f"{self.images_dir}/{location}_%d.jpg", quality=95
                        )
                        images.get_frame(current_start[location])

                        current_start[location] = None

                progress.update(advance=1)

            return scene_changes

    def _rename_images(self, scene_changes: List[Tuple[int, int, str]], fpsnum: int, fpsden: int):
        for scene_change in scene_changes:
            # Concat location (top, bot) to filename
            filename = f"{scene_change[2]}_{self._format_frame_time(scene_change[0], scene_change[1], fpsnum, fpsden)}"
            dst_path = Path(f"{self.images_dir}/{filename}.jpg")
            i = 1
            while dst_path.exists():
                dst_path = Path(f"{self.images_dir}/{filename}_{i}.jpg")
                i += 1
            if Path(f"{self.images_dir}/{scene_change[2]}_{scene_change[0]}.jpg").exists():
                rename(f"{self.images_dir}/{scene_change[2]}_{scene_change[0]}.jpg", dst_path)
            else:
                print(f"Image {scene_change[2]}_{scene_change[0]}.jpg not found")

    def _format_frame_time(self, start_frame: int, end_frame: int, fpsnum: int, fpsden: int) -> str:
        start_time = self._to_timestamp(start_frame * fpsden / fpsnum)
        end_time = self._to_timestamp((end_frame + 1) * fpsden / fpsnum)

        start_formatted = f"{start_time[0]}_{start_time[1]}_{start_time[2]}_{start_time[3]}"
        end_formatted = f"{end_time[0]}_{end_time[1]}_{end_time[2]}_{end_time[3]}"
        return f"{start_formatted}__{end_formatted}"

    def _to_timestamp(self, total_seconds) -> Tuple[str, str, str, str]:
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        milliseconds = int((total_seconds - int(total_seconds)) * 1000)

        return (f"{hours:02d}", f"{minutes:02d}", f"{seconds:02d}", f"{milliseconds:03d}")


if is_preview():
    filter = Filter(r"clean.mkv", 0, r"sub.mkv", 0, images_dir=Path("images"))
    filter.filter_videos()
