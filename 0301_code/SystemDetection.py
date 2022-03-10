import time
import cv2
from threading import Thread
import pygame
import sys
from datetime import datetime
sys.path.append('./AIModule')
from utils.plots import plot_fail_touch
import numpy as np
import math
from collections import deque
from ObjectUtils import Zone, Label, Step
from Config import ServiceConfig
import copy
from pathlib import Path
import os

def write_video(outVideo, q):
    for frame in q:
        outVideo.write(frame)

def save_video(startTime, q): 
    dateText = startTime.strftime('%Y/%m/%d')
    timeText = startTime.strftime('%H:%M:%S')
    dateInfo = dateText.split(' ')[0].replace('/','')
    timeInfo = timeText.split(' ')[1].replace(':','')
    
    savePath = os.path.join('record', dateInfo, 'Motion')
    Path(savePath).mkdir(parents=True, exist_ok=True) 
    saveFile = os.path.join(savePath, f'{timeInfo}_MotionFail.avi')

    width =  1280
    height = 720
    fps = 15
    fourcc = cv2.VideoWriter_fourcc('M','P','4','2')
    outVideo = cv2.VideoWriter(saveFile, fourcc, fps, (width, height))

    subProcess = Thread(write_video(outVideo, q))
    subProcess.start()

def save_frame(frame, dateText):
    dateInfo = dateText.split(' ')[0].replace('/','')
    timeInfo = dateText.split(' ')[1].replace(':','')
    savePath = os.path.join('record', dateInfo, 'HandsTouch')
    Path(savePath).mkdir(parents=True, exist_ok=True) 
    saveFile = os.path.join(savePath, f'{timeInfo}_HandsFail.jpg')
    cv2.imwrite(saveFile, frame)

class PlacementDetection:

    def __init__(self, allRectangleInfo):

        self.allRectangleInfo = allRectangleInfo

    def put_to_zone(self, region, yoloResult):

        if len(yoloResult["hand_PCB_coordinate"]) != 0:
            for yoloRectangle in yoloResult["hand_PCB_coordinate"]:
                for info in self.allRectangleInfo:  # 要改
                    if info.zoneName == region:
                        return info.contains_point(yoloRectangle.centerPoint)          
        return False

class ProcessDetection:

    def __init__(self, allRectangleInfo):
        self.allRectangleInfo = allRectangleInfo
        self.jigLabel = Label.initialize()
        self.currentStep = Step.initialize()

    def is_first_step(self):
        if self.jigLabel.previous == Label.type1: 
            return True
        return False   
   
    #### 有疑問 ####
    def is_final_step(self):
        if self.currentStep.number == len(Label.order)-1:
            return True 
        else:
            return False 
    ################

    def __yoloResult_is_none(self, yoloResult):
        if len(yoloResult) == 0:
            return True

    def run(self, yoloResult):

        if self.is_final_step == True:
            self.currentStep = Step.initialize()
            
        if self.__yoloResult_is_none(yoloResult["label"]):
            return "NONE", self.currentStep.number
        
        self.jigLabel.update_info(yoloResult, self.allRectangleInfo)

        if Step.goto_next(self.jigLabel):

            self.currentStep.update_info()

            return self.jigLabel.is_not_same_label(self.currentStep), self.currentStep.number
                
        return "NONE", self.currentStep.number

