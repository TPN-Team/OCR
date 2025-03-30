import enum

class Engine(enum.Enum):
    VAPOURSYNTH = "vapoursynth"
    VIDEOSUBFINDER = "videosubfinder"

    def __str__(self):
        return self.value