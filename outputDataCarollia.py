import scipy.io
import pickle

filename = '/home/jessica/Carollia/Social_Hierarchy/analyzed.audio.11062023/0410_0414/ANGIE1_20230410_181905.wav'
samplerate, data = scipy.io.wavfile.read(filename)
with open(filename + '.pickle', 'rb') as f:
    p = pickle.load(f)

for idx in range(len(p['labels'])):
    scipy.io.wavfile.write('for_gabby_carollia/' + str(idx)+'_'+p['labels'][idx]['type_call'] + '.wav',
                           samplerate,
                           data[int(samplerate*p['onsets'][idx]):int(samplerate*p['offsets'][idx])])

