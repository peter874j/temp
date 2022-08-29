import cv2
import os
from abc import ABC
import urllib3
# import requests
import pyglet
from pathlib import Path
from threading import Thread
from datetime import datetime
import csv
from Config import SrvCfg, ServiceConfig
from FileUtils import FileManagement


### 播放異常音檔
class Sound(ABC):
    def __init__(self, camID, fileName):
        self.music = pyglet.resource.media(fileName, streaming=False)
        self.camID = camID

    def play(self):   
        if ServiceConfig.allCamInfo[self.camID]["speakerFlag"]:
            self.music.play()

class HandsSound(Sound):
    def __init__(self, camID: str):
        super().__init__(camID, SrvCfg.soundOfHandsAlert[camID])


### 通報&紀錄異常內容
class AlarmUtils():
    def __init__(self, camID):
        self.fileManage = FileManagement()
        self.eqID = SrvCfg.eqID[camID]
        self.alarmSubject = SrvCfg.process + '_' + SrvCfg.eqID[camID] + '_' + SrvCfg.alarmMessage
        self.saveFile = SrvCfg.recordPath

    def save_frame(self, frame, dateText, path):
        try:
            self.fileManage.auto_remove_by_date(SrvCfg.recordPath, SrvCfg.maxDays)    # 30天自動刪除
            self.fileManage.auto_remove_by_size(SrvCfg.recordPath, SrvCfg.maxMBSize)   # 單位MB
            dateInfo = dateText.split(' ')[0].replace('/', '')
            timeInfo = dateText.split(' ')[1].replace(':', '')
            # savePath = os.path.join(SrvCfg.recordPath, dateInfo, 'HandsTouch')
            savePath = os.path.join(path, dateInfo, 'HandsTouch')
            Path(savePath).mkdir(parents=True, exist_ok=True) 
            self.saveFile = os.path.join(savePath, f'{timeInfo}_HandsFail.jpg')
            cv2.imwrite(self.saveFile, frame)
        except:
            print(f"【Warning】{path} is some problem...")

    def save_log(self, dateText, path):
        try:
            # 取得欄位資訊
            dateInfo = dateText.split(' ')[0].replace('/', '')
            # dateTime = dateText.split(' ')[0] + '  ' + dateText.split(' ')[1]   # YYYY/MM/DD hh:mm:ss
            dateTime = dateText.split(' ')[0] + 'T' + dateText.split(' ')[1]   # YYYY/MM/DDThh:mm:ss --> for KEDAS
            # savePath = os.path.join(SrvCfg.recordPath, dateInfo)
            savePath = os.path.join(path, dateInfo)
            Path(savePath).mkdir(parents=True, exist_ok=True) 
            logFile = os.path.join(savePath, 'alarm_logs.csv')
            file_is_exist = Path(logFile).is_file()
            # 先讀檔案, 取得列數(seqID)
            # if file_is_exist:
            #     with open(logFile, 'r', newline='') as csvfile:
            #         reader = csv.reader(csvfile)
            #         for row in reader:
            #             seqID = row[0]
            #     seqID = int(seqID) + 1
            # else:
            #     seqID = 1
        
            seqID = dateText.replace(" ","").replace("/","").replace(":","")

            # 開啟輸出的 CSV 檔案
            with open(logFile, 'a+', newline='') as csvfile:
                # 定義欄位
                fieldnames = ['seq_id', 'date_time', 'fab_id', 'eq_id', 'error_msg', 'record_path']
                # 建立 CSV 檔寫入器
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                # 寫入第一列的欄位名稱
                if not file_is_exist:
                    writer.writeheader()
                # 寫入資料, dateTime需轉為str格式, 避免顯示不全問題
                writer.writerow({'seq_id':seqID, 'date_time':dateTime, 'fab_id':SrvCfg.fabID, 'eq_id':self.eqID, 'error_msg':SrvCfg.alarmMessage, 'record_path':self.saveFile})
        except:
            print(f"【Warning】{path} is some problem...")

    def send_AMS(self):
        response = str()
        url = "http://10.1.10.70:2017/AlarmHandleService.asmx"

        payload = f"<?xml version=\"1.0\" encoding=\"utf-8\"?>\r\n<soap:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\"  \
            xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">\r\n  <soap:Body>\r\n  \
            <AlarmSendWithParam xmlns=\"http://uniworks.alarm/\">\r\n  <alarmSendWithParamMessage>\r\n    <FactoryID>{SrvCfg.fabID}</FactoryID>\r\n  \
            <SubSystemID>GSS</SubSystemID>\r\n  <EqpID></EqpID>\r\n    <AlarmInfoID>AC_GSS_AiMotion_01</AlarmInfoID>\r\n  \
            <AlarmSubject>{self.alarmSubject}</AlarmSubject>\r\n     <AlarmContent>{self.saveFile}</AlarmContent>\r\n  \
            <AlarmContentType>TEXT</AlarmContentType>\r\n <ReceiveType></ReceiveType>\r\n        <FilterParam></FilterParam>\r\n  \
            <InfoParam></InfoParam>\r\n      </alarmSendWithParamMessage>\r\n    </AlarmSendWithParam>\r\n  </soap:Body>\r\n</soap:Envelope>"

        headers = {
        'Content-Type': 'text/xml; charset=utf-8'
        }

        if SrvCfg.AMSSwitch == 'on':
            try:
                # response = requests.request("POST", url, headers=headers, data=payload, timeout=1)
                http = urllib3.PoolManager()
                response = http.request('POST', url, body=payload, headers=headers)
                # return response.status, response.data.decode('utf-8')   # 回傳data是byte格式，需解碼
            except:
                print("【Warning】: Post Msg to AMS Fail.")
                pass
        elif SrvCfg.AMSSwitch == 'off':
            pass
        else:
            print("【Warning】: Invalid AMS switch value.")

        ### 後續需寫入debug log，確認AMS回傳 xml訊息ReturnStatus欄位內容為OK/NG
        # return response.text
