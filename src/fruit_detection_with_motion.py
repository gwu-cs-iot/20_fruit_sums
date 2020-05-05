import cv2
import io
import os
import numpy as np
import picamera.array
import RPi.GPIO as GPIO
from google.cloud import vision
from picamera import PiCamera
from time import sleep
from datetime import datetime, timedelta, date
from twilio.rest import Client
import button as button

print(cv2.__version__)

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '<add path to cloudkey json file>'

SOURCE_PATH = '<create directory path for captured photos>'

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)
GPIO.setup(10, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(12, GPIO.OUT)

record = False
capture = False
count = 0
start_time = timedelta(seconds=0)
detected_items = []
veggies = []
camera = PiCamera()

class MotionDetector(picamera.array.PiMotionAnalysis):
	
	def analyse(self, a):
		global count
		global start_time
		global record
		global capture
		
		a = np.sqrt(np.square(a['x'].astype(np.float)) + np.square(a['y'].astype(np.float))).clip(0, 255).astype(np.uint8)
		if (a > 60).sum() > 10:
			count = count + 1
			print('Motion detected: ' + str(count))
			capture = True
			start_time = datetime.now()
		else:
			time_gap = datetime.now() - start_time
			print(time_gap)
			if time_gap > timedelta(seconds=10):
				print('quit camera')
				record = False


def capture_food():
	global record
	global capture
	
	record = True

	camera.start_preview(fullscreen=False, window=(100,200,300,400))
	
	camera.start_recording(
		'<add path to store the captured .h264 file>', format='h264',
		motion_output=MotionDetector(camera)
		)
	
	while record:
		camera.wait_recording()
		if capture:
			camera.capture(SOURCE_PATH + 'image' + str(count) + '.jpg')
			signal_capture()
			capture = False

	camera.stop_recording()
	camera.stop_preview()

def load_list_of_fruits_and_veggies():
	
	list = []
	global veggies
	veg = 0
	
	for line in open('types-of-food.txt'):
		food_item = line.rstrip('\n').lower()
		if food_item == '':
			veg = 1
			continue
		if veg == 1:
			veggies.append(food_item)
		list.append(food_item)
		
	
	print(list)
	print(veggies)
	return list
	

def recognize_fruit_and_veggies(list_of_foods):
	
	
	list_of_images = os.listdir(SOURCE_PATH)
	
	for image in list_of_images:
		print(image)
		imageObj = cv2.imread(SOURCE_PATH + image)
		
		height, width = imageObj.shape[:2]
		
		imageObj = cv2.resize(imageObj,  (800, int((height * 800) / width)))
		
		new_img_path = '<add a directory path other than the source path>'
		
		cv2.imwrite(new_img_path, imageObj)
		
		client = vision.ImageAnnotatorClient()
		
		with io.open(new_img_path, 'rb') as image_file:
			content = image_file.read()
			
		img = vision.types.Image(content=content)
		
		response = client.label_detection(image=img)
		labels = response.label_annotations
		
		for label in labels:
			description = label.description.lower()
			score = round(label.score, 2)
			print('label: ', description, ' score: ', score)
			
			if description in list_of_foods:
				print('adding: ' + str(description).upper()) 
				detected_items.append(description)
				break
	
	print('Finished.')


def trim_list():
	
	final_list = {}
	
	for item in detected_items:
		final_list[item] = detected_items.count(item)
		print(item)
		print(detected_items.count(item))
	
	print(final_list)
	
	msg_string = ''
	for key in final_list:
		msg_string = msg_string + key + ': ' + str(final_list[key]) + '\n'
		
	print(msg_string)
	
	return msg_string
	
def send_list(final_list):
	
	account_sid = '<add account sid>'
	auth_token = '<add auth token>'
	
	twilio_client = Client(account_sid, auth_token)
	
	twilio_client.messages.create(
		to='+1<add number>',
		from_='+1<add number>',
		body='\n\nYour produce for the day ' + str(date.today()) + ':\n' + final_list
	)
		
		
def start_produce_detection():
	
	global detected_items
	global veggies
	global start_time
	
	start_time = datetime.now()
	capture_food()
	key_list = load_list_of_fruits_and_veggies()
	recognize_fruit_and_veggies(key_list)
	print(detected_items)
	final_list = trim_list()
	send_list(final_list)
	detected_items = []
	veggies = []	


def signal_capture():
	
	GPIO.output(12, GPIO.HIGH)
	sleep(1)
	GPIO.output(12, GPIO.LOW)


def button_callback(channel):
	
	print('button was pushed')
	start_produce_detection()
	
GPIO.add_event_detect(10, GPIO.RISING, callback=button_callback)

input('Press the push button to start. Press the enter key to quit program.\n')

GPIO.cleanup()
