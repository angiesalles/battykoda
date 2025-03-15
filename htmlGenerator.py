import os
import platform

# Use a local static folder in the project directory
if platform.system() == "Darwin":  # macOS
    static_folder = 'static/'
elif platform.system() == "Windows":
    static_folder = 'static\\'
else:
    static_folder = 'static/'


def available_species(osfolder=None):
   """
   Get list of available species based on .txt files in the static folder.
   
   Args:
      osfolder: Optional folder prefix (no longer used with local static folder)
   """
   try:
      prelist = os.listdir(static_folder)
      finallist = []
      for item in prelist:
         if item.endswith('.txt'):
            finallist.append(item[:-4])
      return finallist
   except FileNotFoundError:
      # Return empty list if static folder doesn't exist
      return []
def spgather(wholepath, osfolder, assumed_answer):
   """
   Gather species information for display
   
   Args:
      wholepath: The URL path
      osfolder: Optional folder prefix (no longer used with local static folder)
      assumed_answer: The currently selected answer
   """
   species = wholepath.split('/')[2]
   jpgname = '/static/'+species+'.jpg'
   
   try:
      with open(static_folder + species + '.txt') as f:
         lines = f.readlines()
   except FileNotFoundError:
      # Return empty data if species file doesn't exist
      return "", jpgname
   collectstrings=''
   for idx in range(len(lines)):
      namecall= lines[idx].split(',')[0]
      particle = ''
      if namecall == assumed_answer:
         particle = "checked='checked'"
      radiobutton=f'<input {particle} type="radio" id="{namecall}" name="type_call" value="{namecall}"><label for="{namecall}" style="font-family:Helvetica">{namecall}</label></br>'
      collectstrings+=radiobutton

   return collectstrings, jpgname




