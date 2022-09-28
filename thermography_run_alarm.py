#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import sys
print("Python v" + sys.version)
import threading

import time
import pytz

import base64
import numpy as np
print(f'NumPy v{np.version.version}')

import json

import cv2
print("OpenCV V", cv2.__version__)

import imutils

from datetime import datetime, timezone
from dateutil.parser import parse


# In[ ]:


from influxdb_client import WritePrecision, InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS


# In[ ]:


id_table = ['0', '1', '2']
img_gap_size = (10, 320)
img_size = (256, 320)
img_text_time_pos = (30, 20)
img_text_temp_pos = (50, 250)
img_text_color = (0,0,255)
sensor_size = (80,64)


# In[ ]:


rois = {'0':[(13, 11), (49, 70)], '1':[(24,13), (58, 60)], '2':[(14,16), (58, 62)]}
#rois = {'0':[(13, 11), (24, 66)], '1':[(24,13), (58, 60)], '2':[(14,16), (58, 62)]}


# In[ ]:


# db_url='http://192.168.0.105:8086'
# db_token="2RXMyjVC3zQKwBS6RKG3rv6T485vc9HIJPGE4qd2O5y8rUccnJbbHxvNIc_FPxPV7dAKm0qle5coR-gpp-mDlA=="
#db_url='http://192.168.1.109:8086'
db_url='http://localhost:8086'
db_token="Dmg37145YsUKL_7iv2oplpXP4-0qySj2zvOkC-GAoYineBDbVHnP0VXwy9fr__3gozPJVO1RdhEZ96J-dN3Syw=="
db_org = "AUO"
db_bucket = 'auo'
db_bucket_store = 'auo'


# In[ ]:


thermal_img_data = {}
thermal_img_time = {}
thermal_img_time_last = {}
thermal_img_update = {}
temperature_max = {}
temperature_min = {}
hd_thread_img = []


# In[ ]:


db_client = InfluxDBClient(url=db_url, token=db_token, org=db_org)
query_api = db_client.query_api()
write_api = db_client.write_api(write_options=SYNCHRONOUS)


# In[ ]:


def img_query_get():
    img_data = {}
    img_time = {}
    fg_upgate = {}
        
    query = f'from(bucket: "{db_bucket}")'    '|> range(start: -80s)'     '|> filter(fn: (r) => r._measurement == "mqtt_consumer")'    '|> filter(fn: (r) => r.topic == "THERMALIMAGE")'     '|> filter(fn:(r) => r._field == "Image")'
    
    tables = query_api.query(query=query, org=db_org)
    
    for table in tables:
        idx = -1
        
        # 相同的 'idx'.
        for record in table.records:
            idx += 1
            dt1 = record.values['_time']
            if idx == 0:
                idx = 0
                last_tiem = dt1
                last_idx = idx
            elif dt1 > last_tiem:
                last_tiem  = dt1
                last_idx = idx
            
        if idx >= 0:
            ID = table.records[idx].values['idx']
            thermal_img_b64 = table.records[idx].values['_value']
            thermal_img_byte = base64.b64decode(thermal_img_b64)
            img_data[ID] = np.frombuffer(thermal_img_byte, dtype=np.uint16)
            img_time[ID] = last_tiem.astimezone(pytz.timezone('Asia/Taipei'))
            
            if (thermal_img_time_last.get(ID) == None) or (thermal_img_time_last[ID] < img_time[ID]):
                thermal_img_time_last[ID] = img_time[ID];
                fg_upgate[ID] = True
                print(ID, type(ID), img_time[ID])
                
            
    return img_data, img_time, fg_upgate


# In[ ]:


