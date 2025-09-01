from typing import override
from rich.progress import ProgressColumn, Task
from rich.text import Text


class ImageSecondSpeedColumn(ProgressColumn):
    @override
    def render(self, task: Task) -> Text:
        return Text(f"{task.speed or 0:.02f} images/s")
    
class BatchSpeedColumn(ProgressColumn):

    @override
    def render(self, task: Task) -> Text:
        speed = task.speed or 0
        return Text(f"{speed:.2f} batches/s")