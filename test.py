from __future__ import print_function
from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
import io
from apiclient.http import MediaIoBaseDownload

import gspread 
from oauth2client.service_account import ServiceAccountCredentials 

from flask import Flask
from flask import request
from flask import make_response

import datetime 

import os
import json
app = Flask(__name__)

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
    list_files = get_wav_file(folder_name,service)
    if not list_files:    #If None, this will be false -> then flipped to true
        return {
            "fulfillmentText": "No such file in drive"
        }
    
    output = "test"
     
    wks.update_cell(120,1,len(list_files[0]))
    wks.update_cell(121,1,len(list_files[1]))
    wks.update_cell(122,1,folder_name)
    wks.update_cell(123,1,list_files[0][0])
    wks.update_cell(124,1,list_file[0][1])
                  
    return {
            "fulfillmentText": output
    }

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
