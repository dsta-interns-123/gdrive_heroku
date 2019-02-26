from __future__ import print_function
from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
import io
from apiclient.http import MediaIoBaseDownload
import Vokaturi

import gspread 
from oauth2client.service_account import ServiceAccountCredentials 

from flask import Flask
from flask import request
from flask import make_response

import datetime 

import os
import json
app = Flask(__name__)

Vokaturi.load("lib/open/linux/OpenVokaturi-3-0-linux64.so")
SCOPES = 'https://www.googleapis.com/auth/drive'

@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)
    print("Request:")
    print(json.dumps(req, indent=4))
    res = processRequest(req)
    res = json.dumps(res, indent=4)
    print(res)
    r = make_response(res)
    r.headers['Content-Type'] = 'application/json'
    return r

def processRequest(req):
    
    #Obtain info from the query in Dialogflow
    result = req.get("queryResult")
    parameters = result.get("parameters")
    folder_name = parameters.get("FolderType")
    
    #verify credentials to use google drive API & get Google API client (or something like that)
    service = authentication()
    
    #verify credentials to use google sheet API & get Google sheet
    wks = open_gsheet()
    
    #check for file in drive
    file_list = get_wav_file(folder_name,service)
    if not file_list:    #If None, this will be false -> then flipped to true
        return {
            "fulfillmentText": "No such file in drive"
        }
    
    output = ""
    
    total_count = 0
    neutral_true = 0
    neutral_false = 0
    happy_true = 0
    happy_false = 0
    sad_true = 0
    sad_false = 0
    angry_true = 0
    angry_false = 0
    fear_true = 0
    fear_false = 0
    
    if len(file_list[0]) == 1:   
        live()
    elif len(file_list[0]) > 1:         
        batch()
    return {
            "fulfillmentText": output
    }

def live():
     position = file_list[0].index(item)
     file_name = file_list[0][position]
     file_id = file_list[1][position]
     request = service.files().get_media(fileId=file_id) #to edit so can read batch files 
    
     #downloads binary data of wav file and stored in a buffered stream
     fh = io.BytesIO()
     downloader = MediaIoBaseDownload(fh, request)
     done = False
     while done is False:
         status, done = downloader.next_chunk()
    
     #parse buffered stream into Vokaturi (TO-DO: FIX BYTE CONVERSION)
     buffer_length = fh.getbuffer().nbytes
     c_buffer = Vokaturi.SampleArrayC(buffer_length)
     c_buffer[:] = fh.getvalue() 
     voice = Vokaturi.Voice (8000, buffer_length)
     voice.fill(buffer_length, c_buffer)
     quality = Vokaturi.Quality()
     emotionProbabilities = Vokaturi.EmotionProbabilities()
     voice.extract(quality, emotionProbabilities)
        
     emotionName = ["neutral", "happy", "sad", "angry", "fear"]
    
     if quality.valid:
         emotionValue = [emotionProbabilities.neutrality, 
                         emotionProbabilities.happiness,
                         emotionProbabilities.sadness,
                         emotionProbabilities.anger,
                         emotionProbabilities.fear]
            
         output += "The results of the analysis of " + file_name + " is "
         output += 'Neutral: %.5f, ' % emotionProbabilities.neutrality
         output += 'Happiness: %.5f, ' % emotionProbabilities.happiness
         output += 'Sadness: %.5f, ' % emotionProbabilities.sadness
         output += 'Anger: %.5f, ' % emotionProbabilities.anger
         output += 'Fear: %.5f' % emotionProbabilities.fear
                  
         i = 0
         maxValue = 0
         maxIndex = 0;
         while i < len(emotionValue):
              if emotionValue[i] > maxValue:
                 maxIndex = i
                 maxValue = emotionValue[i]
              i += 1
         output += " Main emotion is " + emotionName[maxIndex]
     else: 
         output += "Not enough sonorancy to determine emotions." 
     voice.destroy() 
     return output 

