from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from os import rename
from pathlib import Path
from typing import Dict, List, Tuple

from vskernels import Bilinear
from vsmasktools import HardsubLine
from vspreview.api import is_preview
from vsrgtools import box_blur
from vssource import source
from vstools import clip_async_render, depth, get_prop, get_w, get_y, iterate, merge_clip_props, set_output, vs

core = vs.core

class Location(str, Enum):
    BOT = "bot"
    TOP = "top"

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
        clean = source(self.clean_path)[self.clean_offset :]
        hardsub = source(self.hardsub_path)[self.sub_offset :]

        if hardsub.height > 720:
            hardsub = Bilinear().scale(hardsub, width=get_w(720, hardsub), height=720)
        if clean.width != hardsub.width or clean.height != hardsub.height:
            clean = Bilinear().scale(clean, hardsub.width, hardsub.height)
        clean = depth(clean, 8)
        hardsub = depth(hardsub, 8)
        
        if hardsub.num_frames != clean.num_frames:
            min_frames = min(hardsub.num_frames, clean.num_frames)
            hardsub = hardsub[:min_frames]
            clean = clean[:min_frames]

        sub_height = hardsub.height - (hardsub.height / 5)
        sub_vert = 20

        bot_clean = clean.std.Crop(bottom=sub_vert, top=sub_height)
        bot_hardsub = hardsub.std.Crop(bottom=sub_vert, top=sub_height)

        top_clean = clean.std.Crop(bottom=sub_height, top=sub_vert)
        top_hardsub = hardsub.std.Crop(bottom=sub_height, top=sub_vert)

        bot_subtitles = self._get_subtitles(bot_clean, bot_hardsub)
        bot_subtitles = self._props_rename(bot_subtitles, Location.BOT)

        top_subtitles = self._get_subtitles(top_clean, top_hardsub)
        top_subtitles = self._props_rename(top_subtitles, Location.TOP)
        
        blank = hardsub.std.BlankClip(format=hardsub.format.id, keep=True)
        merge_props = merge_clip_props(blank, bot_subtitles, top_subtitles)

        if is_preview():
            set_output(
                top_subtitles,
                "top",
            )
            set_output(
                bot_subtitles,
                "bot",
            )
            set_output(hardsub, "sub")
            set_output(clean, "clean")
            set_output(merge_props, "diff")
            # set_output(diff, "diff")
            return
        
        rendered_props = self._get_props(merge_props)
        scene_changes = self._get_scene_changes(rendered_props, bot_subtitles, top_subtitles)
        self._rename_images(scene_changes, hardsub.fps_num, hardsub.fps_den)

    def _props_rename(self, clip: vs.VideoNode, location: Location) -> vs.VideoNode:
        def _rename(n, f):
            f = f.copy()
            for prop in f.props:
                f.props[f"{location.value}{prop}"] = f.props[prop]
                del f.props[prop]
            return f
        return clip.std.ModifyFrame(clip, _rename)


    def _get_subtitles(self, clean: vs.VideoNode, hardsub: vs.VideoNode) -> vs.VideoNode:
        clean_y = get_y(clean)
        hardsub_y = get_y(hardsub)

        mask = HardsubLine().get_mask(box_blur(hardsub_y), box_blur(clean_y))
        mask = iterate(mask, core.std.Maximum, 10).misc.SCDetect(0.012).vszip.PlaneAverage([0])

        blank = hardsub.std.BlankClip(format=hardsub.format.id, keep=True)
        merge = blank.std.MaskedMerge(hardsub.std.MakeDiff(clean), mask)
        return merge.std.CopyFrameProps(mask)

    def _get_props(self, clip: vs.VideoNode) -> List[Dict[str, int | float]]:
        return clip_async_render(
            clip, 
            None, 
            'Detecting subtitles...', 
            lambda n, f: {
                f"{loc.value}{suffix}": get_prop(f, f"{loc.value}{suffix}", float if suffix == "psmAvg" else int)
                for loc in Location 
                for suffix in ["psmAvg", "_SceneChangePrev", "_SceneChangeNext"]
            }
        )

    def _get_scene_changes(
        self, rendered_props: List[Dict[str, int | float]], bot_clip: vs.VideoNode, top_clip: vs.VideoNode
    ) -> List[Tuple[int, int, Location]]:
        scene_changes: List[Tuple[int, int, Location]] = []
        current_start = {Location.TOP: None, Location.BOT: None}
        
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="image_writer") as executor:
            futures = []
            
            for n, props in enumerate(rendered_props):
                for location in Location:
                    location_str = location.value
                    if props[f"{location_str}psmAvg"] < 0.9:
                        continue
                    elif props[f"{location_str}_SceneChangePrev"] == 1:
                        current_start[location] = n
                    elif props[f"{location_str}_SceneChangeNext"] == 1 and current_start[location] is not None:
                        source_clip = bot_clip if location == Location.BOT else top_clip

                        
                        scene_changes.append((current_start[location], n, location))
                        
                        future = executor.submit(
                            self._write_image, 
                            source_clip, 
                            current_start[location], 
                            location
                        )
                        futures.append(future)
                        
                        current_start[location] = None
            
            for future in futures:
                future.result()
        
        return scene_changes

    def _write_image(self, source_clip: vs.VideoNode, frame_number: int, location: Location) -> None:
        try:
            crop_value = int(source_clip.width / 3)
            crop_value = crop_value if crop_value % 2 == 0 else crop_value - 1

            if source_clip.format.color_family != vs.YUV:
                source_clip = Bilinear().resample(source_clip, format=vs.YUV420P8)
            crop = source_clip.acrop.AutoCrop(top=0, bottom=0, left=crop_value, right=crop_value)
            crop = Bilinear().resample(crop, format=vs.RGB24, matrix_in_s="709")
            images = crop.imwri.Write(
                imgformat="JPEG", 
                filename=f"{self.images_dir}/{location.value}_%d.jpg", 
                quality=90
            )
            images.get_frame(frame_number)            
        except Exception as e:
            print(f"Error writing image {location.value}_{frame_number}.jpg: {e}")

    def _rename_images(self, scene_changes: List[Tuple[int, int, Location]], fpsnum: int, fpsden: int):
        for scene_change in scene_changes:
            # Concat location (top, bot) to filename
            loc = scene_change[2].value
            frame_start = scene_change[0]
            frame_end = scene_change[1]

            filename = f"{loc}_{self._format_frame_time(frame_start, frame_end, fpsnum, fpsden)}"
            dst_path = Path(f"{self.images_dir}/{filename}.jpg")
            i = 1
            while dst_path.exists():
                dst_path = Path(f"{self.images_dir}/{filename}_{i}.jpg")
                i += 1
            if Path(f"{self.images_dir}/{loc}_{frame_start}.jpg").exists():
                rename(f"{self.images_dir}/{loc}_{frame_start}.jpg", dst_path)
            else:
                print(f"Image {loc}_{frame_start}.jpg not found")

    def _format_frame_time(self, start_frame: int, end_frame: int, fpsnum: int, fpsden: int) -> str:
        def frame_to_time_ms(frame: int) -> int:
            raw_ms = frame * fpsden * 1000 // fpsnum
            return (raw_ms + 5) - (raw_ms + 5) % 10
        
        start_time = self._ms_to_timecode(frame_to_time_ms(start_frame))
        end_time = self._ms_to_timecode(frame_to_time_ms(end_frame))

        start_formatted = f"{start_time[0]}_{start_time[1]}_{start_time[2]}_{start_time[3]}"
        end_formatted = f"{end_time[0]}_{end_time[1]}_{end_time[2]}_{end_time[3]}"
        return f"{start_formatted}__{end_formatted}"

    def _ms_to_timecode(self, ms: int) -> Tuple[str, str, str, str]:
        hours = ms // (1000 * 60 * 60)
        ms %= (1000 * 60 * 60)
        minutes = ms // (1000 * 60)
        ms %= (1000 * 60)
        seconds = ms // 1000
        centiseconds = (ms % 1000) // 10
        
        return (f"{hours}", f"{minutes:02d}", f"{seconds:02d}", f"{centiseconds:02d}")


if is_preview():
    filter = Filter(r"[SubsPlease] Dandadan - 21 (720p) [FAF7CD93].mkv", 0, r"DAN DA DAN S2 - Tập 21 [Việt sub] [NUCEFo1g2LI].mp4", 0, images_dir=Path("images"))
    filter.filter_videos()
