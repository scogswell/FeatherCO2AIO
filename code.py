#
#
# CO2 Monitor with logging to Adafruit IO using an Adafruit ESP32-S3 TFT 
# and Adafruit SCD-40 CO2/Temperature/Humidity breakout board
#
# https://www.adafruit.com/product/5483
# https://www.adafruit.com/product/5187
#
# SCD-40 is connected via STEMMA
#
# This logs using Adafruit IO to three items in a group:
# 'co2-monitor-group.co2', 'co2-monitor-group.temperature', 'co2-monitor-group.humidity'
# 
# Rather than hammer the network with constant updates this keeps a running average of values
# and only upates adafruitIO every 10 minutes or so.  
#
# In the event of errors publishing to AdafruitIO or network errors the board will automatically
# try to reconnect or eventually reset.  The Neopixel is used to indicated network status.  
# 
# Tested with Circuitpython 8.x.  You need these libraries in /lib:
# adafruit_bus_device, adafruit_display_text, adafruit_io, adafruit_minimqtt, 
# adafruit_scd4x, adafruit_st7789, neopixel 
#
# Steven Cogswell February 2023
import time
import board
import adafruit_scd4x
import ssl
import terminalio
import displayio
from adafruit_display_text import label
from adafruit_st7789 import ST7789
import wifi
import neopixel
import socketpool
import microcontroller
import adafruit_minimqtt.adafruit_minimqtt as MQTT
from adafruit_io.adafruit_io import IO_MQTT

CO2_AVG = 0
TEMP_AVG = 0
HUMID_AVG = 0

AVERAGE_INTERVAL = 10 * 60   # minutes as seconds
AVERAGE_POINTS = 10

i2c = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller
scd4x = adafruit_scd4x.SCD4X(i2c)
print("Serial number:", [hex(i) for i in scd4x.serial_number])
scd4x.start_periodic_measurement()

display=board.DISPLAY
text_data = displayio.Group()
co2_text = label.Label(terminalio.FONT, color=0x00FF00)
co2_text.anchored_position = (0,0)
co2_text.scale=3
co2_text.anchor_point=(0,0)

temp_humid_text = label.Label(terminalio.FONT, color=0xFFFFFF)
temp_humid_text.anchored_position=(0,34)
temp_humid_text.anchor_point=(0,0)
temp_humid_text.scale=2

avg_text = label.Label(terminalio.FONT, color=0x00FFFF)
avg_text.anchored_position=(0,90)
avg_text.anchor_point=(0,0)
avg_text.scale=1

message_text = label.Label(terminalio.FONT, color=0xFFFFFF)
message_text.anchored_position=(0,105)
message_text.anchor_point=(0,0)
message_text.scale=2

text_data.append(co2_text)
text_data.append(temp_humid_text)
text_data.append(avg_text)
text_data.append(message_text)
display.show(text_data)
co2_text.text = "CO2 Monitor"
temp_humid_text.text = "IO Updating {:d} sec".format(AVERAGE_INTERVAL)

def calculate_average(new_value, old_average, n):
    """
    https://stackoverflow.com/questions/12636613/how-to-calculate-moving-average-without-keeping-the-count-and-data-total
    """
    new_average = (old_average * (n-1) + new_value)/n
    return new_average

# Adafruit IO callback when connected
def io_connected(client):
    """ Callback for when connected to Adafruit IO"""
    message_text.text = "Adafruit IO OK"

def io_message(client, feed_id, payload):  # pylint: disable=unused-argument
    print("Feed {0} received new value: {1}".format(feed_id, payload))

def connect_wifi():
    if wifi.radio.ipv4_address is not None:
        return
    pixel.fill((0,255,255))
    try:
        pixel.fill((0,0,255))
        message_text.text="WiFi Connect"
        print("Connecting to %s" % secrets["ssid"])
        wifi.radio.connect(secrets["ssid"], secrets["password"])
        print("Connected to %s!" % secrets["ssid"])
        message_text.text = str(wifi.radio.ipv4_address)
        print("IPv4 address",wifi.radio.ipv4_address)
        time.sleep(0.5)
    # Wi-Fi connectivity fails with error messages, not specific errors, so this except is broad.
    except Exception as e:  # pylint: disable=broad-except
        pixel.fill((255,0,0))
        print("Failed to connect to WiFi. Error:", e, "\nBoard will hard reset in 30 seconds.")
        message_text.text="WiFi Error"
        time.sleep(30)
        microcontroller.reset()
    pixel.fill((0,255,0))

