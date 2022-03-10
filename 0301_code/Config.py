import cv2
import datetime
from PIL import Image
import io
import configparser
from AIModule.ObjectUtils import BBox

class ConfigType:
	action = "action_config"
	hand = "hand_config"
	console = "console_config"
	mainPage_console = "mainPage_console_config"

class ServiceConfig:
	@staticmethod
	def write_config(data, type):
		# 處理hand、motion txt
		if isinstance(data, list):
			with open('config/{}.txt'.format(type), 'w') as f:
				f.write(('\n').join(data)) 
		else:
			# 處理console txt
			with open('config/{}.txt'.format(type), 'a') as f:
				f.write(data+'\n') 

	#動作流程座標框
	@staticmethod
	def get_bbox_config():
		result = []
		with open('config/{}.txt'.format(ConfigType.action),'r') as f:
			for line in f.readlines():
				content = line.split(" ")
				result.append(BBox.get_from_list(content[0], int(content[1]), int(content[2]), int(content[3]), int(content[4])))
			return result

    #透視變換四個點
	@staticmethod
	def get_4_coordinate():
		result = []
		with open('config/{}.txt'.format(ConfigType.hand), 'r') as f:
			for line in f.readlines():
				temp = line.split(" ")
				result.append([int(temp[0]), int(temp[1])])
			return result

	#獲得console內容
	@staticmethod
	def get_console_config(type):
		with open('config/{}.txt'.format(type), 'r') as f:
			result = ''
			contents = f.readlines()       #讀取全部行
			for content in contents:       #顯示一行	
				EventDays = datetime.datetime.strptime(content.split(' ')[0], '%Y/%m/%d')	
				ReserveDays = datetime.datetime.today().date() + datetime.timedelta(days = -0)
				if EventDays.date() >= ReserveDays:
					result += content
			return result

class Frame:

	BBoxInfo = ServiceConfig.get_bbox_config() 
	roiPts = ServiceConfig.get_4_coordinate() 

	@staticmethod
	def initialize_label():
		Frame.BBoxInfo = ServiceConfig.get_bbox_config() 
		Frame.roiPts = ServiceConfig.get_4_coordinate() 

	@staticmethod
	def draw_rectangle_in_zone(frame):
		for BBox in Frame.BBoxInfo:
			cv2.rectangle(frame, (BBox.startPoint.x, BBox.startPoint.y), (BBox.endPoint.x, BBox.endPoint.y), (255, 0, 0), 3)
			cv2.putText(frame, BBox.zoneName, (BBox.startPoint.x, BBox.startPoint.y), cv2.FONT_HERSHEY_DUPLEX, 2, (0, 255, 255), 3, cv2.LINE_AA)

	@staticmethod
	def transform_virtual_file(frame):
		frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
		frame = Image.fromarray(frame.astype('uint8'))
		file_object = io.BytesIO()
		frame.save(file_object, 'PNG')
		file_object.seek(0)
		return file_object

	@staticmethod
	def encode(frame):
		frame = cv2.imencode('.png', frame)[1].tobytes()
		frame = (b'--frame\r\n'b'Content-Type: image/png\r\n\r\n' + frame + b'\r\n')
		return frame

class ParseSetting():

	def __init__(self):
		self.SrvCfg = configparser.ConfigParser()
		self.savePath = './config/setting.cfg'

	def read(self, section, savePath='./config/setting.cfg'):
		self.SrvCfg.read(savePath)
		return self.SrvCfg[section]

