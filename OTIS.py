# Imports
from PIL import Image
import numpy as np
from scipy.io.wavfile import write, read
from moviepy import VideoFileClip, AudioFileClip
import moviepy.video.io.ImageSequenceClip
import os
from tqdm import tqdm

# Calculate signal chunk from one column of pixels
def signalize_column(column):
    # Pixel order top-bottom -> bottom-top
    r = np.flip(column[:,0])
    g = np.flip(column[:,1])
    b = np.flip(column[:,2])

    # Combine all ffts together into one large fft
    # red->low freqs, green -> mid freqs, blue -> high freqs
    combined = np.concatenate((r, g, b))

    # Calculate inverse FFT of combined signal
    signal = np.fft.irfft(combined)

    # normalize signal for .wav writing [-32767, 32767]
    maxsig = max(signal)
    minsig = min(signal)
    normalized_signal = 2 * (signal - minsig)/ (maxsig - minsig) - 1
    normalized_signal = np.int16(normalized_signal * 32767)

    return normalized_signal

# Crossfade two signal segments together to prevent tapping noises from waveform discontinuities
def crossfade(waveform1, waveform2, duration):
    # In case user somehow manages to input too large of a crossfade duration (larger than the waveform segments)
    if len(waveform1) < duration or len(waveform2) < duration:
        raise ValueError("Waveforms must be longer than the crossfade duration.")

    # Separate waveform into unaffected and mixed segments
    w1_unaffected = waveform1[:-duration]
    w1_cross = waveform1[-duration:]
    w2_cross = waveform2[:duration]
    w2_unaffected = waveform2[duration:]

    # Blend mixed segments into eachother linearly and recombine all segments
    cross_combine = w1_cross * np.linspace(1, 0, duration) + w2_cross * np.linspace(0, 1, duration)
    return np.concatenate((w1_unaffected, np.int16(cross_combine), w2_unaffected))


