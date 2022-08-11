import DataReader
import pickle
def get_audio_bit(path_to_file, call_to_do, hwin):
    audiodata, fs, hashof = DataReader.DataReader.data_read(path_to_file)
    with open(path_to_file + '.pickle', 'rb') as pfile:
        segment_data = pickle.load(pfile)
    onset = (segment_data['onsets'][call_to_do] * fs).astype(int)
    offset = (segment_data['offsets'][call_to_do] * fs).astype(int)

    thr_x1 = audiodata[max(0, onset - (fs * hwin // 1000)):min(offset + (fs * hwin // 1000), len(audiodata)), :]
    return thr_x1, fs, hashof