def connect_and_publish(co2,t,h):
    connect_wifi()
    print("IP address is",wifi.radio.ipv4_address)
    message_text.text = str(wifi.radio.ipv4_address)
    try:
        if not io.is_connected:
            pixel.fill((255,255,0))
            print("Not connected to Adafruit IO, connecting")
            message_text.text="IO Connect"
            io.connect()
        pixel.fill((0,255,255))
        message_text.text = "IO Publish"
        print("Publishing data to Adafruit IO")
        io.publish_multiple([('co2-monitor-group.co2',co2),('co2-monitor-group.temperature',t),('co2-monitor-group.humidity',h)], is_group=True)
    except Exception as e:   # pylint: disable=broad-except
        pixel.fill((255,0,0))
        print("Failure conneting to Adafruit IO. Error:", e, "\nBoard will hard reset in 30 seconds.")
        message_text.text="AdafruitIO Error"
        time.sleep(30)
        microcontroller.reset()
    message_text.text = "IO Success"
    print("Data published")
    pixel.fill((0,255,0))
    time.sleep(0.5)

# Initialise NeoPixel
pixel = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.3)

try:
    from secrets import secrets
except ImportError:
    print("WiFi and Adafruit IO credentials are kept in secrets.py - please add them there!")
    raise

connect_wifi()

# Create a socket pool
pool = socketpool.SocketPool(wifi.radio)
# Initialize a new MQTT Client object
mqtt_client = MQTT.MQTT(
    broker="io.adafruit.com",
    username=secrets["aio_username"],
    password=secrets["aio_key"],
    socket_pool=pool,
    ssl_context=ssl.create_default_context(),
)

# Initialize Adafruit IO MQTT "helper"
io = IO_MQTT(mqtt_client)
# Set up the callback methods above
io.on_connect = io_connected
io.on_message = io_message

if not io.is_connected:
    pixel.fill((255,255,0))
    print("Not connected to Adafruit IO, connecting")
    message_text.text="IO Connect"
    io.connect()
pixel.fill((0,255,255))

print("Waiting for first SCD4x measurement")
message_text.text = "SCD4x Init"

while not scd4x.data_ready:
    time.sleep(0.5)
CO2_AVG = scd4x.CO2
TEMP_AVG = scd4x.temperature
HUMID_AVG = scd4x.relative_humidity
print("Initial values",CO2_AVG,"ppm",TEMP_AVG," C",HUMID_AVG,"%")

refresh_time = time.monotonic()
points = 0
interval_points = 0
while True:
    if scd4x.data_ready:
        points += 1
        co2 = scd4x.CO2
        temperature = scd4x.temperature
        humidity = scd4x.relative_humidity
        CO2_AVG = calculate_average(co2, CO2_AVG, AVERAGE_POINTS)
        TEMP_AVG = calculate_average(temperature, TEMP_AVG, AVERAGE_POINTS)
        HUMID_AVG = calculate_average(humidity, HUMID_AVG, AVERAGE_POINTS)
        co2_text.text = "CO2 %d ppm" % co2
        temp_humid_text.text = "Temp {:.1f} C\nHumidity: {:.1f}%".format(temperature,humidity)
        avg_text.text = "Avg {:.1f} ppm, {:.1f} C, {:.1f}% pts {:d}".format(CO2_AVG, TEMP_AVG, HUMID_AVG,AVERAGE_POINTS)
        if wifi.radio.ipv4_address is not None:
            message_text.text=str(wifi.radio.ipv4_address)
        else:
            message_text.text=""

        print(co2_text.text)
        print(temp_humid_text.text)
        print(avg_text.text)
        print()
        try:
            io.loop()
        except Exception as e:
            message_text.text="io.loop() failed"
            print("Failure in io.loop(). Error:", e, "\nTrying to reconnect")
            try:
                io.reconnect()
            except Exception as e2:
                print("Failure in io.loop() reconnect. Error:", e2, "\nRebooting")
                message_text.text="io.loop() Rebooting"
                time.sleep(30)
                microcontroller.reset()
            print("Reconnect to adafruit io completed")

        if time.monotonic() - refresh_time > AVERAGE_INTERVAL:
            refresh_time = time.monotonic()
            AVERAGE_POINTS = points
            points=0
            print("Interval refresh")
            print("Average points over interval was",AVERAGE_POINTS)
            connect_and_publish(co2=CO2_AVG,t=TEMP_AVG,h=HUMID_AVG)

    time.sleep(1)
