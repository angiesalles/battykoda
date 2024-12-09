import matplotlib.pyplot as plt
import matplotlib
import GetAudioBit
import os
import scipy.signal
import numpy as np
import SoftCreateFolders
from AppropriateFile import appropriate_file
import Hwin
# Force matplotlib to not use any Xwindows backend.
# https://stackoverflow.com/questions/2801882/generating-a-png-with-matplotlib-when-display-is-undefined
matplotlib.use('Agg')

def plotting(path, args, event, osfolder):
    event.wait()
    overview = args['overview'] == 'True'
    hwin = Hwin.overview_hwin if overview else Hwin.normal_hwin
    call_to_do = int(args['call'])
    contrast = float(args['contrast'])
    thr_x1, fs, hashof = GetAudioBit.get_audio_bit(osfolder + os.sep.join(path.split('/')[:-1]), call_to_do, hwin)
    errorc = fs<0
    fs = np.abs(fs)
    thr_x1 = thr_x1[:, int(args['channel'])]
    assert args['hash'] == hashof
    f, t, sxx = scipy.signal.spectrogram(thr_x1, fs, nperseg=2 ** 8, noverlap=254, nfft=2 ** 8)
    plt.figure(facecolor='black')
    ax = plt.axes()
    ax.set_facecolor('indigo')
    temocontrast = 10 ** contrast
    plt.pcolormesh(t, f, np.arctan(temocontrast * sxx), shading='auto')
    if not overview:
        plt.xlim(0, 0.050)
    ax.tick_params(axis='x', colors='white')
    ax.tick_params(axis='y', colors='white')
    ax.xaxis.label.set_color('white')
    ax.yaxis.label.set_color('white')
    if errorc:
        plt.ylabel('kevinerror')
        plt.xlabel('kevinerror')
    else:
        plt.ylabel('Frequency [Hz]')
        plt.xlabel('Time [sec]')
    SoftCreateFolders.soft_create_folders(appropriate_file(path, args, osfolder, folder_only=True))
    plt.savefig(appropriate_file(path, args, osfolder))
    plt.close()

