import sys
import serial
import datetime
import csv
import time
from retry import retry


from influxdb import InfluxDBClient
client = InfluxDBClient('192.168.1.180', 8086, 'root', '', 'sensor')

# ser = serial.Serial('/dev/ttyACM0', 9600, timeout=15)  # ポートの情報を記入

@retry(delay=5)
def run():
    with serial.Serial('/dev/ttyACM0', 9600, timeout=15) as ser: # ポートの情報を記入
        while (1):
            time.sleep(0.8)
            value = str(ser.readline().decode('utf-8').rstrip('\n'))
            # date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            dat = value.split(',')
            print('Th', dat[0], 'Tc', dat[1], 'T_ADC', dat[2], 'NO2', dat[3], 'EtOH', dat[4], 'VOC', dat[5], 'CO', dat[6])
            wp_body = [{"measurement": "mpc9601_measure", "fields": {"Th(degC)": float(dat[0]), "Tc(degC)":float(dat[1]), "ADC(uV)":float(dat[2])}}]
            client.write_points(wp_body)
            wp_body = [{"measurement": "mgs_v2_measure_R", "fields": {"NO2": int(dat[3]), "C2H5OH":int(dat[4]), "VOC":int(dat[5]), "CO":int(dat[6])}}]
            client.write_points(wp_body)

if __name__ == '__main__':
    run()

    # print(date+','+value)
    # with open('mgs.csv', 'a') as f:
    #    print('{},{}'.format(date,value),file=f)
