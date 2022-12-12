import pickle
import csv
def store_task(path_to_file, result):

    with open(path_to_file + '.pickle', 'rb') as pfile:
        segment_data = pickle.load(pfile)
    segment_data['labels'].append(result)
    with open(path_to_file+'.pickle', 'wb') as pfile:
        pickle.dump(segment_data, pfile)
    data = []
    data_pre = segment_data
    for idx in range(len(data_pre['onsets'])):
        data.append([data_pre['onsets'][idx], data_pre['offsets'][idx], data_pre['labels'][idx]['type_call']])
    with open(path_to_file + '.csv', 'w') as f:
        writer = csv.writer(f)
        writer.writerows(data)
    # newpath = sppath + os.sep + 'classifier'
    # soft_create_folders(newpath)
    #
    # call_to_do = len(segment_data['labels'])
    # thrX1, fs = get_audio_bit(path_to_file, call_to_do, 0)
    # scipy.io.wavfile.write(newpath + os.sep + '.'.join(browpath.replace('/','_').split('.')[:-1]) + str(onset) +'_'+\
    # result['type_call'] + '.wav', fs, thrX1)#ask gabby if she needs buffer around sound

