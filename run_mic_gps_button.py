#!/usr/bin/python3
# This script saves data from ReSpeaker Far-field Mic Array (*.wav) and GPS L80M39 (*.csv)
# triggered by the pushbutton
# ReSpeaker Mic Array - 8 channels, 16 kHz, 16 bit little endian
# GPS - 1 Hz, date, time (UTC), latitude, longitude

import math
import time
import subprocess
import os
import signal
import microstacknode.hardware.gps.l80gps
import threading

import RPi.GPIO as GPIO # Import Raspberry Pi GPIO library
from pixel_ring_on_off import pixel_ring
import sox

PIN_ID = 40

isRunning = False

GPIO.setwarnings(False) # Ignore warning 
GPIO.setmode(GPIO.BOARD) # Use physical pin numbering
GPIO.setup(PIN_ID, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # Set PIN_ID to be an input pin and set initial value to be pulled low (off)

# Start recording data from microphones using in-built library "arecord"
def startMic():
    timestr_mic = time.strftime("%Y%m%d-%H%M%S")

    global filename_mic
    filename_mic = ('mic-data-' + timestr_mic + '.wav')

    cmd = ["arecord", "-M", "-D", "plughw:1", "-v", "-f", "S16_LE", "-c8", "-r16000", filename_mic]

    global micProcess
    micProcess = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid)
    print('Started recording mic')

# Stop recording data from mics
def stopMic():
    os.killpg(os.getpgid(micProcess.pid), signal.SIGTERM)
    print('Stopped recording mic')

# Split written data from mics
def splitMic():
    print('Splitting written mic channels...')
    for channel in range (1, 9):
        tfm = sox.Transformer()
        remix_dictionary = {1: [channel]}
        tfm.remix(remix_dictionary)
        filename_mic_channel = (filename_mic[:-4] + '-ch-' + str(channel) + '.wav')
        tfm.build(filename_mic, filename_mic_channel)
    print('Splitted 8 channels to separate files')

# Start writing GPS data
def startGps():

    # initialisation
    print('Started writing GPS data')
    timestr_gps = time.strftime("%Y%m%d-%H%M%S")
    filename_gps = ('gps-data-' + timestr_gps + '.csv')
    file_csv = open(filename_gps, "w")
    file_csv.write('Date (RPi), Time (RPi), Date (GPS), UTC (GPS), Latitude, Longitude, Validity\n')
    gps = microstacknode.hardware.gps.l80gps.L80GPS()

    # reading loop
    before_msec = 0
    while isRunning:

        # always read from GPS as often as possible
        data = None
        err = None
        try:
            data = gps.get_gprmc()
        except Exception as inst:
            err = inst
            pass

        # ignore readings if less than a second elapsed
        now_msec = math.floor(time.monotonic() * 1000)
        if now_msec - before_msec < 1000:
            continue
        else:
            before_msec = now_msec

        # write either data or an error
        if err is not None:
            file_csv.write(str(err) + '\n')
        else:
            file_csv.write(time.strftime("%d/%m/%Y,%H:%M:%S,") +
                           str(data['date']) + ',' +
                           str(data['utc']) + ',' +
                           str(data['latitude']) + ',' +
                           str(data['longitude']) + ',' +
                           str(data['data_valid']) + '\n')

        # force writing to disk
        file_csv.flush()

    # clean up
    file_csv.close()
    print('Stopped writing GPS data')

# Logic when pushbutton is ON/OFF
def onButtonPress(channel):
    global isRunning
    isRunning = not isRunning
    print("Button pressed, now is " + ("ON" if isRunning else "OFF"))
    if (isRunning):
        pixel_ring.on()
        startMic()
        threading.Thread(target=startGps).start()
    else:
        pixel_ring.off()
        stopMic()
        splitMic()

# Monitoring the status of pushbutton
GPIO.add_event_detect(PIN_ID, GPIO.RISING, callback=onButtonPress, bouncetime=1000)

# Run forever as a service
print('Waiting for push button presses...\n')
while True:
    pass

# Clean up
GPIO.cleanup()
