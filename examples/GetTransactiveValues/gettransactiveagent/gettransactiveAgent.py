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
class GetTransactiveAgent(Agent):
    
    def __init__(self, config_path, **kwargs):
        '''
            Initializes the HASS Switch Agent for communicating with HASS API
            regarding switch components
        ''' 

        super(GetTransactiveAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self.agentId = self.config['agentId']
        self.hassConfig = self.config['hassConfigPath']
        self.url = self.config['url']
        self.urlPass = self.config['urlPass']
        self.entityId = self.config['entityID'] 
        self.friendly_name = self.config['friendly_name']
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
        self.zone_max =1
        self.zone_min =0 
        self.new_state = self.config['state']
        self.request = self.config['request']
        self.data  = []


    @Core.receiver('onstart')
    def GetData(self,sender, **kwargs):
        '''
            Get the current state for loaded components
            from Home Assistant API
        '''
        urlStates = self.url+'states'
        while True:
            self.data = requests.get(urlStates).json()
            # data_json =  json.dumps(self.data)
            dataObject = json.loads(json.dumps(self.data))
            print(dataObject)
            for value in (dataObject[3]['attributes']['device']):
                pub_topic = 'house/'+ value['name']+'/'+value['name']+'_beta'
                print("--------------------------------------------------------------")
                print(pub_topic)
                now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
                headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
                self.vip.pubsub.publish('pubsub',pub_topic,headers,0.6)     
                time.sleep(5)


      

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



   
            