def batch():
    for item in file_list[0]:       
        position = file_list[0].index(item)
        file_name = file_list[0][position]
        file_id = file_list[1][position]
        request = service.files().get_media(fileId=file_id) #to edit so can read batch files 
    
        #downloads binary data of wav file and stored in a buffered stream
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
    
        #parse buffered stream into Vokaturi (TO-DO: FIX BYTE CONVERSION)
        buffer_length = fh.getbuffer().nbytes
        c_buffer = Vokaturi.SampleArrayC(buffer_length)
        c_buffer[:] = fh.getvalue() 
        voice = Vokaturi.Voice (8000, buffer_length)
        voice.fill(buffer_length, c_buffer)
        quality = Vokaturi.Quality()
        emotionProbabilities = Vokaturi.EmotionProbabilities()
        voice.extract(quality, emotionProbabilities)
    
        row = 2
        emotionName = ["neutral", "happy", "sad", "angry", "fear"]
    
        if quality.valid:
           total_count += 1
           emotionValue = [emotionProbabilities.neutrality, 
                           emotionProbabilities.happiness,
                           emotionProbabilities.sadness,
                           emotionProbabilities.anger,
                           emotionProbabilities.fear]
           if wks.cell(row, 1).value == "":
              wks.update_cell(row,1,file_name)
              wks.update_cell(row,2,str(datetime.datetime.now()) + " GMT")
              wks.update_cell(row,3,'%0.5f' % emotionValue[0])
              wks.update_cell(row,4,'%0.5f' % emotionValue[1]) 
              wks.update_cell(row,5,'%0.5f' % emotionValue[2]) 
              wks.update_cell(row,6,'%0.5f' % emotionValue[3])
              wks.update_cell(row,7,'%0.5f' % emotionValue[4])
           else:
              while wks.cell(row, 1).value != "":
                    row += 1
              wks.update_cell(row,1,file_name)
              wks.update_cell(row,2,str(datetime.datetime.now()) + " GMT")
              wks.update_cell(row,3,'%0.5f' % emotionValue[0]) 
              wks.update_cell(row,4,'%0.5f' % emotionValue[1]) 
              wks.update_cell(row,5,'%0.5f' % emotionValue[2]) 
              wks.update_cell(row,6,'%0.5f' % emotionValue[3])
              wks.update_cell(row,7,'%0.5f' % emotionValue[4]) 
            
           true_emotions = ["angry", "fear", "sad", "neutral", "happy", "disgust", "surprise"]
           if file_name[0] == "a":
                real_emotion = true_emotions[0]
           elif file_name[0] == "f":
                real_emotion = true_emotions[1]
           elif file_name[0:2] == "sa":
                real_emotion = true_emotions[2]
           elif file_name[0] == "n":
                real_emotion = true_emotions[3]
           elif file_name[0] == "h":
                real_emotion = true_emotions[4]
           elif file_name[0] == "d":
                real_emotion = true_emotions[5]
           elif file_name[0:2] == "su":
                real_emotion = true_emotions[6]
           else:
                real_emotion = "not detected"
                wks.update_cell(row,9,real_emotion)
            
           i = 0
           maxValue = 0
           maxIndex = 0;
           while i < len(emotionValue):
               if emotionValue[i] > maxValue:
                  maxIndex = i
                  maxValue = emotionValue[i]
                  i += 1
               wks.update_cell(row,8,emotionName[maxIndex])
            
           if real_emotion == "neutral":
              if emotionName[maxIndex] == "neutral":
                 neutral_true += 1
              else: 
                 neutral_false += 1
           elif real_emotion == "happy":
                if emotionName[maxIndex] == "happy": 
                    happy_true += 1
                else:
                    happy_false += 1
           elif real_emotion == "sad": 
                if emotionName[maxIndex] == "sad":
                    sad_true += 1
                else:
                    sad_false += 1
           elif real_emotion == "angry":
                if emotionName[maxIndex] == "angry":
                    angry_true += 1
                else:
                    angry_false += 1
           elif real_emotion == "fear":
                if emotionName[maxIndex] == "fear":
                    fear_true += 1
                else:
                    fear_false += 1
           output += file_name      
        else:
           output += "Not enough sonorancy to determine emotions"    
        voice.destroy()
        
    neutral_rate = ((neutral_true)/(neutral_false + neutral_true))*100
    happy_rate = ((happy_true)/(happy_true + happy_false))*100
    sad_rate = ((sad_true)/(sad_true + sad_false))*100
    angry_rate = ((angry_true)/(angry_true + angry_false))*100
    fear_rate = ((fear_true)/(fear_true + fear_false))*100
        
    wks.update_cell(2, 11, '%0.5f' % neutral_rate)
    wks.update_cell(3, 11, '%0.5f' % happy_rate)
    wks.update_cell(4, 11, '%0.5f' % sad_rate)
    wks.update_cell(5, 11, '%0.5f' % angry_rate)
    wks.update_cell(6, 11, '%0.5f' % fear_rate)
        
    output += " analysis complete"
        
    return output, wks
        
