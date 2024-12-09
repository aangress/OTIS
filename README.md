# OTIS
**Observation Transformation using Image Sonification**

*by Aaron Angress*

*This README assumes you have little to no experience with programming.*

OTIS is a Python script that will turn an image file into an audio file and vice versa. OTIS accomplishes this by treating every pixel in an image as a Discrete Fourier Transform value. Red values make up the lower third of the frequency range, green the middle, and blue the high. By running an inverse DFT on this image data, column by column, OTIS produces a series of waveform segments that can be interpreted as an audio signal. OTIS turns audio into images by reversing this process. OTIS is also capable of producing a video file showing the connection between corresponding audio and image files over time.

## Table of Contents
- [Installation](#Installation)
- [Usage](#Usage)
- [Features](#Features)

# Installation

First, make sure you have Python installed on your device. You can find downloads [here](https://www.python.org/downloads/). 

Next, open up a terminal on your device. Navigate to your desired directory using, for example:
```
cd desired/directory
```

Clone the repository and install dependencies:
```
git clone https://github.com/aangress/OTIS.git
cd OTIS
```

Activate the virtual environment *OTISenv*:
```Windows
OTISenv\Scripts\activate
```
```Linux/macOS
source OTISenv/bin/activate
```
This environment comes preloaded with all the Python packages you need to run OTIS. OTIS is now ready to go!

# Usage

After activating the virtual environment *OTISenv*, run OTIS using
```
python OTIS.py
```
OTIS will then ask a series of questions about which functionalities you want to use. Answer the questions by typing your responses into the terminal and pressing enter.

## Notes and Considerations
* Putting any image/audio files you want to transform in the same directory as OTIS will make it much easier to interface with OTIS.
* Creating a video takes a substantial amount of processing time.
* Using a large image or audio file will increase processing time. Consider using the image resizing feature within OTIS or trimming your audio file if it is long.
* OTIS supports most typical image formats.
* OTIS **ONLY** supports mono .wav audio files.
* You may need to download additional software to view the .mp4 videos that OTIS produces. VLC is a popular free media player that does job. It can be downloaded [here](https://www.videolan.org/vlc/).

# Features
* Crossfading: When converting image to audio, blend together audio segments to reduce tapping noises from discontinuities between segments. OTIS allows you to choose a crossfading duration from 0 to 100%. 100% duration means that no audio samples will maintain their original value, but all audio segments will be very-well blended together.
* Resizing: When converting image to audio, OTIS allows you to resize your image if you give it a large image. This can speed up processing time, especially for creating a video.
* Creating a video: OTIS allows you the option to use the current audio-image pair to create a video. A white vertical column will scan across the image as the corresponding audio segments play.