class Motion:

    def __init__(self, model, allRectangleInfo):
        self.model = model
        self.allRectangleInfo = allRectangleInfo
        self.processDetection = ProcessDetection(self.allRectangleInfo)
        self.placementDetection = PlacementDetection(self.allRectangleInfo)
        # self.q = deque()
        self.q = []
        self.temp1 = False
        self.haveAlarm = False
        self.initialize_parameter()

    def initialize_parameter(self):
        # self.q.clear()
        self.processDetection.currentStep.number = 0
        self.centerPointAToD = 0
        self.processEnd = False
        self.placementOK = {"A":False, "C1":False, "C2":False, "D":False}
        self.waitCorrection = {"A":False, "D":False}
        
    def run(self, image):

        self.q.append(image)

        if self.processEnd: # processDetection.is_final_step
            if self.needRecord:
                self.needRecord = False
                temp = copy.deepcopy(self.q)
                save_video(datetime.now(), temp) 
            self.initialize_parameter()  
            self.q.clear()
            self.haveAlarm = False
            self.needRecord = False
    
        # 跑YOLO
        yoloResult = self.model.detect_motion(image)
        print(f'yoloResult: {yoloResult}', self.processDetection.currentStep.number)

        isAnomalyStep, numOfCurrentStep = self.processDetection.run(yoloResult)
      
        #################################################### 用放置去判斷是否正確 ################################################################    
        if self.processDetection.currentStep.number == 0:
            if not self.placementOK["C2"] and self.temp1:
                C2_placementOK = self.placementDetection.put_to_zone(Zone.C, yoloResult)
                if C2_placementOK:
                    self.placementOK["C2"] = True
                    self.processEnd = True
                    self.temp1 = False
                    return ["NO"], [4]
            if not self.placementOK["C1"]:
                C1_placementOK = self.placementDetection.put_to_zone(Zone.C, yoloResult)
                if C1_placementOK:
                    self.placementOK["C1"] = True
                    # return ["NO"], [numOfCurrentStep]

        # 目前步驟待定 : step. 2 要不斷去判斷 D與A區的狀態
        elif self.processDetection.currentStep.number == 2:

            if self.haveAlarm and isAnomalyStep != "NONE":
                return ["YES"], [numOfCurrentStep]

            # 判斷A區->D區 (第二步補救)
            if self.waitCorrection['D']:
                if not self.placementOK['A']:
                    A_placementOK = self.placementDetection.put_to_zone(Zone.A, yoloResult)
                    if A_placementOK:
                        self.placementOK['A'] = True
                        self.centerPointAToD = 0
                elif self.placementOK['A']:
                    D_placementOK = self.placementDetection.put_to_zone(Zone.D, yoloResult)
                    if D_placementOK and self.centerPointAToD > 0: #已正確修正(A區->D區)
                        self.waitCorrection['D'] = False
                        self.placementOK['A'] = False
                        self.placementOK['D'] = True
                        self.haveAlarm = False
                        return ["NO"], [numOfCurrentStep]

                centerPointInA = self.placementDetection.put_to_zone(Zone.A, yoloResult)
                centerPointInD = self.placementDetection.put_to_zone(Zone.D, yoloResult)
                if len(yoloResult["hand_PCB_coordinate"]) > 0 and not centerPointInA and not centerPointInD:
                    self.centerPointAToD += 1

            elif not self.placementOK["D"]:
                D_placementOK = self.placementDetection.put_to_zone(Zone.D, yoloResult)
                if D_placementOK:
                    self.placementOK["D"] = True
                    return ["NO"], [numOfCurrentStep]
                else: # 若還沒放到D區就先放到A區時，就判流程錯
                    A_placementOK = self.placementDetection.put_to_zone(Zone.A, yoloResult)
                    if A_placementOK:
                        isAnomalyStep = "YES"
                        self.waitCorrection['D'] = True
                        
            elif self.placementOK["D"] and not self.placementOK["A"]:
                A_placementOK = self.placementDetection.put_to_zone(Zone.A, yoloResult)
                if A_placementOK:
                    self.placementOK["A"] = True

        # 判斷有無回到第二步，B區->D區 (第三步補救)        
        elif self.processDetection.currentStep.number == 4:

            if self.waitCorrection['D'] or self.waitCorrection['A']:
                if self.processDetection.jigLabel.current == Label.type3:
                    self.processDetection.currentStep.number = 2
                    self.haveAlarm = False
                    return ["NO"], [self.processDetection.currentStep.number]
                else:
                    isAnomalyStep = "YES"
                    self.processEnd = True
            else:
                if not self.placementOK["C2"]:
                    C2_placementOK = self.placementDetection.put_to_zone(Zone.C, yoloResult)
                    if C2_placementOK:
                        self.placementOK["C2"] = True
                        self.processEnd = True
                        return ["NO"], [numOfCurrentStep]
            
            if self.haveAlarm and isAnomalyStep != "NONE":
                self.processEnd = True
                return ["YES"], [numOfCurrentStep]

            if isAnomalyStep != "YES":
                self.temp1 = True
                self.initialize_parameter()  
                # self.processEnd = True
                return ["NONE"], [-1]

        ######################################################### 用流程去判斷是否正確 #############################################################
        # 目前步驟正確
        if isAnomalyStep == "NO":

            if self.processDetection.is_first_step():
                pass

            if self.processDetection.currentStep.number == 1:
                list1 = []
                list2 = []
                if not self.placementOK["C2"] and self.temp1:
                    self.temp1 = False
                    list1.append("YES")
                    list2.append(4)
                    temp = copy.deepcopy(self.q)
                    save_video(datetime.now(), temp) 
                    self.q.clear()
                    self.haveAlarm = False
                if not self.placementOK["C1"]:
                    self.temp1 = False
                    isAnomalyStep = "YES"
                    list1.append("YES")
                    list2.append(1)

                    thread = Thread(target=self.__tool.play_sound())
                    thread.start()
                    self.haveAlarm = True
                    self.needRecord = True

                    return list1, list2
                else:
                    self.temp1 = False
                    list1.append("NO")
                    list2.append(1)
                    # return isAnomalyStep, numOfCurrentStep
                    return list1, list2
                

            if self.processDetection.currentStep.number == 2: # 交由PlacementDetection判斷
                pass
            
            if self.processDetection.currentStep.number == 3: # 流程到step 3.，但過程中面板沒有到D區和A區時，就判 step 2.B->D 錯
                
                if self.haveAlarm and isAnomalyStep != "NONE":
                    return ["YES"], [numOfCurrentStep]

                if self.waitCorrection['D']: # 代表有過A區、但D區都沒放面板
                    isAnomalyStep = "YES"
                elif not self.placementOK["D"]: # 代表A區、D區都沒放面板
                    isAnomalyStep = "YES"
                    numOfCurrentStep = numOfCurrentStep-1
                    self.waitCorrection['D'] = True
                else: # 代表D區有放面板
                    if self.placementOK["A"]:
                        self.waitCorrection['A'] = False
                        return [isAnomalyStep], [numOfCurrentStep]
                    else:
                        isAnomalyStep = "YES"
                        self.waitCorrection['A'] = True

            elif self.processDetection.currentStep.number == 4: # 交由PlacementDetection判斷
                pass

            else:
                pass
                # self.gui.show_currentStep_is_correct(numOfCurrentStep)
                # return isAnomalyStep, numOfCurrentStep

        # 目前步驟錯誤
        if isAnomalyStep == "YES":
            thread = Thread(target=self.__tool.play_sound())
            thread.start()
            self.haveAlarm = True
            self.needRecord = True
            return [isAnomalyStep], [numOfCurrentStep]

        if isAnomalyStep == 'NONE':
            return [isAnomalyStep], [-1]

    class __tool:
        @staticmethod
        def play_sound():
            pygame.mixer.init()
            pygame.mixer.music.load('warning_4th_step.mp3')
            pygame.mixer.music.play()

