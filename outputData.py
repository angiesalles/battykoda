import scipy.io
import pickle

filename = 'todo/todo/asdf.wav'
samplerate, data = scipy.io.wavfile.read(filename)
with open(filename + '.pickle', 'rb') as f:
    p = pickle.load(f)

for idx in range(len(p.labels)):
    scipy.io.wavfile.write(str(idx)+'_'+p.labels[idx] + '.wav', data[p.start[idx]:p.end[idx]], samplerate)