def image_normalize(u16Array, **kwargs):
    t_max = int((150 +273.15)*10) # 150
    t_min = int((5 +273.15)*10)  # 30
    
    image = np.asarray(u16Array, dtype=float)
    
    # mask.
    if "mask" in kwargs:
        make = kwargs["mask"]
        image = image * mask

    # skip_line = 5
    if "skip_line" in kwargs:
        skip_line = kwargs["skip_line"]
        #image = image[skip_line:sensor_size[1]-skip_line, skip_line:sensor_size[0]-skip_line]
        top = skip_line
        donw = sensor_size[0]-skip_line
        left = skip_line
        reght = sensor_size[1]-skip_line
        image[:left, :] = np.nan
        image[:, :top] = np.nan
        image[reght:, :] = np.nan
        image[:, donw:] = np.nan
    
    img_max = int(np.nanmax(image)) # nanmax, amax
    img_min = int(np.nanmin(image)) # nanmin, amin
    image[np.isnan(image)] = 0
    
    print(f'image min: {k2c(img_min)}, max: {k2c(img_max)}')
    
    image = np.int32(image)

    image[image > t_max] = t_max
    image[image < t_min] = t_min
    image_norm = np.uint8((image - t_min) *255 / (t_max-t_min)) # 2700~4500
    print(f'norm min: {k2c(t_min)}({t_min}), max: {k2c(t_max)}({t_max})');
    
    
    return image_norm, img_max


# In[ ]:


def InitCanvas(width, height, color=(255, 255, 255)):
    canvas = np.ones((height, width, 3), dtype="uint8")
    canvas[:] = color
    return canvas


# In[ ]:


def thermal_data2img(data, dt):
    data.shape = (sensor_size[1], sensor_size[0])
    mask = oval_mask_generate(data.shape, 15)
    #image_norm, t_max, = image_normalize(data, mask=mask)
    image_norm, t_max, = image_normalize(data, skip_line=5)
    img = cv2.applyColorMap(image_norm, cv2.COLORMAP_JET)
    #img = imutils.rotate_bound(img, 90)
    img = np.rot90(img,3)
    ## INTER_AREA, INTER_CUBIC.
    img = cv2.resize(img, img_size, interpolation = cv2.INTER_AREA)
    text = dt.strftime("%Y-%m-%d %H:%M:%S")
    # FONT_HERSHEY_SIMPLEX, 
    cv2.putText(img, text, img_text_time_pos, cv2.FONT_HERSHEY_DUPLEX, 0.6, img_text_color, 1)
    text = "T_max:" + str((t_max-2732)/10)
    cv2.putText(img, text, img_text_temp_pos, cv2.FONT_HERSHEY_DUPLEX, 0.6, img_text_color, 1)

    return img


# In[ ]:


def image_data_merge(img_data, img_time):
    img_gap = InitCanvas(img_gap_size[0], img_gap_size[1])
    img = img_gap
    for id in id_table:
        if id in img_data:
            data = img_data[id]
            dt = img_time[id]
            img_temp = thermal_data2img(data, dt)
        else:
            print("Not", id, "thermal image")
            img_temp = InitCanvas(img_size[0], img_size[1])
        print("img:", img.shape, "new:", img_temp.shape)
        img = np.hstack((img, img_temp))
        print("img:", img.shape, "gap:", img_gap.shape)
        img = np.hstack((img, img_gap))
    
    return img


# In[ ]:


def save_jpg(img):
    fname = './thermography.jpg'
    cv2.imwrite(fname, img)
    #print('Saving image ', fname)


# In[ ]:


def img_thread():
    global thermal_img_update, thermal_img_data, thermal_img_time
    fgexit = 0
    
    hd_thread = threading.currentThread()
    
    while (not fgexit) and (getattr(hd_thread, "do_run", True)):
        try:
            if thermal_img_update != {}:
                img = image_data_merge(thermal_img_data, thermal_img_time)

                save_jpg(img)

                cv2.imshow('Thermography', img)
                thermal_img_update = {}

            key = cv2.waitKey(200)& 0xFF
            # ESC: 0x1B, ctrl + q: 0x11, q: ord('q')    
            if key == 0x11:
                fgexit = 1
                print("Key:",  key)
            elif key != 0xFF:
                print("Key:",  key)
                    
        except Exception as e:
            print(e)
        
    cv2.destroyAllWindows() #close the image window


# In[ ]:


