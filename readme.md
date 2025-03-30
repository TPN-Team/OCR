<!--toc:start-->

- [TPN-Team's OCR tool](#tpn-teams-ocr-tool)
  - [How it work?](#how-it-work)
  - [Accuracy](#accuracy)
  - [Setup](#setup)
    - [For Windows](#for-windows)
    - [For Arch linux](#for-arch-linux)
  - [Usage](#usage)
    - [Vapoursynth Method](#vapoursynth-method)
    - [VideoSubFinder Method](#videosubfinder-method)
  - [TODO](#todo)
  - [Acknowledgement](#acknowledgement)

# TPN-Team's OCR tool

## How it work?

Diff a hardsubbed video with video that is not hardsubbed to detect subtitles frames (Default: VapourSynth).
Another way is using VideoSubFinder to extract subtitles frames.
Extract these frames as images and OCR them using Google Lens.
Integrate the resulting text into an SRT subtitle file.

## Accuracy

Guess this :)

## Setup

### For Windows

Step 1: Install [Python](https://www.python.org/downloads/)

Step 2: Create the Virtual Environment: `python -m venv .venv`

Step 3: Activate the Virtual Environment:

```bash
# window cmd
.venv\Scripts\activate.bat
# or
# window powershell
Set-ExecutionPolicy Unrestricted -Scope Process
.venv\Scripts\Activate.ps1
```

Step 4: Install python libraies:
`pip install -r requirements.txt`

> [!NOTE]  
> If you are pretend to using OCRing images from VideoSubFinder only, you can skip the steps below.

Step 5: Install [VapourSynth](https://github.com/vapoursynth/vapoursynth/releases)

Step 6: Install vsrepo
`git clone https://github.com/vapoursynth/vsrepo`

Step 7: Install vapoursynth plugins:
`python ./vsrepo/vsrepo.py install acrop hysteresis lsmas misc tcanny tedgemask resize2 imwri`

Step 8: Install vsjetpack
`pip install vsjetpack vspreview`

### For Arch linux

Step 1: Install Python: `yay -S python`

Step 2: Create the Virtual Environment: `python -m venv .venv`

Step 3: Activate the Virtual Environment:

```bash
# for fish shell
. .venv/bin/activate.fish
# bash shell
. .venv/bin/activate
```

Step 4: Install python libraies: `pip install -r requirements.txt`

> [!NOTE]  
> If you are pretend to using OCRing images from VideoSubFinder only, you can skip the steps below.

Step 5: Install VapourSynth + ffmpeg: `yay -S vapoursynth ffmpeg`

Step 6: Install vapoursynth plugins:

```bash
yay -S vapoursynth-plugin-imwri-git vapoursynth-plugin-lsmashsource-git vapoursynth-plugin-misc-git vapoursynth-plugin-resize2-git vapoursynth-plugin-tcanny-git vapoursynth-plugin-tedgemask-git
git clone https://github.com/vapoursynth/vsrepo
# Install hysteresis plugin
sudo python ./vsrepo/vsrepo.py update
sudo python ./vsrepo/vsrepo.py install hysteresis
# The following commands to build acrop plugin
git clone https://github.com/Irrational-Encoding-Wizardry/vapoursynth-autocrop
# Link C interfaces to build acrop
cp -R /usr/include/vapoursynth/*.h ./vapoursynth-autocrop/
# Build and install acrop plugin
cd ./vapoursynth-autocrop/ && sudo g++ -std=c++11 -shared -fPIC -O2 ./autocrop.cpp -o /usr/lib/vapoursynth/libautocrop.so && cd ..
# Install vsjetpack
pip install vsjetpack vspreview
```

## Usage

### Vapoursynth Method
Prepare two sources.

- Muse HardSubed from YouTube, should choose 720p AVC format.
- Non HardSubed, should be the same resoluion with HardSubed source. Higher
  resolution will take a longer time to process.

Two sources must be synchronized. If not, adjust offset arguments.

```sh
python run.py clean.mkv sub.mp4
```

Batch mode
Prepare 2 folder, one is contain HardSub, another is contain Non HardSubed.
Episode naming between 2 folder must be the same. 
Give program the path to 2 folder above.
```sh
python run.py clean sub
```

For non-Muse sources, it is necessary to adjust the crop parameters to an
subtitles area, also may need to adjust SceneDetect threshold. In filter.py with preview.

Modify Filter function at the end of `filter.py` file.
```python
filter = Filter(r"clean.mkv", 0, r"sub.mkv", 0, images_dir=Path("images"))
```
```sh
python -m vspreview filter.py
```

### VideoSubFinder Method

If two sources is hard to sync, then use VSF instead to generate subtitles frame.

```sh
python run.py --engine videosubfinder -vsf {Path to VideoSubFinderWXW} -i {Path to Video Directory or Video File}
```
If Windows VideoSubFinderWXW path must have ".exe" suffix. eg: blabla/VideoSubFinderWXW.exe.

If VideoSubFinderWXW already in Path then you no need to specify path to VideoSubFinderWXW.


For more VideoSubFinder tunning param.
```sh
python run.py --help
```

## TODO

- Implement concat OCR (Merge an amount of image into one and OCR then get result base on coordinates. This would have better performance) (Need help).

## Acknowledgement

- [VapourSynth](https://www.vapoursynth.com/doc/index.html)
- [JET](https://github.com/Jaded-Encoding-Thaumaturgy)
- [image-ocr-google-docs-srt](https://github.com/Abu3safeer/image-ocr-google-docs-srt)
- [owocr](https://github.com/AuroraWright/owocr)

