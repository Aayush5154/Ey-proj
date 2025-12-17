import serial
import pymongo
from datetime import datetime
import time

ser = serial.Serial('COM5', 9600)  


client = pymongo.MongoClient("YOUR_MONGODB_CONNECTION_STRING")
db = client["smoke"]
collection = db["mq2Data"]

print("Reading from Arduino...")

last_insert_time = 0 

while True:
    try:
        raw_value = ser.readline().decode().strip()

        if raw_value.isdigit():
            value = int(raw_value)
            print("MQ2 Value:", value)

            current_time = time.time()

            if current_time - last_insert_time >= 10:
                data = {
                    "value": value,
                    "timestamp": datetime.now(),
                    # "maintenance": "Required" if value < 300 else "OK"
                }

                collection.insert_one(data)
                last_insert_time = current_time  

                print("Inserted into DB:", data)
            else:
                print("Waiting to insert...")

    except Exception as e:
        print("Error:", e)
