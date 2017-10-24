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
        self.flexibility = 50
        self.load_value1 =0
        self.energy_value1 =0
        self.load_value2 =0
        self.energy_value2 =0
        self.load_value3 =0
        self.energy_value3 =0
        self.overall_energy =0
        self.overall_power =0
        self.device1_json = ""
        self.device2_json = ""
        self.device3_json = ""
        self.energyDataPlot = ""
        self.powerDataPlot = ""
        self.zone_max =100
        self.zone_min =0 
        self.new_state = self.config['state']
        self.request = self.config['request']
        self.data  = []
        self.powerDict = {'a':[]}
        self.energyDict = {'b':[]}
        
        # if ((request == "get")):
        #     while True: 
        #         self.GetData()

    # @Core.receiver('onstart')
    # def getOrPost(self,sender, **kwargs):
    #     # self.config = utils.load_config(config_path)
    #     # request = self.config['request']
    #     if ((self.request == "get")):
    #         while True: 
    #             self.GetData()



    # @Core.receiver('onstart')
    def GetData(self):
        '''
            Get the current state for loaded components
            from Home Assistant API
        '''
        urlStates = self.url+'states'
        self.data = requests.get(urlStates).json()
        data_json =  json.dumps(self.data)
        dataObject = json.loads(json.dumps(data_json))
        print(dataObject)
        pub_topic= 'house/AC1/AC1_beta'
        now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
        headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
        self.vip.pubsub.publish('pubsub',pub_topic,headers,0.6)     
        time.sleep(5)       


       



    @PubSub.subscribe('pubsub', 'house/')
    def on_match_all(self, peer, sender, bus,  topic, headers, message):
        ''' This method subscibes to all topics. It simply prints out the 
        topic seen.
        # '''
        device_name = topic.partition('/')[-1].rpartition('/')[0]
        # timestamp = headers['Date']
        # now = datetime.datetime.now()
        # timestamp = now.isoformat()
        # if (device_name not in device_list):
        #     device_list.append(device_name)
        if (device_name == 'AC1'):
            if (topic == 'house/'+ device_name +'/all'):
                now = datetime.datetime.now()
                timestamp = now.isoformat()
                self.load_value1 = round(message[0]['load(kW)'],2)
                self.energy_value1 = round(message[0]['Energy(kWH)'],2)
                self.device1_json = {
                            "efficiency":50,
                            "energy":self.energy_value1,
                            "name":device_name,
                            "participate":"true",
                            "power":self.load_value1,
                            "zone_max":self.zone_max,
                            "zone_min":self.zone_min}

        if (device_name == 'AC2'):
            if (topic == 'house/'+ device_name +'/all'):
                now = datetime.datetime.now()
                timestamp = now.isoformat()
                self.load_value2 = round(message[0]['load(kW)'],2)
                self.energy_value2 = round(message[0]['Energy(kWH)'],2)
                self.device2_json = {
                            "efficiency":90,
                            "energy":self.energy_value2,
                            "name":device_name,
                            "participate":"true",
                            "power":self.load_value2,
                            "zone_max":self.zone_max,
                            "zone_min":self.zone_min}

       
        if (device_name == 'WH1'):
            if (topic == 'house/'+ device_name +'/all'):
                now = datetime.datetime.now()
                timestamp = now.isoformat()
                self.load_value3 = round(message[0]['load(kW)'],2)
                self.energy_value3 = round(message[0]['Energy(kWH)'],2)
                self.device3_json = {
                            "efficiency":45,
                            "energy":self.energy_value3,
                            "name":device_name,
                            "participate":"true",
                            "power":self.load_value3,
                            "zone_max":self.zone_max,
                            "zone_min":self.zone_min}

        energyPoints = [timestamp,self.energy_value1 + self.energy_value2 + self.energy_value3]
        self.energyDict['b'].append(energyPoints)
        if (len(self.energyDict['b']) == 10):
            del self.energyDict['b'][0]
            print("the first entry deleted")

        self.energyDataPlot = {
                            "data":self.energyDict['b'],
                            "type":"line",
                            "label":"energy"
        }
        
        # print( self.energyDataPlot)

        powerPoints = [timestamp,self.load_value1,self.load_value2,self.load_value3]
        self.powerDict['a'].append(powerPoints)
        # print(self.powerDict)
        if (len(self.powerDict['a']) == 10):
            del self.powerDict['a'][0]
            print("the first entry deleted")

        self.powerDataPlot = {
                            "data":self.powerDict['a'],
                            "type":"bar",
                            "label":"power"
        }
        # print(self.powerDataPlot)
        self.overall_energy = self.energy_value1 +self.energy_value2 +self.energy_value3
        self.overall_power = self.load_value1 +self.load_value2 +self.load_value3
        # time.sleep(5)
        self.ChangeTransactiveState(self.device1_json,self.device2_json,self.device3_json,self.overall_energy,self.overall_power, self.energyDataPlot, self.powerDataPlot)



    def ChangeTransactiveState(self,device1_json,device2_json,device3_json,overall_energy,overall_power,energyDataPlot, powerDataPlot):
        '''
            Turns on the switch.entityId device
        '''
        init_value = 0
        if entityId is None:
            return
        
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
                        "device":[
                        device1_json,
                        device2_json,
                        device3_json
                        ],
                        "friendly_name": "Transactive Home",  
                        "overallflexibility":[
                        {
                            "flexibility" : self.flexibility ,
                            "zone_max" : self.zone_max,
                            "zone_min" : self.zone_min
                        }]              
                    },
                    "state": self.new_state
                })
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



   
            