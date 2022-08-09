import h5py
import numpy as np
from scipy.io import wavfile
import time
import hashlib

class DataReader:
    cache = dict()
    @classmethod
    def data_read(cls, path_to_file):

        if path_to_file in cls.cache and time.time() - cls.cache[path_to_file]['time'] < 300:
                fs = cls.cache[path_to_file]['fs']
                audiodata = cls.cache[path_to_file]['audiodata']
                hashof = cls.cache[path_to_file]['hashof']
        else:
            hashof = hashlib.md5(open(path_to_file, 'rb').read()).hexdigest()
            if path_to_file.endswith('.mat'):
                datafile = h5py.File(path_to_file)
                audiodata = np.array(datafile['ni_data']['mic_data'])
                fs = 250000
            else:
                fs, audiodata = wavfile.read(path_to_file)
            cls.cache[path_to_file] = {'time': time.time(),
                                       'fs': fs,
                                       'audiodata': audiodata,
                                       'hashof': hashof}


        if len(audiodata.shape) == 1:
            audiodata = audiodata.reshape([-1,1]).repeat(3, axis = 1)
        audiodata = audiodata.astype(float)
        audiodata /= np.std(audiodata)

        return audiodata, fs, hashof



