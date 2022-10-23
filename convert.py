import pickle
import pandas
import os
import numpy as np
import math
from collections import defaultdict
excel_data = pandas.read_excel('/home/angie/Efuscus/HannaTerHofstede/Big brown bat social calls.xlsx',sheet_name=2)
mentioned_files = np.unique(excel_data['Avisoft.audio.file.name'])
todos = defaultdict(list)

file_lookup = {'EF2andEF3':  '20160721',
               'EF2andEF5':  '20160721',
               'EF2andEF9':  '20160802',
               'EF4andEF5':  '20160721',
               'EF7andEF14': '20160803',
               'EF8andEF9':  '20160802',
               'EF2andEF4':  '20160724',
               'EF2andEF7':  '20160802',
               'EF3andEF4':  '20160721',
               'EF7andEF12': '20160803',
               'EF7andEF8':  '20160802'}
for idx in range(excel_data.shape[0]):
    item = excel_data['Avisoft.audio.file.name'][idx]
    print(item)
    particle = item.split('_')[0].replace('AND', 'and')
    filename = '/home/angie/Efuscus/HannaTerHofstede/' + particle + '_' + file_lookup[particle] + '/Four-channel recordings/' + item
    floaty = float(excel_data['Time.in.Avisoft.audio.s'][idx])
    if math.isnan(floaty):
        continue
    todos[filename].append(floaty)

for key in todos:
    with open(key + '.pickle', 'wb') as pfile:
        pickle.dump({'onsets': (np.array(todos[key]) + 0.0).tolist(), 'offsets': (np.array(todos[key]) + 0.01).tolist(), 'labels': []}, pfile)
