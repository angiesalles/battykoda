import scipy.io
import pickle

filename = '/home/angie/Efuscus/hungerGames/MicWavfiles/20210626/Pair_Trial1_1638_ch1.wav'
samplerate, data = scipy.io.wavfile.read(filename)
with open(filename + '.pickle', 'rb') as f:
    p = pickle.load(f)

for idx in range(len(p['labels'])):
    scipy.io.wavfile.write('for_gabby2/' + str(idx)+'_'+p['labels'][idx]['type_call'] + '.wav',
                           samplerate,
                           data[int(samplerate*p['onsets'][idx]):int(samplerate*p['offsets'][idx])])

