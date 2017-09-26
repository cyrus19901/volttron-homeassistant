import datetime
import logging
import sys
import gevent
import grequests
import json
import requests
import time
import csv
from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from . import settings
from volttron.platform.messaging import topics, headers as headers_mod
from calendar import timegm
from scipy.interpolate import interp1d
from cvxopt import matrix, solvers

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '3.0'
class GetTransactiveAgent(Agent):
    
    def __init__(self, config_path, **kwargs):
        '''
            Initializes the HASS Switch Agent for communicating with HASS API
            regarding switch components
        ''' 

        super(GetTransactiveAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self.entityId_device = self.config['entityID_device']
        self.entityId_transactive = self.config['entityID_transactive']
        self.url = self.config['url']
        self.data  = []
        self.data2  = []


    @Core.receiver('onstart')
    def GetDeviceData(self,sender, **kwargs):
        '''
            Get the current state for loaded components
            from Home Assistant API
        '''
        if len(self.entityId_device):
            for device in self.entityId_device:
                urlState = self.url+'states/'+device
                req = grequests.get(urlState)
                results = grequests.map([req])
                self.data = results[0].text
                dataObject = json.loads(self.data)
                deviceName = dataObject['entity_id']
                pub_topic_currentTemp = 'house/devices/'+deviceName+'/currentTemp'
                pub_topic_changedTemp = 'house/devices/'+deviceName+'/changedTemp'
                currentTemp = dataObject['attributes']['current_temperature']
                temperature = dataObject['attributes']['temperature']
                now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
                headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
                # print(pub_topic_currentTemp)
                # print(currentTemp)
                # print(pub_topic_changedTemp)
                # print(temperature)
                self.vip.pubsub.publish('pubsub',pub_topic_currentTemp,headers,currentTemp) 
                self.vip.pubsub.publish('pubsub',pub_topic_changedTemp,headers,temperature) 
        self.setWillingness()


    def setWillingness(self):   

        urlStates = self.url+'states'
        while True:
            req = grequests.get(urlStates)
            results = grequests.map([req])
            self.data2 = results[0].text
            dataObject = json.loads(self.data2)
            deviceName = dataObject[2]["attributes"]["devices"]
            advancedSettingSaving = dataObject[1]["attributes"]["energySavings"]["goal"]
            advancedSettingSavingEndtime = dataObject[1]["attributes"]["savingsEndTime"]
            advancedSettingSavingStarttime = dataObject[1]["attributes"]["savingsStartTime"]
            print("---------------------------------------------------------------------")
            print(advancedSettingSaving)
            print(advancedSettingSavingEndtime)
            print(advancedSettingSavingStarttime)
            gevent.sleep(5)
            # print(dataObject)
            for value in  dataObject[2]["attributes"]["devices"]:
                # print(value)
                flexibility = dataObject[2]["attributes"]["devices"][str(value)]["flexibility"]
                if (flexibility == "low"):
                    self.willingness = 8
                if (flexibility == "medium"):
                    self.willingness = 5
                if (flexibility == "high"):
                    self.willingness = 2
            self.data = results[0].text
            dataObject = json.loads(self.data)
            print(dataObject)
            # deviceName = dataObject[0]["attributes"]["devices"]
            time.sleep(5)
            for value in  dataObject[3]["attributes"]["devices"]:
                print(value)
                flexibility = dataObject[3]["attributes"]["devices"][str(value)]["flexibility"]
                if (flexibility == "low"):
                    self.willingness = 2
                if (flexibility == "medium"):
                    self.willingness = 5
                if (flexibility == "high"):
                    self.willingness = 8
                pub_topic = 'house/'+ value+'/'+value+'_beta'
                print("-----------------------------------------")
                print(pub_topic)
                print(self.willingness)
                now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
                headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
                self.vip.pubsub.publish('pubsub',pub_topic,headers,self.willingness)         
                self.vip.pubsub.publish('pubsub',pub_topic,headers,self.willingness)    
        
def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(GetTransactiveAgent,version=__version__)
    except Exception as e:
        print e
        _log.exception('unhandled exception')

if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass                 



   
            
