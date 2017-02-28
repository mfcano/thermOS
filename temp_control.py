#temp

import RPi.GPIO as GPIO
import time
import sys
import automationhat
import Adafruit_DHT
import json
import multiprocessing
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import SocketServer
import math
import os.path

class S(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
    	self.send_header('Access-Control-Allow-Credentials', 'true')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

    def do_GET(self):
        self._set_headers()
        res = open("commtemp.txt", "r")
    	# self.send_header('Access-Control-Allow-Credentials', 'true')
     #    self.send_header('Access-Control-Allow-Origin', '*')
        s = res.read()
        self.wfile.write(str(s))

    def do_HEAD(self):
        self._set_headers()
        
    def do_POST(self):
        # Doesn't do anything with posted data
        self._set_headers()
        self.wfile.write("<html><body><h1>POST!</h1></body></html>")
        # self.send_response(200)
        # self.send_header('Access-Control-Allow-Credentials', 'true')
        # self.send_header('Access-Control-Allow-Origin', '*')
        s = self.rfile.read(int(self.headers.getheader('Content-Length')))
        print "POST response", s
        set_point_log = open("setpoint_log.txt", "w")
        set_point_log.write(s + "\n")
        set_point_log.close()
        #write in intervals
        
def run(server_class=HTTPServer, handler_class=S, port=8081):
    server_address = ("128.237.250.46", port)
    httpd = server_class(server_address, handler_class)
    print 'Starting httpd...'
    httpd.serve_forever()

# GPIO Setup
# GPIO.setwarnings(False)

# BCM pin numberings                    # Automation Hat:
TEMP_HUMID_PIN = 15                     # Input 1
MOTION_SENSOR_PIN = 20                  # Input 2
ACTUATOR_CONTROL = 5                    # Output 1
LED_PIN = 12                            # Output 2

SET_POINT_TEMP = 68
MAX_DELTA = 1
TEMP_READ_PERIOD = 5 
HOME_LAT = 40.443468
HOME_LON = -79.9420620

GPIO.setup(TEMP_HUMID_PIN, GPIO.IN)     # Temp/Humidity pin

GPIO.setup(MOTION_SENSOR_PIN, GPIO.IN)  # PIR motion sensor pin
GPIO.setup(ACTUATOR_CONTROL, GPIO.OUT)  # Actuator control pin
GPIO.setup(LED_PIN, GPIO.OUT)           # LED output pin

# Set PWM to 1kHz on actuator control pin
PWM1 = GPIO.PWM(ACTUATOR_CONTROL, 1000)

SET_POINT_TEMP = 68 # Temperature in Fahrenheit
MAX_DIFF = 5 # Max difference between set_point_temp and current temp
TEMP_READ_PERIOD = 50
MAX_TSO = 100
# state defintions
DVAC, DCOL, DTVAC, DCOOL, DHEAT = 0, 1, 2, 3, 4

# outputs
FAN_SPEED = (0, 0, 0, 0) # OFF, FS1, FS2, FS3
VALVE = (0, 0, 0, 0) # VOFF, V30, V60, V90

############## Room Occupancy Detection #######################################

def imm_occupancy_detect(pin):
	if not pin:
		time.sleep(0.1)
		return 0 # empty
	elif pin == 1:
		time.sleep(0.1)
		return 1 # full
	else:
		return -1
		
############## Actuator Module ############################################

def rotate_valve(valve):
  """
  Rotate the valve to a position from 0 - 90 degrees
  """
 
  if valve[0] == 1:
    position = 0   # 0
  elif valve[1] == 1:
    position = 30  # 30
  elif valve[2] == 1:
    position = 60  # 60
  elif valve[3] == 1:
    position = 90  # 90
  else:
    return
  
  # Higher duty cycle corresponds to lower voltage for
  # the wiring. Duty cycle is percentage.
  duty = int(100*(position/90.0))
  PWM1.start(duty)

############## Fan Module #################################################

def switch_fan(speed):
  """
  Switch the relays to set the fan speed.
  """
 
  if speed[0] == 1:
  
  	automationhat.relay.one.off()
  	automationhat.relay.two.off()
  	automationhat.relay.three.off()
  elif speed[1] == 1:
  
  	automationhat.relay.two.off()
  	automationhat.relay.three.off()
  	automationhat.relay.one.on()  # low
  elif speed[2] == 1:

  	automationhat.relay.one.off()
  	automationhat.relay.three.off()
  	automationhat.relay.two.on()  # medium
  elif speed[3] == 1:
  	automationhat.relay.one.off()
  	automationhat.relay.two.off()
  	automationhat.relay.three.on() # high

#############################################################################
####### Temperature AND Humidity Module ###################################

def temp_humid_call():
	# Parse command line parameters.
	
	sensor = Adafruit_DHT.AM2302
	pin = str(TEMP_HUMID_PIN)

	# Try to grab a sensor reading.  Use the read_retry method which will retry up
	# to 15 times to get a sensor reading (waiting 2 seconds between each retry).
	humidity, temperatureC = Adafruit_DHT.read_retry(sensor, pin)

	# in Fahrenheit
	if (humidity is not None and temperatureC is not None):
		temperatureF = temperatureC * (9/5.0) + 32
		return(int(temperatureF), int(temperatureC), int(humidity))
	else:
		print("Error -- no data from sensor")
		return('Jailed to get reading temperature/humidity reading. Check pin connections.')

def mono_occup(occup, reg_occup):
	if (occup != reg_occup):
		print "Occupancy:", occup
	
	if occup:
		GPIO.output(LED_PIN, 1)

	else:
		GPIO.output(LED_PIN, 0)

def mono_temp_humid(temp_humid, reg_temp_humid):
	if (temp_humid != reg_temp_humid):
		print "Temperature and Humidity:", temp_humid[0], "F,", temp_humid[2], "%"
		reg_temp_humid = temp_humid

def temp_test(temperature):
	temp = int(temperature)
	if abs(temp - SET_POINT_TEMP) > MAX_DELTA:
		return temp - SET_POINT_TEMP 
	return 0

def log(temp_humid, occup, logfile, trigger):
	t = time.strftime("%Y-%m-%d %H:%M:%S")
	if (trigger):
		s = "{0}, {1}, {2}, {3}\n".format(t,
			temp_humid[0], occup, temp_humid[2])

		temp = open("commtemp.txt", "w")
		temp.write(s + "\n")
		temp.close()

		logfile.write(s)

class switch(object):
    value = None
    def __new__(class_, value):
        class_.value = value
        return True

def case(*args):
    return any((arg == switch.value for arg in args))

def distance(lat1, lng1, lat2, lng2):
    #return distance as meter if you want km distance, remove "* 1000"
    radius = 6371 * 1000 

    dLat = (lat2-lat1) * math.pi / 180
    dLng = (lng2-lng1) * math.pi / 180

    lat1 = lat1 * math.pi / 180
    lat2 = lat2 * math.pi / 180

    val = math.sin(dLat/2) * math.sin(dLat/2) + math.sin(dLng/2) * math.sin(dLng/2) * math.cos(lat1) * math.cos(lat2)    
    ang = 2 * math.atan2((val)**(0.5), (1-val)**(0.5))
    return radius * ang

def dist_miles(lat1, lon1, lat2, lon2):
	return distance(lat1, lon1, lat2, lon2) * 0.000621371

def read_curr_coor():
	if os.path.exists("/tmp/gps-position.txt"):
		coor = open("/tmp/gps-position.txt", "r")
		s = coor.read()
		if len(s) < 1: return (50.44116175, -79.94548589)
		ret = float(s.split('_')[1]), float(s.split('_')[2])
		return ret
	else:
		return (50.44116175, -79.94548589)

def set_point_start():
	global SET_POINT_TEMP
	global MAX_DELTA
	global TEMP_READ_PERIOD
	global HOME_LAT
	global HOME_LON
	if os.path.exists("setpoint_log.txt"):
		s = open("setpoint_log.txt", "r")
		file = s.read()
		if len(file) > 1:
			split = file.split(",")
			for i in range(len(split)):
				split[i] = float(split[i])
			(SET_POINT_TEMP, MAX_DELTA, 
				TEMP_READ_PERIOD, HOME_LAT, HOME_LON) = split

#############################################################################
################################# Main Loop ####################################

def main():
	reg_temp_humid, reg_occup = -1, -1
	temp_delay = 0
	state, next_state = DVAC, DVAC
	TSO = 0
	temp_humid, occup = (SET_POINT_TEMP, 0, 0), 0
	logfile = open("temp_log.txt", 'w')

	while True:
		temp_delay += 1

		while switch(state):
			# Default Vacant 
			if case(DVAC):
				set_point_start()
				FAN_SPEED = (1, 0, 0, 0)
				VALVE = (0, 0, 0, 0)
				switch_fan(FAN_SPEED)
				rotate_valve(VALVE)
				
				(curr_lat, curr_lon) = read_curr_coor()
				dist = dist_miles(HOME_LAT, HOME_LON, curr_lat, curr_lon) 
				#print dist
				if dist <= 2:
					next_state = DCOL
				else:
					next_state = DVAC
				break
			
			# Default Collect
			if case(DCOL):
				trigger = 0
				
				# read occupancy
				gpio_occupant_in = GPIO.input(MOTION_SENSOR_PIN)
				occup = imm_occupancy_detect(gpio_occupant_in)
				mono_occup(occup, reg_occup)
				trigger = (reg_occup != occup)
				reg_occup = occup

				# read humidity & temperature
				if not (temp_delay % TEMP_READ_PERIOD):
					temp_humid = temp_humid_call()
					mono_temp_humid(temp_humid, reg_temp_humid)
					trigger = (temp_humid != reg_temp_humid)

				# read gps

				(curr_lat, curr_lon) = read_curr_coor()
				dist = dist_miles(HOME_LAT, HOME_LON, curr_lat, curr_lon)
				
				if (occup): TSO = 0
				
				TSO += 1

				if dist > 2:
					next_state = DVAC
				elif TSO > MAX_TSO:
					next_state = DTVAC
				elif (temp_test(temp_humid[0]) > 0):
					next_state = DCOOL
				elif (temp_test(temp_humid[0]) < 0):
					next_state = DHEAT
				else:
					next_state = DTVAC
	
				log(temp_humid, occup, logfile, trigger)
				break
			
			# Default Cool
			if case(DCOOL):
				VALVE = (0, 0, 0, 1)
				dT = temp_test(temp_humid[0])
				FAN_SPEED = (0, dT <= 2, dT > 2 and dT <= 4, dT > 4)
				switch_fan(FAN_SPEED)
				rotate_valve(VALVE)
				next_state = DCOL
				break

			# Default Heat
			if case(DHEAT):
				VALVE = (1, 0, 0, 0)
				FAN_SPEED = (1, 0, 0, 0)
				switch_fan(FAN_SPEED)
				rotate_valve(VALVE)
				next_state = DCOL
				break

			if case(DTVAC):
				VALVE = (0, 1, 0, 0)
				FAN = (0, 1, 0, 0)
				switch_fan(FAN_SPEED)
				rotate_valve(VALVE)
				next_state = DCOL
				break

		state = next_state


if __name__ == "__main__":
	jobs = []
#	LATEST_DATA = multiprocessing.Value("c", 1)
	p = multiprocessing.Process(target=run)
	j = multiprocessing.Process(target=main)

	jobs.append(p)
	jobs.append(j)
	p.start()
	j.start()
