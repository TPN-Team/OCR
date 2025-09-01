from typing import override

class AssSubtitle:
    ASS_HEADER = """[Script Info]
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

    def __init__(self, start_time: str, end_time: str, text_content: str, is_top: bool = False):
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
        processed_text = self.text_content.replace('\n', '\\n')
        return f"Dialogue: 0,{self.convert_timestamp(self.start_time)},{self.convert_timestamp(self.end_time)},{self.style_name},,0,0,0,,{processed_text}\n"