# Transform image file into audio file
def image_to_audio(image_path, audio_path, fs, crossfadeflag, duration, resize_factor):

    # Open image and grab RGB pixel data
    image = Image.open(image_path).convert("RGB")
    image_data = np.array(image)
    rows = len(image_data)
    cols = len(image_data[0])

    # Resize image
    image = image.resize((int(resize_factor * cols), int(resize_factor * rows)))
    image_data = np.array(image)
    rows = len(image_data)
    cols = len(image_data[0])

    # Initialize first audio file segment
    waveform = signalize_column(image_data[:,0,:])

    # Calculate crossfade duration from duration percentage input by user
    duration = int(duration/100.0 * (len(waveform)//2))

    # Turn the ith column into an audio segment
    for i in range(1, cols):
        new_chunk = signalize_column(image_data[:,i,:])

        # Crossfade if required
        if crossfadeflag:
            waveform = crossfade(waveform, new_chunk, duration)

        # Add new segment to overall waveform
        else:
            waveform = np.concatenate((waveform, new_chunk))

    # Write the finished audio file
    write(audio_path, fs, waveform)

    # Close the image
    image.close()

    # Return useful information for video generation
    return image_data, waveform, cols


# Transform audio file into image
def audio_to_image(audio_path, cols, image_path):

    # Read .wav file sample frequency and waveform
    fs, signal = read(audio_path)

    # Calculate number of audio segments required and number of samples per segment
    signal_length = len(signal)
    samples_per_chunk = signal_length // cols
    remainder = signal_length % cols

    # Remove excess audio samples
    if remainder > 0:
        signal = np.array(signal[:-remainder])

    # Normalize signal [-1, 1]
    signal = signal / 32767.0

    # Calculate required number of rows for image
    signal_chunk = signal[:samples_per_chunk]
    fft = np.fft.rfft(signal_chunk)
    fftlen = len(fft)
    rows = fftlen//3

    # Initialize image array
    image_data = np.empty((rows, cols, 3))

    # For the ith audio segment
    for i in range(cols - 1):

        # Calculate the fft of the audio segment
        signal_chunk = signal[i * samples_per_chunk:(i+1) * samples_per_chunk]
        fft = np.fft.rfft(signal_chunk)

        # Divide up the spectrum into red (low), green (mid), blue (high)
        fftlen = len(fft)
        rfft = np.flip(fft[:fftlen//3])
        gfft = np.flip(fft[fftlen//3: 2*(fftlen//3)])
        bfft = np.flip(fft[2*(fftlen//3): 3*(fftlen//3)])

        # Set pixel data of the column
        image_data[:,i] = np.column_stack((np.abs(rfft), np.abs(gfft), np.abs(bfft)))

    # A small correction to help for normalizing color data
    # Sometimes, low frequencies will dominate red spectrum and mess up red normalization for pixel data
    # This is a temporary fix to minimize this problem
    image_data[-2:,:,0] = 0.001 * image_data[-2:,:,0]

    # For R, G, and B
    for color in range(3):
        # Find min and max fft spectrum values
        single_color_data = image_data[:,:,color]
        colormax = np.max(single_color_data)
        colormin = np.min(single_color_data)
    
        # Normalize color data
        image_data[:,:,color] = (single_color_data - colormin) * 255 / (colormax - colormin)

    # Attempt to reverse red correction
    image_data[-2:,:,0] = 1000 * image_data[-2:,:,0]

    # Format to int8
    image_data = np.round(image_data)
    image_data = image_data.astype(np.uint8)
    image = Image.fromarray(image_data)
    
    # Save and close image
    image.save(image_path)
    image.close()

    # Return useful information for video generation
    return signal, fs, image_data


# Generate video file. Vertical white bar scans across image as corresponding audio plays
# Can be used to create a video for audio->image or image->audio
def video_file(signal, fs, cols, image_data, video_path, audio_path):

    # Calculate length of sound in seconds
    sound_duration = len(signal) / fs

    # Calculate necessary frames per second
    fps = cols/sound_duration  

    # Create temporary image directory for storing frames
    image_folder = 'tempimagefolder'
    if not os.path.isdir(image_folder):
        os.mkdir(image_folder)

    # Remove any images in the directory
    image_files = [os.path.join(image_folder,img) for img in os.listdir(image_folder) if img.endswith(".png")]
    for img in image_files:
        os.remove(img)

    # Move a white vertical line across the image and generate a frame for each column of pixels
    for i in tqdm(range(cols)):
        
        current_image = image_data.copy()
        current_image[:,i] = np.array([255, 255, 255])
        Image.fromarray(current_image).save(os.path.join(image_folder, 'col' + str(i) + '.png'))

    print('Just wrapping things up...')
    # Make array of frame filenames and sort
    image_files = [os.path.join(image_folder,img) for img in os.listdir(image_folder) if img.endswith(".png")]
    image_files = sorted(image_files, key=lambda x: int(x.split('col')[1].split('.')[0]))

    # Generate video and add audio
    video_clip = moviepy.video.io.ImageSequenceClip.ImageSequenceClip(image_files, fps=fps)
    audio_clip = AudioFileClip(audio_path)
    video_clip.audio = audio_clip

    # Save video
    video_clip.write_videofile(video_path, logger = None)
    video_clip.close()

    # Remove any frames in temporary directory
    for img in image_files:
        os.remove(img)

# Main OTIS function. User interface.
def main():
    print('\n********** WELCOME TO OTIS! **********\n\nObservation Transformation with Image Sonification\n\nby Aaron Angress\n\n')


    # Image-> Audio or Audio->Image
    print('Enter 1 or 2:\n(1) Image to Audio\n(2) Audio to Image')
    while True:
        choice1 = int(input())
        if choice1 in [1, 2]:
            break
        else:
            print('Invalid entry. Please enter 1 or 2.')

    ####################################################################################################################
    # Image to Audio
    if choice1 == 1:

        # Image file
        print('Enter the directory/name of the image file you want to convert including the extension (ex: images/dog.jpg). Your audio/video file output will be saved with the same name but with extension .wav/.mp4')
        while True:
            filename = str(input())
            try:
                # Try to open the image
                with Image.open(filename) as img:
                    img.verify()  # Check if it's a valid image file
                break
            except Exception as e:
                print('Invalid filename entry')

        # Output file
        name, _ = filename.rsplit('.', 1)
        audio_path = name + '.wav'

        # Sampling freuency
        print('Enter the integer sampling frequency that you want to generate the audio file with in Hz (typical value: 44100)')
        while True:
            fs = input()
            try:
                fs = int(fs)
                if fs > 0:
                    break
                else:
                    print('Invalid sampling frequency. Enter a positive integer.')
            except Exception as e:
                print('Invalid sampling frequency. Enter a positive integer.')

        # Crossfade
        print('Do you want to crossfade the audio? (y/n)\n*Be warned, some data will be lost in the process and this will make it harder to reverse the transformtion process and recreate your original image.*')

        while True:
            crossfade = input()
            if crossfade == 'y':
                crossfade = True
                break
            elif crossfade == 'n':
                crossfade = False
                break
            else:
                print('Invalid entry. Enter y or n')

        # Crossfade duration
        crossfade_duration = 0
        if crossfade:
            print('Enter the percentage of the audio you want to crossfade. Entry must be greater than 0 and less than or equal to 100.')
            while True:
                try:
                    crossfade_duration = float(input())
                    if 0 < crossfade_duration <= 100:
                        break
                    else:
                        print('Invalid entry. Entry must be greater than 0 and less than or equal to 100.')
                except ValueError:
                    print('Invalid entry. Entry must be greater than 0 and less than or equal to 100.')

        # Generate video file
        print('Do you want to generate a corresponding video file? (y/n)')

        while True:
            videoflag = input()
            if videoflag == 'y':
                videoflag = True
                break
            elif videoflag == 'n':
                videoflag = False
                break
            else:
                print('Invalid entry. Enter y or n')

        # Image resizing
        print('Enter the factor you would like to resize your image by. Decreasing the size of your image (0 < factor < 1) may decrease processing time. Enter 1 to keep the original size of the image.')
        while True:
            resize_factor = input()
            try:
                resize_factor = float(resize_factor)
                if resize_factor > 0:
                    break
                else:
                    print('Invalid resizing factor. Enter a positive number.')
            except Exception as e:
                print('Invalid resizing factor. Enter a positive number.')

        print('\nHang tight...')
        # Generate audio file
        image_data, signal, cols = image_to_audio(filename, audio_path, fs, crossfade, crossfade_duration, resize_factor)

        # Generate video file
        if videoflag:
            video_path = name + '.mp4'
            video_file(signal, fs, cols, image_data, video_path, audio_path)


        print('\n\nCompleted!')

    


    ######################################################################################################################
    #Audio to Image
    else:

        # Audio file
        print('Enter the directory/name of the audio file you want to convert including the extension (ex: images/dog.wav).  File MUST be a mono .wav file. Your image/video file output will be saved with the same name but with extension .jpg/.mp4')
        while True:
            filename = input()
            try:
                # Check if the file has a .wav extension
                sample_rate, data = read(filename)
                if filename.lower().endswith('.wav') and data.ndim == 1:
                    break
                else:
                    print('Invalid file. Enter the name of a mono .wav file')
            except Exception as e:
                print('Invalid file. Enter the name of a mono .wav file')

        # Output files
        name, _ = filename.rsplit('.', 1)
        image_path = name + '.jpg'

        # Number of columns in output image
        print('Enter an integer for the number of columns of pixels you want your image to have')
        while True:
            cols = input()
            try:
                cols = int(cols)
                if cols > 0:
                    break
                else:
                    print('Invalid sampling frequency. Enter a positive integer.')
            except Exception as e:
                print('Invalid sampling frequency. Enter a positive integer.')

        # Video file
        print('Do you want to generate a corresponding video file? (y/n)')
        
        while True:
            videoflag = input()
            if videoflag == 'y':
                videoflag = True
                break
            elif videoflag == 'n':
                videoflag = False
                break
            else:
                print('Invalid entry. Enter y or n')
        
        print('\nHang tight...')
        # Generate image
        signal, fs, image_data = audio_to_image(filename, cols, image_path)

        # Generate video
        if videoflag:
            video_path = name + '.mp4'
            video_file(signal, fs, cols, image_data, video_path, filename)

        print('\n\nComplete!')

# Run interface
main()
    