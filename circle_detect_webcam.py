import cv2
import time
import os
import numpy as np

fileDir= r'C:\Users\WYLee\Desktop\circle\raw_data_CCD\tube89_B'
fileName = 'tube89_53_0.avi'
filePath = os.path.join(fileDir, fileName)
now_time = time.strftime("%m%d%Y%H%M%S", time.localtime())

cap = cv2.VideoCapture(filePath)
# cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)  
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080) 

# fourcc = cv2.VideoWriter_fourcc(*'XVID')
fourcc = cv2.VideoWriter_fourcc('M', 'J', 'P', 'G')
out = cv2.VideoWriter(now_time+'.avi', fourcc, 30.0, (1920, 1080))

inner_r = 0
outer_r = 0
r_count = 0
r_list = []
while(True):
    ret, frame = cap.read()
    image = frame.copy()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.medianBlur(gray, 5)
    # canny = cv2.Canny(blur, 20, 50)
    # cv2.imshow('canny',canny)

    try:
        # minDist:兩個圓之間圓心的最小距離
        # param2越小，就越可以檢測到更多根本不存在的圓，而它越大的話，能通過檢測的圓就更加接近完美的圓形了

        # black
        circles= cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, 1, minDist=100, param1=60, param2=80, minRadius=200, maxRadius=500)
        # circles= cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, 1, minDist=60, param1=40, param2=85, minRadius=200, maxRadius=450)
        # gray
        # circles= cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, 1, minDist=60, param1=100, param2=80, minRadius=200, maxRadius=500)
        # circles= cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, 1, minDist=80, param1=70, param2=85, minRadius=200, maxRadius=400)
        # orange
        # circles= cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, 1, minDist=60, param1=60, param2=80, minRadius=250, maxRadius=500)
        # circles= cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, 1, minDist=120, param1=100, param2=80, minRadius=250, maxRadius=500)

        for circle in circles[0]:
            #座標行列
            x = int(circle[0])
            y = int(circle[1])

            #半徑
            r = int(circle[2])
            print(r)

            #在原圖用指定顏色標記出圓的位置
            cv2.circle(frame,(x,y),r,(0,0,255),1)
            if r and (r > 0):
                r_count += 1
                r_list.append(r)
                if  r_count == 10:
                    r_count = 0

                    # black, gray
                    inner_r = max( [x for x in r_list if x <= 300] )  
                    outer_r = max( [x for x in r_list if x > 300 and x < 350] )

                    # black, gray 斜
                    # inner_r = max( [x for x in r_list if x <= 260] )  
                    # outer_r = max( [x for x in r_list if x > 260 and x < 300] )

                    # orange
                    # inner_r = max( [x for x in r_list if x <= 350] )  
                    # outer_r = max( [x for x in r_list if x > 350 and x < 380] )

                    # orange 斜
                    # inner_r = max( [x for x in r_list if x <= 300] )  
                    # outer_r = max( [x for x in r_list if x > 300 and x < 350] )


                    cv2.circle(image, (x, y), inner_r, (0,0,255), 2)
                    cv2.circle(image, (x, y), outer_r, (0,255,0), 2)
                    cv2.putText(image, "inner:" + str(inner_r), (0, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 255), 1, cv2.LINE_AA)  
                    cv2.putText(image, "outer:" + str(outer_r), (0, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 1, cv2.LINE_AA) 
                    cv2.putText(image, "Tube Width:" + str(float((outer_r - inner_r))), (0, 120), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 1, cv2.LINE_AA)
                    # cv2.imshow('image', image)
                    cv2.imwrite('result.jpg', image)
                    r_list  = []
    except:
        pass    
    
    cv2.putText(frame, "inner:" + str(inner_r), (0, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 255), 1, cv2.LINE_AA)  
    cv2.putText(frame, "outer:" + str(outer_r), (0, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 1, cv2.LINE_AA) 
    cv2.putText(frame, "Tube Width:" + str(float((outer_r - inner_r))), (0, 120), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 1, cv2.LINE_AA)
    cv2.imshow('Hough', frame)
    out.write(frame)


    k = cv2.waitKey(1) & 0xFF
    # 若按下 q 鍵則離開迴圈
    if  k == ord('s'):
        t = time.strftime("%m%d%Y%H%M%S", time.localtime())
        cv2.imwrite( os.path.join(os.getcwd(), t+".jpg"), frame)
    elif  k == ord('q'):
        break

# 釋放攝影機
cap.release()
out.release()

# 關閉所有 OpenCV 視窗
cv2.destroyAllWindows()