def oval_mask_generate(size, rm):
    print(size)
    mask = np.ones(size)
    r = np.sqrt(np.square(mask.shape[0]/2) + np.square(mask.shape[1]/2))
    r = int(r) - rm

    r_square = np.square(r)
    for y in range(mask.shape[0]//2, 0, -1):
        w = np.sqrt(r_square - np.square(y))
        for w_cut in range(0, mask.shape[1]//2 - int(w)):
            top = mask.shape[0]//2 - y
            donw = mask.shape[0]//2 + y -1
            left = w_cut
            reght = mask.shape[1]-1 - w_cut
            mask[top, left] = np.nan
            mask[top, reght] = np.nan
            mask[donw, left] = np.nan
            mask[donw, reght] = np.nan
    return mask


# In[ ]:


# kelvin to celsius
def k2c(kelvin):
    celsius = (int(kelvin)-2731.5)/10
    return celsius


# In[ ]:


def calcROI2M(u16nparray, roi):
    u16nparray.shape = (sensor_size[1], sensor_size[0])
    u16nparray = np.rot90(u16nparray,3)
    
    roi_array = u16nparray[roi[0][1]:roi[1][1],roi[0][0]:roi[1][0]]
    
    
    val_max = int(np.nanmax(roi_array))# nanmax, amax
    val_min = int(np.nanmin(roi_array)) # nanmin, amin
    print('max:', val_max, type(val_max), ', min:', val_min, type(val_min))
                                                                 
    return val_max, val_min


# In[ ]:


def DBInsert(time, idx, val_max, val_min, estimate_diff, rst_diff):

    #p1 = Point("my_measurement")\
    p1 = Point("temp_cal_3")    .tag("cabinet", "Cabinet_1")    .tag("topic", "THERMALIMAGE")    .tag("idx", idx)    .field("temperature_max", val_max)    .field("temperature_min", val_min)    .field("temperature_diff", val_max-val_min)    .field("temperature_estimate_diff", estimate_diff)    .field("temperature_rst_diff", rst_diff)    .time(time)
    
    write_api.write(org=db_org, bucket=db_bucket_store, record=[p1])


# In[ ]:


def AlarmProc(img_data, img_time, img_update):
    if img_update != {}:
        for id in thermal_img_update:
            print('id:', id, type(id), 'Update:', thermal_img_update[id])
            if thermal_img_update[id] == True:
                val_max, val_min = calcROI2M(img_data[id], rois[id])
                val_max_c = k2c(val_max)
                val_min_c = k2c(val_min)

                temperature_max[id] = val_max_c
                temperature_min[id] = val_min_c

        for id in thermal_img_update:
            print('id:', id, type(id))
            #print('temperature_max[]', temperature_max[id], type(temperature_max[id]))
            # 同一顆, 最高溫與最低溫的溫度差, 與預估的溫度差.
            diff_estimate =-13.37837809+0.64235575*temperature_max[id]
            diff = abs(temperature_max[id] - temperature_min[id] )

            # 不同顆相互間的最大差異.
            rst_diff = 0
            for id_diff in temperature_max:
                temp = abs(temperature_max[id] - temperature_max[id_diff])
                print('id_diff:', id_diff, type(id_diff), temp)
                if rst_diff < temp:
                    rst_diff = temp

            print(f'ID: {id}, T_max: {val_max_c}, estimate: {diff_estimate}, diff: {diff}, rst_diff: {rst_diff}')
            DBInsert(img_time[id], id, val_max_c, val_min_c, diff, rst_diff)


# In[ ]:





# # Main

# In[ ]:


fgexit = False

hd_thread_img = threading.Thread(target = img_thread)
hd_thread_img.start()

while not fgexit:
    try:
        thermal_img_data, thermal_img_time, thermal_img_update = img_query_get()        
        AlarmProc(thermal_img_data, thermal_img_time, thermal_img_update)
        
        if hd_thread_img.is_alive():
            time.sleep(6)
        else:
            fgexit = True

    except KeyboardInterrupt:
        fgexit = True
    except Exception as e:
        print(e)

hd_thread_img.do_run = False
hd_thread_img.join()
print('Done')
