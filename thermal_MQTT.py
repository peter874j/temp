#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import socket, sys
import time
import numpy as np
from threading import Thread
import numpy
import select

ADDRESS = ('0.0.0.0', 3001)

g_socket_server = None  
g_conn_pool = []   

F_rawData  = [0,0,0]
final_data = []
checklist_accept = [0,0,0]
checklist_data = [0,0,0]
ask_check=[0,0,0]


# In[ ]:


import cv2
def image_normalize(u16Array, mask):
    global img
    
    skip_line = 5
    image = np.asarray(u16Array, dtype=np.int)
    print('in:', len(u16Array))

    line = np.int(len(image)/80)
    print('line:', line)
    image.shape = (line, 80)
    image = image * mask
    image = image[skip_line:line-skip_line, skip_line:80-skip_line]
    
    img_max = np.int(np.nanmax(image))# nanmax, amax
    img_min = np.int(np.nanmin(image)) # nanmin, amin
    print('max:', img_max, type(img_max))
    print('min:', img_min, type(img_min))
    
    image_norm = np.uint8((image - img_min) *255 / (img_max-img_min))
    
    print('max:', np.amax(image_norm), ', min:',np.amin(image_norm), ',', type(image_norm[0]))
    
    return image_norm


# In[ ]:


def print_img(idx):
    mask = np.ones((64,80))
    image_norm = image_normalize(F_rawData[idx], mask)
    img = cv2.applyColorMap(image_norm, cv2.COLORMAP_JET)
    # INTER_AREA, INTER_CUBIC.
    img = cv2.resize(img, (320, 256), interpolation = cv2.INTER_AREA)
    cv2.imshow('Output', img)
    cv2.waitKey(1) #wait for any key
#    cv2.destroyAllWindows() #close the image window


# In[ ]:


from enum import Enum
class accept(Enum):
    first=1
    second=2
    third=3


# In[ ]:


def init():    
    global g_socket_server
    global g_conn_pool
    global F_rawData
    
    g_conn_pool =[0] * 3
    F_rawData =[0]*3
    try:
        g_socket_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except socket.error as msg:
        #sys.stderr.write("[ERROR] %s\n" % msg[1])
        #sys.exit(1)
        print("Bind failed. Error Code :",str(msg[0]),"Message",msg[1])  
        sys.exit()
    g_socket_server.bind(ADDRESS)
    g_socket_server.listen(5)  
    print("Waiting for client request.....")
    thread = Thread(target=accept_client)    
    thread.setDaemon(True)
    thread.start()


# In[ ]:


def accept_client():  
    
    while True:        
        client, _ = g_socket_server.accept()
        #心跳
        #client.setsockopt(socket.SOL_SOCKET,socket.SO_KEEPALIVE,True)       
        #client.ioctl(socket.SIO_KEEPALIVE_VALS,(1,6*1000,30*1000))
        #g_conn_pool.append(client)
        data1 = client.recv(1024)
        print(data1)
        data=data1.decode(encoding='utf8')          
        sStr1='first'
        sStr2='second'
        sStr3='third'
        if data in sStr1:            
            g_conn_pool[0]=client
            checklist_accept[0]=1
            print('first')            
            idx = 0
        elif data in sStr2:
            g_conn_pool[1]=client 
            checklist_accept[1]=2
            print('second')  
            idx = 1
        elif data in sStr3:
            g_conn_pool[2]=client
            checklist_accept[2]=3
            print('third')
            idx = 2        
        else:
            print('is not correct accept')
            break        
        thread = Thread(target=message_handle, args=(client,idx))
        print('test1:',thread)
        print('test1_1:',idx)
        thread.setDaemon(True)
        thread.start()
        
                


# In[ ]:


