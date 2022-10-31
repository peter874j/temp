# from pyModbusTCP.client import ModbusClient
from concurrent.futures import thread
from flask import Flask, Response, render_template
import urllib3
import datetime
import numpy as np
import cv2
from threading import Thread
import json

class ThermalData():
    def concat_registers(self, client, maxRegNum, packetSize):
        """concat registers by packetSize

        Args:
            client (object): Modbus Client
            maxRegNum (int): target regs length
            packetSize (int): modbus packet size

        Returns:
            (list): regs concatenation
        """    
        concatRegs = list()   # store result in regs list
        startAddress = 0 
        while(len(concatRegs) < maxRegNum): 
            partPacket = client.read_input_registers(reg_addr=startAddress, reg_nb=packetSize)
            startAddress = startAddress + packetSize
            packetSize = packetSize if (maxRegNum - startAddress)>=packetSize else maxRegNum - startAddress
            concatRegs = concatRegs + partPacket
        return concatRegs

    def rising_detection(self, lastTempRegs, curTempRegs, risingWarningFlag, risingThres):
        """rising temperature detection

        Args:
            lastTempRegs (list): last temperature data
            curTempRegs (list): current temperature data
            risingWarningFlag (bool): rising temperature flag
            risingThres (int): Celsius temperature

        Returns:
            bool: rising temperature flag
        """    
        diff = 0
        for lastTemp, curTemp in zip(lastTempRegs, curTempRegs):
            diff = curTemp - lastTemp
            if diff >= risingThres:
                risingWarningFlag = True
                break
            else:
                risingWarningFlag = False

        return risingWarningFlag
        
    def mapping_thermal_image(self, tempRegs=[], deviceTemp=-1, maxTemp=80, minTemp=0, size=512):
        """generate thermal image

        Args:
            tempRegs (list, optional): 1024 temperature data. Defaults to [].
            maxTemp (int, optional): upper temperature on color bar. Defaults to 80.
            minTemp (int, optional): lower temperature on color bar. Defaults to 0.
            size (int, optional): thermal image size(recommended value is 512). Defaults to 512.

        Returns:
            array: thermalImg
        """    
        ### make thermal image
        tempRegs = np.array(tempRegs)
        # imgRegs = np.array([np.round(x) for x in tempRegs])
        tempMatraix = tempRegs.reshape((32, 32))   # reshape 1024 thermal data to 32x32 matrix 
        thermalImg = cv2.convertScaleAbs(tempMatraix, alpha=255/maxTemp, beta=minTemp)
        thermalImg = cv2.rotate(thermalImg, cv2.ROTATE_90_CLOCKWISE)   # ROTATE 90 CLOCKWISE 
        thermalImg = cv2.flip(thermalImg, 1)   # horizontal flip
        thermalImg = cv2.applyColorMap(thermalImg, cv2.COLORMAP_JET)
        thermalImg = cv2.resize(thermalImg, (size, size), interpolation=cv2.INTER_LINEAR)
        ### draw max. temperture point on the thermal image
        imgH, imgW, _ = thermalImg.shape
        gridSize = int(imgH/32)   # get max temperature index    
        iMax, jMax = np.unravel_index(tempMatraix.argmax(), tempMatraix.shape)
        iMin, jMin = np.unravel_index(tempMatraix.argmin(), tempMatraix.shape)
        minTemp = tempMatraix[iMin][jMin]
        maxTempPoint = (int(iMax*gridSize + 0.5*gridSize), int(jMax*gridSize + 0.5*gridSize))
        ### text content ###
        deviceText = f"Device Temp.(C):{deviceTemp}"
        maxTempText = f"Max. Temp.(C):{maxTemp}"
        ### draw text on image###
        cv2.circle(thermalImg, maxTempPoint, 1, (0, 0, 0), thickness=4)
        cv2.putText(thermalImg, str(maxTemp), (maxTempPoint[0]+5, maxTempPoint[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
        cv2.putText(thermalImg, deviceText, (5, imgH-25), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1, cv2.LINE_AA)
        cv2.putText(thermalImg, maxTempText, (5, imgH-10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1, cv2.LINE_AA)
        return thermalImg

    def data_polling(self, host1, port, urlMVIX):
        c1 = ModbusClient(host=host1, port=port, unit_id=1, debug=False, auto_open=True, auto_close=True)
        ### data polling
        while True:
            nowTime = datetime.now().strftime("%Y%m%d%H%M%S")
            ### open or reconnect TCP to server
            if not c1.is_open:
                if not c1.open():
                    print("unable to connect to " + host1 + ":" + str(port))
            
            ### read 16 registers at address 0, store result in regs list
            holdingRegs = c1.read_holding_registers(0, 16)   # 40001~40016
            maxTemp = holdingRegs[13]/100   # 40014, measured max. temperature, temperature(C) = raw data/100
            deviceTemp = holdingRegs[0]/100   # 40001, temperature inside IR Module, temperature(C) = raw data/100
            self.send_data_MVIX(urlMVIX, maxTemp, deviceTemp, nowTime)
            ### read 1024 registers at address 0, store result in regs list
            inputRawRegs = self.concat_registers(c1, 1024, 125)   # measured temperature 
            tempRegs = [raw/100 for raw in inputRawRegs]   # temperature(C) = raw data/100 
            
            ### mapping thermal image
            thermalImg = self.mapping_thermal_image(tempRegs=tempRegs, deviceTemp=deviceTemp, maxTemp=maxTemp, size=512)
            
            cv2.imshow("termalImg", thermalImg)
            cv2.waitKey(50)
            ### sleep 0.05s before next polling
            # time.sleep(0.05)
            yield Utils.encode_frame(thermalImg)

    # def data_polling_offline(self, videoPath, urlMVIX):
        # cap = cv2.VideoCapture(videoPath)
        ## data polling
        # while True:
            # nowTime = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            # maxTemp = 60.00
            # deviceTemp = 30.00
            # self.send_data_MVIX(urlMVIX, maxTemp, deviceTemp, nowTime)
            # ret, frame = cap.read()
            
            cv2.imshow("termalImg", frame)
            cv2.waitKey(50)
            ## sleep 0.05s before next polling
            time.sleep(0.05)
            # yield Utils.encode_frame(frame)
    
    def send_data_MVIX(self, url, maxTemp, moduleTemp, dateTime):
 
        try:
            response = str()
            eqID = "178" # 179/8716/8717
            paraID1 = "8713"   # 管厚
            paraID2 = "8714"   # 管徑

            encodedBody = json.dumps({
            "eq_id": eqID,
            "raw_datas":[
            {
            "p_id": paraID1, 
            "raw_value": str(maxTemp),
            "run_date_time": dateTime
            },
            {
            "p_id": paraID2, 
            "raw_value": str(moduleTemp),
            "run_date_time": dateTime
            }        
            ]
            })

            http = urllib3.PoolManager()

            headers = {'Content-Type': 'application/json; charset=utf-8', 'apiKey': '433576dd-1489-44e5-b19c-baa9c9463dec'}
            response = http.request('POST', url, headers=headers, body=encodedBody)
            print(response)
            print(response.status)
            # response = requests.request("POST", url, headers=headers, data=payload, timeout=1)
            # return response.status, response.data.decode('utf-8')   # 回傳data是byte格式，需解碼

        except:
            print("Send Data Fail...")
            pass

class FlaskAPI:

    __app = Flask(__name__)

    @classmethod
    def run(cls):
        cls.__app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False, threaded=True)

    @staticmethod
    def index():
        return render_template('Test.html')

    @staticmethod
    def displayStream():
        host1 = "192.168.1.1"
        port = 502
        urlMVIX = "http://192.168.50.167:8888/api/Data/UploadPollingRawData"
        test = ThermalData()
        return Response(test.data_polling(host1, port, urlMVIX), mimetype='multipart/x-mixed-replace; boundary=frame') 

    @classmethod
    def set_flaskAPI(cls):
        cls.__app.add_url_rule("/index", view_func=cls.index)
        cls.__app.add_url_rule("/stream", view_func=cls.displayStream)

class Utils:

    @staticmethod
    def encode_frame(frame):
        (flag, encodedImage) = cv2.imencode(".jpg", frame)         
        if flag: 
            encodedImage = b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n'
            return encodedImage 

    @classmethod
    def get(cls):
        while(True):
            frame = cap.getframe()
            yield cls.encode_frame(frame)

if __name__ == '__main__':
    FlaskAPI.set_flaskAPI()
    FlaskAPI.run()
    # Thread(target=FlaskAPI.run, args=())
    print("----------Test----------")
