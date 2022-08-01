import cv2 
import numpy as np
import os
import threading
import time
from datetime import datetime
from dataclasses import dataclass


@dataclass
class ROIBox:
    x: int
    y: int
    w: int
    h: int

class Point:
    x = 0
    y = 0
    r = 0

    def __init__(self, x=0, y=0, r=0):
        self.x = x
        self.y = y
        self.r = r

class Line:
    def __init__(self, p1, p2):
        self.p1 = p1
        self.p2 = p2
        self.m = 0

class Camera:
    def __init__(self,fps=30, video_source=0):
        self.fps = fps
        self.isrunning = True
        self.status = False
        self.cap = cv2.VideoCapture(video_source)
        self.source = video_source
        self.frame = None

    def run(self):
        self.thread = threading.Thread(target=self.update, args=([self.cap]), daemon=True)
        self.thread.start()

    def update(self, cap):
        n = 0
        while cap.isOpened() and self.isrunning:
            n += 1
            cap.grab()
            if n == 1:  # read every 4th frame
                (self.status, frame) = cap.retrieve()  
                if self.status:
                    self.frame = frame
                       
                n = 0
            ### run-time stream don't need to sleep
            if type(self.source[0]) != type(0):
                time.sleep(0.05)

    def stop(self):
        self.isrunning = False

    def get_frame(self):
        ### Camera有讀到影像
        if self.status:
            return cv2.resize(self.frame, (1920, 1080))
        ### Camera讀不到影像，讀預設not_found影像
        else:
            print("not found input image")

def hough_circle(grayImg, minRadius=5, maxRadius=13):

    circles = cv2.HoughCircles(grayImg, cv2.HOUGH_GRADIENT, 1, 10, param1=30, param2=20, minRadius=minRadius, maxRadius=maxRadius)
    circlesPoints = []
    # print(circles)   #輸出返回值，方便檢視型別
    # print(len(circles[0]))   # 輸出檢測到圓的個數
    # 根據檢測到圓的資訊，畫出每一個圓
    if circles is not None:
        for circle in circles[0]:
            # 圓中心座標
            x = int(circle[0])
            y = int(circle[1])
            # 半徑
            r = int(circle[2])
            #在原圖用指定顏色標記出圓的位置
            circlesPoints.append(Point((x, y, r)))
            # print((x, y, r))
            grayImg = cv2.circle(grayImg, (x, y), r, (0, 0, 0) ,-1)
    return grayImg, circlesPoints

def get_backlight_ROI(thrImg):
    contours, hierarchy = cv2.findContours(thrImg, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    width = 0
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)  # 计算点集最外面的矩形边界
        if w > width:
            width = w  
            backlightROI = ROIBox(x, y, w, h)
    return backlightROI

def get_board_ROI(lightInvImg):
    contours, hierarchy = cv2.findContours(lightInvImg, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    area = 0
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)  # 计算点集最外面的矩形边界
        # cv2.rectangle(lightInvImg, (x, y), (x+w, y+h), (125, 125, 125), 2)
        if w*h > area:
            area = w*h  
            boardROI = ROIBox(x, y, w, h)
        # # 找面积最小的矩形
        # rect = cv2.minAreaRect(c)
        # # 得到最小矩形的坐标
        # box = cv2.boxPoints(rect)
        # # 标准化坐标到整数
        # box = np.int0(box)
        # # 画出边界
        # cv2.drawContours(img, [box], 0, (125, 125, 125), 3)
    # cv2.imshow("lightInvImg", lightInvImg)
    # cv2.waitKey(0)
    return boardROI

def get_broken_ROI(brokenImg):
    contours, hierarchy = cv2.findContours(brokenImg, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    area = 0
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)  # 计算点集最外面的矩形边界
        if w * h > area:
            area = w*h  
            brokenROI = ROIBox(x, y, w, h)
    return brokenROI

def get_line_para(line):
    a = line.p1.y - line.p2.y
    b = line.p2.x - line.p1.x
    c = line.p1.x * line.p2.y - line.p2.x * line.p1.y 
    return a, b ,-c