def authentication():
    store = file.Storage('token.json')
    creds = store.get()
    if not creds or creds.invalid:
        flow = client.flow_from_clientsecrets('credentials.json', SCOPES)
        creds = tools.run_flow(flow, store)
    service = build('drive', 'v3', http=creds.authorize(Http()))
    return service
    
def open_gsheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_name("gsheet_credentials.json", scope)
    gc = gspread.authorize(credentials)
    wks = gc.open("Data").sheet1
    
    #Set headers for google sheet
    wks.update_cell(1, 1, "File")
    wks.update_cell(1, 2, "Time")
    wks.update_cell(1, 3, "Neutrality")
    wks.update_cell(1, 4, "Happiness")
    wks.update_cell(1, 5, "Sadness")
    wks.update_cell(1, 6, "Anger")
    wks.update_cell(1, 7, "Fear")
    wks.update_cell(1, 8, "Dominant Emotion")
    wks.update_cell(1, 9 , "True Emotion")
    wks.update_cell(1, 10, "Emotions")
    wks.update_cell(1, 11, "True Positive Rate")
    wks.update_cell(2, 10, "Neutral")
    wks.update_cell(3, 10, "Happy")
    wks.update_cell(4, 10, "Sad")
    wks.update_cell(5, 10, "Angry")
    wks.update_cell(6, 10, "Fear")
    return wks
  
def get_wav_file(folder_name, service):
    #Get the list of folders available
    folder_list = [[],[]]
    page_token = None
    while True:
        response = service.files().list(q="mimeType='application/vnd.google-apps.folder'",
                           spaces='drive', fields="nextPageToken, files(id, name)",
                           pageToken=page_token).execute()
        for item in response.get('files', []):
            folder_list[0].insert(len(folder_list[0]),item.get('name'))
            folder_list[1].insert(len(folder_list[1]),item.get('id'))
        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break
    
    #Search for the folder and get its ID
    
    folder_id = ""
    if folder_name in folder_list[0]:
        index = folder_list[0].index(folder_name)
        folder_id = folder_list[1][index]
    
    #Get the list of files in the folder available & add it if it's a WAV file
    file_list = [[],[]]
    page_token = None
    while True:
        response = service.files().list(
                q="'" + folder_id + "' in parents",
                spaces='drive', fields="nextPageToken, files(id, name)", pageToken=page_token).execute()
        for item in response.get('files', []):
            if ".wav" in item.get('name'):
                file_list[0].insert(len(folder_list[0]),item.get('name'))
                file_list[1].insert(len(folder_list[1]),item.get('id'))
        page_token = response.get('nextPageToken', None)
        if page_token is None:
            print("getting out")
            break
    
    #Select first file to analyse with Vokaturi (TO-DO: Run through all for full analysis)
    list_of_files = [[],[]]
    for item in file_list[0]: #If list empty, this will be false
        order = file_list[0].index(item)
        file_name = file_list[0][order]
        list_of_files[0].insert(order,file_name)
        file_id = file_list[1][order]
        list_of_files[1].insert(order,file_id)
    return list_of_files
