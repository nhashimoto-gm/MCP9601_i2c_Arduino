import sys
import serial
import datetime
import csv
import time
#from retry import retry


from influxdb import InfluxDBClient
client = InfluxDBClient('192.168.1.180', 8086, 'root', '', 'sensor')

# ser = serial.Serial('/dev/ttyACM0', 9600, timeout=15)  # ポートの情報を記入

#@retry(delay=1)
def run():
    with serial.Serial('/dev/ttyACM0', 9600) as ser: # ポートの情報を記入
        ser.flush()
        while True:
            ser.flush()
            if ser.in_waiting > 0:
                try:
                    line = ser.readline().decode('utf-8').rstrip()
                    dat = line.split(',')
                    print('Th', dat[0], 'Tc', dat[1], 'T_ADC', dat[2]) #, 'NO2', dat[3], 'EtOH', dat[4], 'VOC', dat[5], 'CO', dat[6])
                    wp_body = [{"measurement": "mpc9601_measure", "fields": {"Th(degC)": float(dat[0]), "Tc(degC)":float(dat[1]), "ADC(uV)":float(dat[2])}}]
                    client.write_points(wp_body)
                except IndexError as ie:
                    print(ie)

if __name__ == '__main__':
    run()