def get_cross_point(l1, l2):
    a1, b1, c1 = get_line_para(l1)
    a2, b2, c2 = get_line_para(l2)
    diff = a1 * b2 - b1 * a2
    xDiff = c1 * b2 - b1 * c2
    yDiff = a1 * c2 - c1 * a2
    ### 兩線平行
    if diff == 0:
        return None
    crossPoint = Point()
    crossPoint.x = xDiff*1.0 /diff
    crossPoint.y = yDiff*1.0 /diff
    print(crossPoint.x, crossPoint.y)
    return crossPoint

def fill_circle_hole(grayImg):
    filledImg, circlesPoints = hough_circle(grayImg)
    ### 影像開運算
    kernel = np.ones((5, 5), np.uint8)
    filledImg = cv2.morphologyEx(filledImg, cv2.MORPH_OPEN, kernel)
    # cv2.imshow('filledImg', filledImg)
    # cv2.waitKey(0)
    return filledImg

def get_hough_line(grayImg):
    kernelSize = (5, 5)
    grayImg = cv2.GaussianBlur(grayImg, kernelSize, 0)
    edges = cv2.Canny(grayImg, 50, 200)
    # cv2.imshow("edges", edges) 
    # cv2.waitKey(0)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, 30, minLineLength=20, maxLineGap=60)
    vLines = []
    hLines = []
    lines1 = lines[:,0,:]#提取為二維
    for x1, y1, x2, y2 in lines1[:]: 
        m = abs((y2-y1)/(x2-x1+0.001))
        # print(x1, y1, x2, y2)
        # print(m)
        # cv2.line(grayImg, (x1, y1), (x2, y2), (80, 80, 80), 2)

        # find vertical line, 點順序依y排序
        if m > 30:
            if y1 < y2:   # y值小為p1
                p1 = Point(x1, y1)
                p2 = Point(x2, y2)
            else:
                p1 = Point(x2, y2)
                p2 = Point(x1, y1)
            houghLine = [Line(p1, p2), m, abs(y2-y1)]
            vLines.append(houghLine)
            # vLine = Line(p1, p2)
        # find horizontal line, 點順序依x排序
        elif m < 0.5 and y2 < 30:
            p1 = Point(x1, y1)
            p2 = Point(x2, y2)
            houghLine = [Line(p1, p2), m, abs(x2-x1)]
            hLines.append(houghLine)
            # hLine = Line(p1, p2)
        # cv2.imshow("grayImg", grayImg) 
        # cv2.waitKey(0)
    # sort由小到大排序
    vLines.sort(key = lambda s: s[2])   # 垂直線依最長線篩選   
    vLines = vLines[-1]    
    hLines.sort(key = lambda s: s[1])   # 水平線依最小斜率篩選 
    hLines = hLines[0]
    hLine = hLines[0]
    # print(hLine.p1.x, hLine.p1.y, hLine.p2.x, hLine.p2.y)
    vLine = vLines[0]
    # print(vLine.p1.x, vLine.p1.y, vLine.p2.x, vLine.p2.y)
    return vLine, hLine

def get_broken_Info(rawImg, brokenImg, defectROI):
    brokenROI = get_broken_ROI(brokenImg)
    defectROI.w = brokenROI.w
    defectROI.h = brokenROI.h
    brokenImg = brokenImg[brokenROI.y:brokenROI.y+brokenROI.h, brokenROI.x:brokenROI.x+brokenROI.w]
    (BImg, GImg, RImg) = cv2.split(rawImg) # 3 channel
    BImg[defectROI.y:defectROI.y+defectROI.h, defectROI.x:defectROI.x+defectROI.w] = 0
    GImg[defectROI.y:defectROI.y+defectROI.h, defectROI.x:defectROI.x+defectROI.w] = 0
    RImg[defectROI.y:defectROI.y+defectROI.h, defectROI.x:defectROI.x+defectROI.w] = brokenImg
    mergeImg = cv2.merge([BImg, GImg, RImg])
    brokenArea = np.sum(brokenImg==255)   # 破片面積
    text = f"Broken Area = {brokenArea} pixels" 
    cv2.putText(mergeImg, text, (defectROI.x, defectROI.y - 5), 0, 0.6, (0, 0, 255), thickness=1, lineType=cv2.LINE_AA)
    # print(brokenArea)   
    return mergeImg, brokenArea

