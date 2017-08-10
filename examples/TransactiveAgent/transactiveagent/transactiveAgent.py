import datetime
import logging
import sys
import json
from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from . import settings
from volttron.platform.messaging import topics, headers as headers_mod

import requests
import json
import time
import csv
from calendar import timegm
from scipy.interpolate import interp1d

from cvxopt import matrix, solvers

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.0'
record_topic = 'record/'
entityId ='transactive_home.transactive_home'
new_state ='on'
device_list=[]
datafile = "data_set.json"
class TransactiveAgent(Agent):
    
    def __init__(self, config_path, **kwargs):
        '''
            Initializes the HASS Switch Agent for communicating with HASS API
            regarding switch components
        ''' 

        super(TransactiveAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self.agentId = self.config['agentId']
        self.hassConfig = self.config['hassConfigPath']
        self.url = self.config['url']
        self.urlPass = self.config['urlPass']
        self.entityId = self.config['entityID'] 
        self.friendly_name = self.config['friendly_name']
        self.flexibility = 10
        self.overall_energy =0
        self.overall_power =0
        self.energyDataPlot = ""
        self.powerDataPlot = ""
        self.zone_max =100
        self.participation=True
        self.reset=False
        self.zone_min =0 
        self.new_state = self.config['state']
        self.request = self.config['request']
        self.data  = []
        self.totalEnergy = 0
        self.device_name =""
        self.totalPower =0
        self.powerDict = {'a':[]}
        self.energyDict = {'b':[]}
        self.deviceDict = {'AC1':[],'AC2':[],'WH1':[]}
        self.deviceDict['AC1'] = {'energy':0,'participate':True,'reset':False,'power':0,'zone_max':0,'zone_min':0}
        self.deviceDict['AC2'] = {'energy':0,'participate':True,'reset':False,'power':0,'zone_max':0,'zone_min':0}
        self.deviceDict['WH1'] = {'energy':0,'participate':True,'reset':False,'power':0,'zone_max':0,'zone_min':0}
    
    @PubSub.subscribe('pubsub', 'house/')
    def on_match_all(self, peer, sender, bus,  topic, headers, message):
        ''' This method subscibes to all topics. It simply prints out the 
        topic seen.
        # '''
        i=0
        self.device_name = topic.partition('/')[-1].rpartition('/')[0]
        urlServices = self.url+'states/'+ self.entityId
        self.data = requests.get(urlServices).json()
        data_json =  json.dumps(self.data)
        dataObject = json.loads(data_json)

        # with open('/home/yingying/git/volttron/examples/TransactiveAgent/transactiveagent/data_set.json') as data_file:   
        #     data = json.load(data_file)
        #     print(data)
        #     for d in data["data"]:
        #       print(d["kWh"])
        # print(dataObject)
        self.flexibility = dataObject['attributes']['overallflexibility'][0]['flexibility']
        self.participation = dataObject['attributes']['device'][str(self.device_name)]['participate']
        self.reset = dataObject['attributes']['device'][str(self.device_name)]['reset']
        # print(str(self.device_name))
        # print(self.participation)
        # print(self.reset)
        # print(self.flexibility)  
        time.sleep(4) 
        if (topic == 'house/'+ self.device_name +'/all'):
            # self.device_name = topic.partition('/')[-1].rpartition('/')[0]
            if (self.device_name in self.deviceDict):
                now = datetime.datetime.now()
                timestamp = now.isoformat()
                self.load_value = round(message[0]['load(kW)'],2)
                self.energy_value = round(message[0]['Energy(kWH)'],2)
                self.device_json = {
                    "energy":self.energy_value,
                    "participate": self.participation ,
                    "power":self.load_value,
                    "reset":self.reset,
                    "zone_max":self.zone_max,
                    "zone_min":self.zone_min} 
                self.deviceDict[self.device_name]=self.device_json
                self.powerPoints = [timestamp]
                for key , value in self.deviceDict.items():
                    if (self.deviceDict[key]['energy']) is not None:
                        # print(self.deviceDict[key]['energy'])
                        self.totalEnergy += self.deviceDict[key]['energy']
                    if (self.deviceDict[key]['power']) is not None:
                        # print(self.deviceDict[key]['power'])
                        self.totalPower += self.deviceDict[key]['power']
                        self.powerPoints.append(self.deviceDict[key]['power'])
                # print(self.powerPoints)
                # self.chartData = []
                # with open('/home/yingying/git/volttron/examples/TransactiveAgent/transactiveagent/data_set.json') as data_file:   
                #     data = json.load(data_file)
                #     for d in data["data"]:
                #       energyPoints = [timestamp,float(d["kWh"]),10,None]
                #       self.chartData.append(energyPoints)

                # print(self.chartData[0][3])
                # self.chartData[i][3] = round(self.totalEnergy,2)
                # energyPoints =self.chartData
                energyPoints = [timestamp,6,10,round(self.totalEnergy,2)]
                self.energyDict['b'].append(energyPoints)
                if (len(self.energyDict['b']) == 10):
                    del self.energyDict['b'][0]
                    print("the first entry deleted")
                self.energyDataPlot = {
                                    "data":self.energyDict['b'],
                                    "type":"line",
                                    "label":"energy"
                } 
                print( self.energyDataPlot)
                self.powerDict['a'].append(self.powerPoints)
                # print(self.powerDict)
                if (len(self.powerDict['a']) == 10):
                    del self.powerDict['a'][0]
                    print("the first entry deleted")

                self.powerDataPlot = {
                                    "data":self.powerDict['a'],
                                    "type":"bar",
                                    "label":"power"
                }
                # print( self.powerDataPlot)
                self.overall_energy =round(self.totalEnergy,2)
                self.overall_power= round(self.totalPower,2)
                # time.sleep(5)
                # print(json.dumps(self.deviceDict))
                if (i != 20):
                    i=i+1
                else:
                    i=0
                self.ChangeTransactiveState(self.device_name,self.deviceDict,self.overall_energy,self.overall_power, self.energyDataPlot, self.powerDataPlot,self.flexibility)



    def ChangeTransactiveState(self,device_name,device_json,overall_energy,overall_power,energyDataPlot, powerDataPlot,flexibility):
        '''
            Turns on the switch.entityId device
        '''
        init_value = 0
        if entityId is None:
            return
        self.totalEnergy = 0
        self.totalPower =0
        
        urlServices = self.url+'states/'+ self.entityId
        try:
            jsonMsg = json.dumps({
                    "attributes": {
                        "chartSeries":[
                            energyDataPlot,
                            powerDataPlot
                        ],
                        "measures":[
                        {
                            "label":"Overall Energy",
                            "unit":"kw-hr/24 hrs",
                            "value":overall_energy
                        },
                        {
                            "label":"Overall Power",
                            "unit":"kw",
                            "value":overall_power                           
                        }],
                        "friendly_name":self.friendly_name,
                        "device": device_json,
                        "friendly_name": "Transactive Home",  
                        "overallflexibility":[
                        {
                            "flexibility" : flexibility,
                            "zone_max" : self.zone_max,
                            "zone_min" : self.zone_min
                        }],
                        "progress_bar":{
                            "end_point":80,
                            "message": "Half-way through, keep up the good work!",
                            "starting_point": 0,
                            "value": 55
                        },   

                    },
                    "state": self.new_state
                })
            # print(jsonMsg)
            header = {'Content-Type': 'application/json'}
            requests.post(urlServices, data = jsonMsg, headers = header)
            print("Transactive State has been changed")
        except ValueError:
                pass

def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(TransactiveAgent,version=__version__)
    except Exception as e:
        print e
        _log.exception('unhandled exception')

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass                 



   
