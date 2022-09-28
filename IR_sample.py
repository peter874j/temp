from pyModbusTCP.client import ModbusClient
import time
import datetime
import numpy as np
import cv2

def concat_registers(client, maxRegNum, packetSize):
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

def rising_detection(lastTempRegs, curTempRegs, risingWarningFlag, risingThres):
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

def mapping_thermal_image(tempRegs=[], maxTemp=80, minTemp=0, thermalSize=512):
    """generate thermal image

    Args:
        tempRegs (list, optional): 1024 temperature data. Defaults to [].
        maxTemp (int, optional): upper temperature on color bar. Defaults to 80.
        minTemp (int, optional): lower temperature on color bar. Defaults to 0.
        thermalSize (int, optional): thermal image size(recommended value is 512). Defaults to 512.

    Returns:
        array: thermalImg
    """    
    ### make thermal image
    tempRegs = np.array(tempRegs)
    tempMatraix = tempRegs.reshape((32, 32))   # reshape 1024 thermal data to 32x32 matrix 
    thermalImg = cv2.convertScaleAbs(tempMatraix, alpha=255/maxTemp, beta=minTemp)
    thermalImg = cv2.rotate(thermalImg, cv2.ROTATE_90_CLOCKWISE)   # ROTATE 90 CLOCKWISE 
    thermalImg = cv2.flip(thermalImg, 1)   # horizontal flip
    thermalImg = cv2.resize(thermalImg, (thermalSize, thermalSize), interpolation=cv2.INTER_LINEAR)
    thermalImg = cv2.applyColorMap(thermalImg, cv2.COLORMAP_JET)
    ### draw max. temperture point on the thermal image
    imgH, imgW, _ = thermalImg.shape
    gridSize = int(imgH/32)   # get max temperature index    
    iMax, jMax = np.unravel_index(tempMatraix.argmax(), tempMatraix.shape)
    maxTempPoint = (int(iMax*gridSize + 0.5*gridSize), int(jMax*gridSize + 0.5*gridSize))
    cv2.circle(thermalImg, maxTempPoint, 1, (0, 0, 0), thickness=4)
    cv2.putText(thermalImg, str(maxTemp), (maxTempPoint[0]+5, maxTempPoint[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    return thermalImg
    
if __name__ == '__main__':
    ### init parameter
    host1 = "192.168.1.114"
    port = 502
    c1 = ModbusClient(host=host1, port=port, unit_id=1, debug=False, auto_open=True, auto_close=True)
    risingWarningFlag = False   # temperature rising 5C is warning
    lastTempRegs = []
    risingThres = 5
    minuteThres = 1   # rising temperature detection by a minute
    initFlag = True   # init lastTempRegs & lasttime
    ### data polling
    while True:
        nowTime = datetime.datetime.now()
        ### open or reconnect TCP to server
        if not c1.is_open:
            if not c1.open():
                print("unable to connect to " + host1 + ":" + str(port))
        
        ### read 16 registers at address 0, store result in regs list
        holdingRegs = c1.read_holding_registers(0, 16)   # 40001~40016
        maxTemp = holdingRegs[13]/100   # 40014, measured max. temperature, temperature(C) = raw data/100
        deviceTemp = holdingRegs[0]/100   # 40001, temperature inside IR Module, temperature(C) = raw data/100

        ### read 1024 registers at address 0, store result in regs list
        inputRawRegs = concat_registers(c1, 1024, 125)   # measured temperature 
        tempRegs = [raw/100 for raw in inputRawRegs]   # temperature(C) = raw data/100 
        if initFlag:
            lastTempRegs = tempRegs 
            lasttime = nowTime
            initFlag = False
            
        ### rising temperature detection by a minute
        diff = (nowTime - lasttime).total_seconds()/60
        if diff >= minuteThres:
            lasttime = nowTime
            risingWarningFlag = rising_detection(lastTempRegs, tempRegs, risingWarningFlag, risingThres)
            lastTempRegs = tempRegs

        ### rising warning
        if risingWarningFlag:
            print("temperature rising warning!!!")
        
        ### mapping thermal image
        thermalImg = mapping_thermal_image(tempRegs=tempRegs)
        cv2.waitKey(50)
        ### sleep 0.05s before next polling
        time.sleep(0.05)
