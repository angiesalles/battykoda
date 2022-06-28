import h5py
import numpy as np
from scipy.io import wavfile


def data_read(path_to_file):
    if path_to_file.endswith('.mat'):
        datafile = h5py.File(path_to_file)
        audiodata = np.array(datafile['ni_data']['mic_data'])
        fs = 250000
    else:
        fs, audiodata = wavfile.read(path_to_file)


    assert (np.sum(np.array(audiodata.shape) > 1) == 1) #here is where we assert only one channel
    audiodata = audiodata.flatten().astype(float)
    audiodata /= np.std(audiodata)

    return audiodata, fs



