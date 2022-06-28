import h5py
import numpy as np


def data_read(path_to_file):
    datafile = h5py.File(path_to_file)
    audiodata = np.array(datafile['ni_data']['mic_data'])
    assert (np.sum(np.array(audiodata.shape) > 1) == 1) #here is where we assert only one channel
    audiodata = audiodata.flatten()
    fs=250000
    return audiodata, fs


