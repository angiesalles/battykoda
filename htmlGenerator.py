import os

static_folder = 'home/data/battykoda/static/'


def available_species(osfolder):
   prelist = os.listdir(osfolder + static_folder)
   finallist = []
   for item in prelist:
      if item.endswith('.txt'):
         finallist.append(item[:-4])
   return finallist
def spgather(wholepath,osfolder, assumed_answer):
   species=wholepath.split('/')[2]
   jpgname='/static/'+species+'.jpg'

   f = open(osfolder + static_folder + species + '.txt')
   lines = f.readlines()
   f.close()
   collectstrings=''
   for idx in range(len(lines)):
      namecall= lines[idx].split(',')[0]
      particle = ''
      if namecall == assumed_answer:
         particle = "checked='checked'"
      radiobutton=f'<input {particle} type="radio" id="{namecall}" name="type_call" value="{namecall}"><label for="{namecall}" style="font-family:Helvetica">{namecall}</label></br>'
      collectstrings+=radiobutton

   return collectstrings, jpgname




