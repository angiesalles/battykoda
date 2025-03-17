import os
import platform

# Use a local static folder in the project directory
static_folder = "static"


def available_species():
   """
   Get list of available species based on .txt files in the static folder.
   

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
def spgather(wholepath, assumed_answer):
   """
   Gather species information for display
   
   Args:
      wholepath: The URL path
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
      line_parts = lines[idx].split(',', 1)
      namecall = line_parts[0].strip()
      description = line_parts[1].strip() if len(line_parts) > 1 else ""
      
      particle = ''
      if namecall == assumed_answer:
         particle = "checked='checked'"
      
      # Include the description in a span with appropriate styling
      desc_html = f'<span style="color: #a0a0a0; margin-left: 5px; font-size: 0.9em;">{description}</span>' if description else ''
      
      radiobutton=f'<input {particle} type="radio" id="{namecall}" name="type_call" value="{namecall}"><label for="{namecall}" style="font-family:Helvetica">{namecall}</label> {desc_html}</br>'
      collectstrings+=radiobutton

   return collectstrings, jpgname




