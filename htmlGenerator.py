def spgather(wholepath,osfolder):
   species=wholepath.split('/')[2]
   jpgname='/battykoda/'+species+'.jpg'

   f=open(osfolder+species+'.txt')
   lines=f.readlines()
   f.close()
   collectstrings=''
   for idx in range(len(lines)):
      namecall= lines[idx].split(',')[0]
      particle = ''
      if namecall == 'Echo':#this will be replaced with output of classifier
         particle = "checked='checked'"
      radiobutton=f'<input {particle} type="radio" id="{namecall}" name="type_call" value="{namecall}"><label for="{namecall}" style="font-family:Helvetica">{namecall}</label></br>'
      collectstrings+=radiobutton

   return collectstrings, jpgname