def message_handle(client,idx):
    global F_rawData
    global checklist_data
    global ask_check
    
    client.setsockopt(socket.SOL_SOCKET,socket.SO_KEEPALIVE,True)
    client.ioctl(socket.SIO_KEEPALIVE_VALS,(1, 4*1000, 100))
    client.sendall("ok!".encode(encoding='utf8'))      
    while True:
        try:
            client.settimeout(1)
            MSGLEN=10240            
            datas = []
            bytes_recd = 0
            
            while bytes_recd < MSGLEN:                
                data = client.recv(MSGLEN - bytes_recd)
                #print("bytes_recd:",bytes_recd)
                #print("data len:" ,len(data))
                if len(data) == 0:
                    print('test')
                    close_client(client,idx)            
                    break
                datas.extend(data)
                bytes_recd = bytes_recd + len(data)
            if ask_check[idx]==1:  
                #print("final data len:" ,len(datas))
                #print("final data type",type(datas))
                #print("final data",datas)
                data_final=datas
                #time.sleep(5)
                if len(datas) == 10240:
                    aaa = np.array(datas,dtype=np.uint8)
                    data_finall = np.frombuffer(aaa, dtype=np.uint16)
                    F_rawData[idx]=data_finall
                    checklist_data[idx]= "collect_data"            
                    print("client from",idx,"message:", F_rawData[idx])                      
                    print("checklist_data:", checklist_data[idx])
                    print_img(idx)
                    ask_check[idx]==0
                elif len(datas) != 10240:    
                    checklist_data[idx]="client message is worng"            
                    print("client message is worng")
                    print("checklist_data:", checklist_data[idx],"from idx:",idx)
                    #time.sleep(5)
                    print("ask data again")
                    message='a'
                    ask_data(idx,message) 
            else :
                print("didn't ask")
                pass
        except socket.timeout:
            #print("socket time out")
            checklist_data[idx]="time_out"
            pass
        except RuntimeError:
            print("socket connection broken")
        except socket.error as msg:
            print("socket.error:",msg)
            close_client(client,idx)
            break
        except:
            print("other error",sys.exc_info()[0])
            close_client(client,idx)
            break


# In[ ]:


def close_client(client,idx):
    client.close()
    g_conn_pool[idx]=0
    checklist_accept[idx]=0
    checklist_data[idx]="disconnect"
    print("disconnect")
    


# In[ ]:


def ask_data(index,message):    
    try:
        g_conn_pool[int(index)].sendall(message.encode(encoding='utf8')) 
    except socket.error:#Send failed                
        print ('Send failed')


# In[ ]:


def askall_data(): 
    global ask_pool
    global g_conn_pool
    global checklist_data
    global checklist_accept
    
    if checklist_accept[0]==accept.first.value:
        ask_check[0]=1
        checklist_data[0]=0
        message = 'a'
        try:
            g_conn_pool[0].sendall(message.encode(encoding='utf8')) 
        except socket.error:#Send failed 
            checklist_data[0]="Send failed"
            print ('Send failed')
        except:
            print("other error",sys.exc_info()[0])   
    else:
        print("didn't accept: first")
    if checklist_accept[1]==accept.second.value:
        ask_check[1]=1
        checklist_data[1]=0
        message = 'a'
        try:
            g_conn_pool[1].sendall(message.encode(encoding='utf8')) 
        except socket.error:#Send failed 
            checklist_data[1]="Send failed"
            print ('Send failed')
        except:
            print("other error",sys.exc_info()[0])    
    else:
        print("didn't accept: second")
    if checklist_accept[2]==accept.third.value:
        ask_check[2]=1
        checklist_data[2]=0
        message = 'a'
        try:
            g_conn_pool[2].sendall(message.encode(encoding='utf8')) 
        except socket.error:#Send failed   
            checklist_data[2]="Send failed"
            print ('Send failed')            
        except:
            print("other error",sys.exc_info()[0])
    else:
        print("didn't accept: third")          
        
        


# In[ ]:


if __name__ == '__main__':
    init()
    
    
   
    


# In[ ]:


askall_data()#問全部的data
print('askall_data') 
#每一顆的data
first_data=F_rawData[0]
print('first data',first_data) 
second_data=F_rawData[1]
print('second data',second_data) 
third_data=F_rawData[2]
print('third data',third_data) 


# In[ ]:


import base64
import numpy as np
# t = np.arange(25, dtype=np.float64)
# t
# s = base64.b64encode(t).decode("Utf-8")
# s
# r = base64.b64encode(s)
# q = np.frombuffer(r, dtype=np.float64)
# q


# In[ ]:


import paho.mqtt.client as mqtt
import json
import time
from datetime import datetime
from threading import Timer
MQTTTopicServerIP = "140.124.201.88"
MQTTTopicServerPort = 1883 #port
MQTTTopicName = "THERMALIMAGE" #TOPIC name

thermal_num=3

def THERMALIMAGE(inc):
    flag=[0]*thermal_num
    x=thermal_num
    print(x)
    while True:
        askall_data()
        for idx in range (thermal_num):
            if flag[idx]==0:
                if checklist_data[idx]=="collect_data":
                    s[idx] = base64.b64encode(F_rawData[idx]).decode("Utf-8")
                    payload = {"Image":s[idx],"idx":idx,"time":datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                    print ("payload=", payload)
                    qttc = mqtt.Client("python_pub")
                    mqttc.connect(MQTTTopicServerIP, MQTTTopicServerPort)
                    mqttc.publish(MQTTTopicName, json.dumps(payload),qos=2)
                    flag[idx]=1           
        for i in range (thermal_num):
            if flag[i]==1:
                flag[i]+=1
                x-=1
                print(x)
        if x==0:
            break          
    t = Timer(inc, THERMALIMAGE, (inc,))
    t.start()
THERMALIMAGE(30)