class Hands:

    def __init__(self, model, pixelThres, degree):
        """initialize parameter

        Args:
            model (torch): YOLOv5 Model
        """        
        self.model = model
        self.pixelThres = pixelThres
        self.degree = degree
        self.NGFlag = None 
        self.lastNGImg = None 

    
    def run(self, image):
        """Stream Hands Abnomal Detection

        Args:
            image (img): perspective image

        Returns:
            img: resultsImg
        """        

        streamImg = image.copy()
        resultsImg = None
        yoloResult = self.model.detect_hands(image)
        ### initial last NG image
        if self.NGFlag == None:
            self.lastNGImg = cv2.imread('config/idle.jpg')   
        ### last  NG Img resize
        if self.lastNGImg.shape != streamImg.shape:
            self.lastNGImg = cv2.resize(self.lastNGImg, (streamImg.shape[1], streamImg.shape[0]), interpolation=cv2.INTER_AREA)

        ### reload pixel config

        ### draw system time on image
        dateFormat = "%Y/%m/%d %H:%M:%S"
        dateText = datetime.now().strftime(dateFormat)
        cv2.putText(streamImg, dateText, (10, streamImg.shape[1] - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
        ### YOLO Predict PCB and Gloves
        if len(yoloResult['PCB'])>0 and len(yoloResult['PCB'])>0:
            streamImg, self.NGFlag, centerFlag = self.check_hands_touch(streamImg, yoloResult['PCB'], yoloResult['Gloves'], self.pixelThres, self.degree)
        else:
            self.NGFlag = False
            centerFlag = False
        # cv2.rectangle(streamImg, (yoloResult['PCB'][0] + pixelThres, yoloResult['PCB'][1] + pixelThres), (yoloResult['PCB'][2] - pixelThres, yoloResult['PCB'][3] - pixelThres), [0, 0, 255], 1, cv2.LINE_AA)  # no filled
        ### Record NG Image
        if self.NGFlag and centerFlag:
            dateFormat = "%Y/%m/%d %H:%M:%S"
            dateText = datetime.now().strftime(dateFormat)
            content = '{} Hands Alarm!'.format(dateText)
            ServiceConfig.write_config(content,"mainPage_console_config")
            self.lastNGImg = streamImg
            plot_fail_touch(streamImg, yoloResult['PCB'], self.pixelThres, color=None, line_thickness=3)
            save_frame(self.lastNGImg, dateText)

        self.NGFlag = False   # RESET 
        
        # Concatenate Stream & History Abnomal Image
        resultsImg = np.hstack((streamImg, self.lastNGImg))
        return resultsImg

    ### CV Judge Hands Touch Mask
    def check_hands_touch(self, image, PCBBoxes, GlovesBoxes, pixelThres, glovesDegree):
        """hands touch check function

        Args:
            image (img): Original BGR Image 
            PCBBoxes (list): PCB YOLO Bounding Box
            GlovesBoxes (list): Gloves YOLO Bounding Box
            pixelThres (int): Inner Pixels Values
            glovesDegree (float): detection range of gloves

        Returns:
            [img]: image
            [bool]: touchFlag
            [bool]: centerFlag
        """
        touchFlag = False
        centerFlag = False
        (imgH, imgW, _) = image.shape
        ### Mask of PCB、Gloves
        zeroMask = np.zeros((imgH, imgW), np.uint8)
        inPlateMask = np.zeros((imgH, imgW), np.uint8)
        PCBMask = np.zeros((imgH, imgW), np.uint8)
        glovesImg = np.zeros((imgH, imgW, 3), np.uint8)
        PCBMask[int(PCBBoxes[1]) + pixelThres:int(PCBBoxes[3]) - pixelThres, int(PCBBoxes[0]) + pixelThres:int(PCBBoxes[2])- pixelThres] = 255
        ### Mask of GlovesL、GlovesR
        lowerGloves = np.array([150, 150, 150])   # BGR
        upperGloves = np.array([255, 255, 255])   # BGR
        ### Paste to Gloves Mask
        for gloveBBox in GlovesBoxes:
            halfBBoxH = int((1-glovesDegree) * (gloveBBox[3] - gloveBBox[1]))
            # halfbBoxW = int((1-glovesDegree) * (gloveBBox[2] - gloveBBox[0]))
            glovesImg[int(gloveBBox[1]):int(gloveBBox[3] - halfBBoxH), int(gloveBBox[0]):int(gloveBBox[2])] = image[int(gloveBBox[1]):int(gloveBBox[3] - halfBBoxH), int(gloveBBox[0]):int(gloveBBox[2])]
        glovesMask = cv2.inRange(glovesImg, lowerGloves, upperGloves)
        kernel = np.ones((3, 3),np.uint8)
        glovesMask = cv2.morphologyEx(glovesMask, cv2.MORPH_OPEN, kernel)   # Open Operation

        ### Bitwise PCB&Gloves Mask
        inPlateMask = cv2.bitwise_and(PCBMask, glovesMask)
        inPlatePixels = np.sum(inPlateMask)

        ### Place the PCB Center Check
        # radius = 0.5 * pixelThres
        radius = 0.5 * 13
        midPCB = [0.5 * int(PCBBoxes[0] + PCBBoxes[2]), 0.5 * int(PCBBoxes[1] + PCBBoxes[3])]
        midImg = [0.5 * imgW - 1, 0.5 * imgH - 1]
        midDiff = np.array(midPCB) - np.array(midImg)
        midDistance = math.hypot(midDiff[0], midDiff[1])
        centerFlag = True if (midDistance <= radius) else False
        touchFlag = True if inPlatePixels else False

        ### Draw Gloves Mask on Image
        if touchFlag and centerFlag:
            kernel = np.ones((3, 3),np.uint8)
            inPlateMask = cv2.dilate(inPlateMask, kernel, iterations=1)
            backgroundMask = cv2.bitwise_not(inPlateMask)
            backgroundImg = cv2.bitwise_and(image, image, mask=backgroundMask)
            touchImg = cv2.merge([zeroMask, zeroMask, inPlateMask])
            resultImg = cv2.add(backgroundImg, touchImg)
            image = resultImg
            
        return image, touchFlag, centerFlag