def detect_broken_board(img):
    rawImg = img.copy()
    ### otsu threshold
    grayImg = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ret, thrRawImg = cv2.threshold(grayImg, 230, 255, cv2.THRESH_BINARY)
    # cv2.imwrite("1_otsuImg.jpg", thrRawImg)   
    ### denoise (opening operation)
    # kernel = np.ones((11, 11), np.uint8)
    # thrRawImg = cv2.morphologyEx(thrRawImg, cv2.MORPH_OPEN, kernel)
    # cv2.imwrite("1-1_openedImg.jpg", thrRawImg)  
    ### find backlight ROI
    backlightROI = get_backlight_ROI(thrRawImg)
    backlightImg = thrRawImg[backlightROI.y:backlightROI.y+backlightROI.h, backlightROI.x:backlightROI.x+backlightROI.w]
    # cv2.imwrite("2_backlightImg.jpg", backlightImg)
    ### find board ROI
    lightInvImg = cv2.bitwise_not(backlightImg)
    boardROI = get_board_ROI(lightInvImg)
    ybias = backlightROI.y + boardROI.y - 1 
    xbias = backlightROI.x + boardROI.x - 1
    boardImg = rawImg[ybias:backlightROI.y+boardROI.y+boardROI.h, xbias:backlightROI.x+boardROI.x+boardROI.w]
    # cv2.imwrite("3_boardImg.jpg", boardImg)
    ### find defect ROI
    ### denoise (opening operation)
    kernel = np.ones((5, 5), np.uint8)
    boardImg = cv2.morphologyEx(boardImg, cv2.MORPH_OPEN, kernel)
    ### houghline transform
    boardGrayImg = cv2.cvtColor(boardImg, cv2.COLOR_BGR2GRAY)
    boardGrayImg = fill_circle_hole(boardGrayImg)
    vLine, hLine = get_hough_line(boardGrayImg)
    crossPoint = get_cross_point(vLine, hLine)
    topPoint = Point(int(crossPoint.x), int(crossPoint.y))
    bottomPoint = Point(int(hLine.p1.x), int(vLine.p1.y))
    defectImg = boardGrayImg[topPoint.y:bottomPoint.y, topPoint.x:bottomPoint.x]
    # cv2.imwrite("4_defectImg.jpg", defectImg)
    defectROI = ROIBox(topPoint.x + xbias, topPoint.y + ybias, bottomPoint.x - topPoint.x, bottomPoint.y - topPoint.y)
    resultImg, brokenArea = get_broken_Info(rawImg, defectImg, defectROI)
    return resultImg, brokenArea

if __name__ == '__main__':
    
    ### init parameter
    saveFolder = r"./output/NG"
    ### run-time inference
    camSource = 0
    dateFormat = "%Y%m%d%H%M%S"
    nowTime = datetime.now()
    dateText = nowTime.strftime(dateFormat)
    camInstance = Camera(video_source=camSource)
    camInstance.run() 
    if cv2.waitKey(1) & 0xFF == ord('q'):
        print("broken detect start...") 
        frame = camInstance.get_frame()
        resultImg, brokenArea = detect_broken_board(frame)
        print(f"broken area is {brokenArea} pixels...")
        cv2.imwrite(os.path.join(saveFolder, dateText+".jpg"), resultImg)
        cv2.imshow("resultImg", resultImg)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    
    '''
    ### offline read
    imgFolder = r"./data/NG_2"
    for root, dirs, files in os.walk(imgFolder):
        for file in files:
            img = cv2.imread(os.path.join(root, file), 1)
            resultImg, brokenArea = detect_broken_board(img)
            print(file)
            cv2.imwrite(os.path.join(saveFolder, file), resultImg)
            cv2.imshow("resultImg", resultImg)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
    '''