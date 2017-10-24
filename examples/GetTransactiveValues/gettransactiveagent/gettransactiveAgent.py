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
# from scipy.interpolate import interp1d
# from cvxopt import matrix, solvers

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
        self.device_list = self.config['device_list']
        # self.entityId_transactive_component = self.config['entityID_transactive']
        self.entityId_transactive_component = 'transactive_home.transactive_home'
        self.entityId_connectedDevices_component = 'connected_devices.connected_devices'
        self.entityId_advancedSettings_component = 'advanced_settings.advanced_settings'
        self.entityId_userSettings_component = 'user_settings.user_settings'
        self.url = self.config['url']
        self.data  = []
        self.data2  = []


    @Core.receiver('onstart')
    def GetDeviceData(self,sender, **kwargs):
        '''
            Get the current state for loaded components
            from Home Assistant API
        '''
        self.urlServices_transactive = self.url+'states/'+ self.entityId_connectedDevices_component 
        self.urlServices_advanced_settings = self.url+'states/'+ self.entityId_advancedSettings_component
        self.urlServices_user_settings = self.url+'states/'+ self.entityId_userSettings_component
        while True:
            self.setWillingness()
            self.setEnergyReduction()
            self.sendDeviceList()
        

    def sendDeviceList(self):   

        urlStates = self.urlServices_user_settings
        req = grequests.get(urlStates)
        results = grequests.map([req])
        data = results[0].text
        dataObject = json.loads(data)
        for value in dataObject["attributes"]["devices"]:
            settings = dataObject["attributes"]["devices"][str(value)]["settings"]
            pub_topic = 'house/device/details/'+ value
            print("-----------------------------------------")
            print(pub_topic)
            print(settings)
            now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
            headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
            self.vip.pubsub.publish('pubsub',pub_topic,headers,settings)         
        gevent.sleep(5) 

    def setWillingness(self):   

        urlStates = self.urlServices_transactive
        req = grequests.get(urlStates)
        results = grequests.map([req])
        data = results[0].text
        dataObject = json.loads(data)
        for value in  dataObject["attributes"]["devices"]:
            flexibility = dataObject["attributes"]["devices"][str(value)]["flexibility"]
            if (flexibility == "low"):
                willingness = 8
            if (flexibility == "medium"):
                willingness = 5
            if (flexibility == "high"):
                willingness = 2
            pub_topic = 'house/'+ value+'/'+value+'_beta'
            print("-----------------------------------------")
            print(pub_topic)
            print(willingness)
            now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
            headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
            self.vip.pubsub.publish('pubsub',pub_topic,headers,willingness)        
        gevent.sleep(5) 
        

    def setEnergyReduction(self):   

        urlStates = self.urlServices_advanced_settings
        req = grequests.get(urlStates)
        results = grequests.map([req])
        data = results[0].text
        dataObject = json.loads(data)
        energyReduction = float(dataObject['attributes']['energySavings']['value'])
        pub_topic = 'house/energy_reduction'
        print("-----------------------------------------")
        print(pub_topic)
        print(energyReduction)
        now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
        headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
        self.vip.pubsub.publish('pubsub',pub_topic,headers,energyReduction)         
        gevent.sleep(5) 



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



   
            
