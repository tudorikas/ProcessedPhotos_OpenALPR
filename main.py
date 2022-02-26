import string
import traceback
from datetime import datetime
import pika
import json
import cv2 as cv
import numpy as np
import random
import csv
import WriteXls
from os import path

"""
    File processedJson.py have the role to get all the processed json from 
    detectnetWork.py and save them in CSV and XLSX + make the Blur for the plate number
"""

class processedJson:
    """ The main class that will process the jsons """

    def __init__(self):
        """Initialize and read from json Config file.
	            DefaultTruckPlateHeight- The default truck plate height (20 its ok)
	            DefaultTruckHeight- The default truck height (260 its ok)
	            WriteProcessedFile- Let 0, used for debug
	            RabbitmqServer- IP RabbitMQ server
	            RabbitmqQueue- RabbitMQ Queueu to connect for getting messages
	            PathToSaveCsv- Path to csv files, need to be with / at final
	            PathToSaveXlsx- Path to XLSX files, need to be with / at final  """
        with open('processedJson.json') as json_file:
            self.JsonConfig = json.load(json_file)
        #self.CsvFileName = self.JsonConfig['CsvFileName']
        self.DefaultTruckPlateHeight = self.JsonConfig['DefaultTruckPlateHeight']
        self.DefaultTruckHeight = self.JsonConfig['DefaultTruckHeight']
        self.WriteProcessedFile = self.JsonConfig['WriteProcessedFile']
        self.RabbitmqServer = self.JsonConfig['RabbitmqServer']
        self.RabbitmqQueue = self.JsonConfig['RabbitmqQueue']
        self.PathToSaveCsv = self.JsonConfig['PathToSaveCsv']
        self.PathToSaveXlsx = self.JsonConfig['PathToSaveXlsx']
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.RabbitmqServer))
        self.channel = self.connection.channel()
        self.writerXls = WriteXls.XlsWriter(self.PathToSaveXlsx)
        args = {"x-max-length": 200}
        self.channel.queue_declare(queue=self.RabbitmqQueue, durable=True,arguments=args)
        self.channel.basic_qos(prefetch_count=1)
        self.channel.basic_consume(queue=self.RabbitmqQueue, on_message_callback=self.callback)
        self.channel.start_consuming()


    #day, time, nationality, first numbers of licence plate, nationality, brand of vehicles
    def create_csv(self,FileName):
        """Create the csv file with all the columns."""
        with open(FileName, 'a') as csvfile:
            fieldnames = ['time','is_parked','best_region','country','picture_name',
                          'orientation','orientation_confidence','color','color_confidence','make_model','make_model_confidence',
                          'make','make_confidence','year','year_confidence','body_type','body_type_confidence','best_confidence',
                          'best_plate_number','region_confidence','confidence']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            csvfile.close()


    def add_row(self,time,date,jsonget,file_path):
        """Add new entry in the csv file."""
        licence_plate=jsonget['best_plate_number'][:3]
        timeforName = int(date) / 1000
        dateget = datetime.utcfromtimestamp(timeforName).strftime('%d_%m_%Y')
        FileName = self.PathToSaveCsv+str(dateget) + "_OpenAlpr.csv"
        if not path.exists(FileName):
            self.create_csv(FileName)

        with open(FileName, 'a') as csvfile:
            fieldnames = ['time', 'is_parked', 'best_region', 'country', 'picture_name',
                          'orientation', 'orientation_confidence', 'color', 'color_confidence', 'make_model',
                          'make_model_confidence',
                          'make', 'make_confidence', 'year', 'year_confidence', 'body_type', 'body_type_confidence',
                          'best_confidence',
                          'best_plate_number', 'region_confidence', 'confidence']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writerow({'time': time, 'is_parked': jsonget['is_parked'], 'best_region': jsonget['best_region'],
                             'country': jsonget['country'], 'picture_name': file_path,
                             'orientation': jsonget['vehicle']['orientation'][0]['name'],
                             'orientation_confidence': jsonget['vehicle']['orientation'][0]['confidence'],
                             'color': jsonget['vehicle']['color'][0]['name'],
                             'color_confidence': jsonget['vehicle']['color'][0]['confidence'],
                             'make_model': jsonget['vehicle']['make_model'][0]['name'],
                             'make_model_confidence': jsonget['vehicle']['make_model'][0]['confidence'],
                             'make': jsonget['vehicle']['make'][0]['name'],
                             'make_confidence': jsonget['vehicle']['make'][0]['confidence'],
                             'year': jsonget['vehicle']['year'][0]['name'],
                             'year_confidence': jsonget['vehicle']['year'][0]['confidence'],
                             'body_type': jsonget['vehicle']['body_type'][0]['name'],
                             'body_type_confidence': jsonget['vehicle']['body_type'][0]['confidence'],
                             'best_confidence': jsonget['best_confidence'],
                             'best_plate_number': licence_plate,
                             'region_confidence': jsonget['best_plate']['region_confidence'],
                             'confidence': jsonget['best_plate']['confidence']})
            csvfile.close()

    def convertBack(self,x,y,w,h):
        """Used for debug."""
        xmin=int(round(x-(w/2)))
        xmax=int(round(x+(w/2)))
        ymin=int(round(y-(h/2)))
        ymax=int(round(y+(h/2)))
        return xmin,ymin,xmax,ymax

    def compare(self,vehicle,plate):
        """Compare the height of the plate entered with the height of the plate form config
        and then resize the height of the car/truck to compare with the one from Config."""
        print("Compare")

        default_truck_plate_height=self.DefaultTruckPlateHeight
        default_truck_height=self.DefaultTruckHeight

        #width=plate[2]['x']-plate[0]['x']
        heigh=plate[2]['y']-plate[0]['y']

        resize=default_truck_plate_height/heigh

        resized_heigh=vehicle['height']*resize
        if resized_heigh>=default_truck_height:
            return "truck"
        else:
            return "car"

    def modify_plate(self,vehicle,plate):
        """Algorithm for automation change of the height of the truck."""
        heighPlate = plate[2]['y'] - plate[0]['y']
        resize = self.DefaultTruckPlateHeight / heighPlate
        resized_heigh_car = vehicle['height'] * resize
        #print("OLD DEFAULT "+str(self.DefaultTruckHeight))
        if resized_heigh_car<self.DefaultTruckHeight:
            self.DefaultTruckHeight=self.DefaultTruckHeight-((self.DefaultTruckHeight-resized_heigh_car)/2)
        if resized_heigh_car>self.DefaultTruckHeight:
            self.DefaultTruckHeight=self.DefaultTruckHeight+((resized_heigh_car-self.DefaultTruckHeight)/4)
        #print("MODIF NEW DEFAULT "+str(self.DefaultTruckHeight))
    def calculate(self,jsonet):
        """Here are 3 cases:
        1)If there are many detection, check if the first one have confidenge over 0.65, if yes
        return the type of the first decetion, if not go to check if there are any car, if not return truck
        else go to Compare
        2)If there are no detections, go to Compare
        3)If there are 1 detection, check if confidence is over 0.6 return the type of detecion,
        if not, go to Compare"""
        if len(jsonet['detections'])>1:
            #multiple detection
            if float(jsonet['detections'][0]['confidence'])>=0.65:
                #certain detect
                if jsonet['detections'][0]['type']=='car':
                    return "car"
                elif jsonet['detections'][0]['type']=='truck' or \
                        jsonet['detections'][0]['type']=='bus' or \
                            jsonet['detections'][0]['type']=='train':
                    #save height
                    vehicle = jsonet['rest']['rest']['best_plate']['vehicle_region']
                    plate = jsonet['rest']['rest']['best_plate']['coordinates']
                    self.modify_plate(vehicle,plate)
                    return "truck"
                return "car"
            else:
                okNoCar=1
                for det in jsonet['detections']:
                    if det['type']=="car":
                        okNoCar=0
                if okNoCar==1:
                    return "truck"
                else:
                    vehicle=jsonet['rest']['rest']['best_plate']['vehicle_region']
                    plate=jsonet['rest']['rest']['best_plate']['coordinates']
                    return self.compare(vehicle,plate)
        elif len(jsonet['detections'])==0:
            vehicle = jsonet['rest']['rest']['best_plate']['vehicle_region']
            plate = jsonet['rest']['rest']['best_plate']['coordinates']
            return self.compare(vehicle, plate)
        else:
            #1 detection
            if float(jsonet['detections'][0]['confidence']) >= 0.60:
                # certain detect
                if jsonet['detections'][0]['type'] == 'car':
                    return "car"
                elif jsonet['detections'][0]['type'] == 'truck' or \
                        jsonet['detections'][0]['type'] == 'bus' or \
                        jsonet['detections'][0]['type'] == 'train':
                    vehicle = jsonet['rest']['rest']['best_plate']['vehicle_region']
                    plate = jsonet['rest']['rest']['best_plate']['coordinates']
                    self.modify_plate(vehicle, plate)
                    return "truck"
                return "car"
            else:
                vehicle = jsonet['rest']['rest']['best_plate']['vehicle_region']
                plate = jsonet['rest']['rest']['best_plate']['coordinates']
                return self.compare(vehicle, plate)

    def blurImage(self,jsonget):
        """Blur the plate number."""
        path=jsonget['rest']['img']
        best_plate=jsonget['rest']['rest']['best_plate']['coordinates']
        roi_corners=np.array([[(best_plate[0]['x'],best_plate[0]['y']), \
                               (best_plate[1]['x'],best_plate[1]['y']), \
                               (best_plate[2]['x'],best_plate[2]['y']), \
                               (best_plate[3]['x'],best_plate[3]['y'])]], dtype=np.int32)
        image=cv.imread(path)
        blurred_image=cv.GaussianBlur(image,(65,65),0)
        mask=np.zeros(image.shape,dtype=np.uint8)
        channel_count=image.shape[2]
        ignore_mask_color=(255,)*channel_count
        cv.fillPoly(mask,roi_corners,ignore_mask_color)
        mask_inverse=np.ones(mask.shape).astype(np.uint8)*255 - mask
        final_image=cv.bitwise_and(blurred_image,mask)+cv.bitwise_and(image,mask_inverse)
        cv.imwrite(path,final_image)

    def callback(self,ch,method,properties,body):
        """Wait for a processed json from detectnetWork.py and process it, in the end write in csv and xls"""
        try:
            #TODO check time stamp
            jsonget=json.loads(body)
            self.blurImage(jsonget)
            respond=self.calculate(jsonget)
            #image=jsonget['rest']['img']
            #photoUnecoded=base64.b64decode(image)
            #fileName = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(2))
            #if self.WriteProcessedFile==1:
            #    with open(self.PathProcessedFile+str(fileName)+"_"+respond+".jpg",'wb') as f:
            #        f.write(photoUnecoded)
            #        f.close()
            test=jsonget['rest']['date']
            test=int(test)/1000
            test = test + 1 * 60 * 60
            jsonget['rest']['date']=test*1000
            time=int(jsonget['rest']['date'])/1000
            date=datetime.utcfromtimestamp(time).strftime('%Y-%m-%d %H:%M:%S')
            #region=jsonget['rest']['rest']['best_plate']['region']
            #plate_number=jsonget['rest']['rest']['best_plate']['plate']

            #list with numbers
            #plate_number_list=list()
#
            #for i in range(0,3):
            #    plate_number_list.append("None")
            #i=0
            #for index in jsonget['rest']['rest']['candidates']:
            #    plate_number_list[i]=index['plate']
            #    i=i+1
            #    if i==3:
            #        break
            type=respond
            self.writerXls.set_value_increment(jsonget,type)
            print(str(type))
            self.add_row(date,jsonget['rest']['date'],jsonget['rest']['rest'],jsonget['rest']['img'])
            #tell rabbit i get the message
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            print(str(e))
            with open('Log_ProcessedJson.txt', 'a') as the_file:
                now = datetime.now()  # current date and time
                the_file.write(
                    now.strftime("%m/%d/%Y, %H:%M:%S") + " " + repr(e) + " " + traceback.format_exc() + "\n")
                the_file.close()
                ch.basic_ack(delivery_tag=method.delivery_tag)


#create_csv()
#add_row()

processedJson = processedJson()
