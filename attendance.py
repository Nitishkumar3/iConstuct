from datetime import datetime
import cv2
from pyzbar.pyzbar import decode
import psycopg2

#del-> ALTER TABLE nk_skcet_attendance DROP COLUMN i_19_12_2023;

db_config = {
    'host': '161.97.70.226',
    'user': 'iconstruct',
    'password': 'u9fk9jp0Ux4dlj71OCKb',
    'database': 'iconstruct',
}

connection = psycopg2.connect(**db_config)

#edit here
project="SKCET"
username="harish"
# sts="out"
#edit here

# stsv="I" if sts =="in" else "O"
stsv="I"

qr_data_dict = {}
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    decoded_objects = decode(gray)

    for obj in decoded_objects:
        qr_data = obj.data.decode('utf-8')
        if qr_data not in qr_data_dict:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            qr_data_dict[qr_data] = current_time
            print(f"ID: {qr_data}")
            print(f"Time: {current_time}")
            print("------------------------------")

    cv2.imshow('QR Code Scanner', frame)
    key = cv2.waitKey(1) & 0xFF

    if key == ord('x'):
        with connection.cursor() as cursor:
            date = datetime.now()
            dstring = f"{stsv}_{date.day}_{date.month}_{date.year}"
            cursor.execute(f"ALTER TABLE {username}_{project}_attendance ADD COLUMN {dstring} TIMESTAMP;") 
        connection.commit()

        print("Attendance:")
        for qr_data, timestamp in qr_data_dict.items():
            print(f"ID: {qr_data} Time: {timestamp}")
            with connection.cursor() as cursor:
                cursor.execute(f"UPDATE {username}_{project}_attendance SET {dstring} = %s WHERE unid = %s", (timestamp, qr_data))        
            connection.commit()
        cv2.destroyAllWindows()
        break

cap.release()