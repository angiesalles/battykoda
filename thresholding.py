import numpy as np
import scipy.signal

def elliptic_filter(data, FLow, FHigh, Fs):
    sos = scipy.signal.ellip(2,3,40,[FLow FHigh]*2/Fs)
    return scipy.signal.sosfilt(sos, data)


def SmoothData(rawsong,Fs):
    F_low = 20000.0
    F_high = 100000.0
    sm_win = 2.0
    filtsong = elliptic_filter(rawsong, F_low, F_high, Fs)
    squared_song = filtsong ** 2
    len1 = round(Fs * sm_win / 1000)
    h = np.ones(1, len1) / len1
    smooth = np.convolve(h, squared_song)
    offset = round((len(smooth) - len(filtsong)) / 2)
    smooth = smooth[1 + offset:len(filtsong) + offset]
    return smooth


def SegmentNotes(smooth, Fs, threshold, min_int = 1.0, min_dur = 1.0):
    # onsets and offsets values are in seconds
    notetimes = smooth > threshold
    trans = np.convolve([1, -1], notetimes)
    onsets = np.argwhere(trans > 0)
    offsets = np.argwhere(trans < 0)
    if len(onsets) < 1 or len(offsets) < 1:
        return [], []
    assert(len(onsets) == len(offsets))
    # eliminate short intervals
    temp_int = (onsets[1:]-offsets[:-1]) * 1000 / Fs
    real_ints = temp_int > min_int
    onsets = np.vstack(onsets[0], onsets[1:][real_ints])
    offsets = np.vstack(offsets[:-1][real_ints], offsets[-1])
    # eliminate short notes
    temp_dur = (offsets - onsets) * 1000 / Fs
    real_durs = temp_dur > min_dur
    onsets = onsets[real_durs]
    offsets = offsets[real_ints]
    return onsets/Fs, offsets/Fs
