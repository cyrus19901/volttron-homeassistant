import datetime
import logging
import sys
import json
import requests
import json
import time
import csv
import gevent
import grequests
from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from . import settings
from volttron.platform.messaging import topics, headers as headers_mod
from datetime import timedelta
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
        self.entityId_advancedSettings_component = 'advanced_settings.utility_settings'
        self.entityId_userSettings_component = 'user_settings.device_settings'
        self.entityId_climate_heatpump = 'climate.heatpump'
        self.entityId_energyEfficiencyPeakPeriod_component = 'energy_efficiency.peak_period_energy_and_compensation'
        self.entityId_timeOfEnergyUseSaving = 'time_of_use.time_of_use_energy_and_savings'
        self.url = self.config['url']
        self.data  = []
        self.data2  = []
        self.new_state = self.config['state']

#Moving some from the transactive agent 
    @Core.periodic(1)
    def accessService(self):

        urls = [
        self.url+'states/'+ self.entityId_transactive_component,
        self.url+'states/'+ self.entityId_connectedDevices_component,
        self.url+'states/'+ self.entityId_advancedSettings_component,
        self.url+'states/'+ self.entityId_energyEfficiencyPeakPeriod_component,
        self.url+'states/'+ self.entityId_timeOfEnergyUseSaving,
        self.url+'states/'+ self.entityId_userSettings_component,
        self.url+'states/'+ self.entityId_climate_heatpump
        ]
        header = {'Content-Type': 'application/json' ,'x-ha-access':'admin'}
        request_data = (grequests.get(u, headers= header) for u in urls)
        response = grequests.map(request_data)
        self.dataObject_transactive = json.loads(response[0].text)
        self.dataObject_connected = json.loads(response[1].text)
        self.dataObject_advanced_settings = json.loads(response[2].text)
        self.dataObject_energyEfficiency_peakPeriod = json.loads(response[3].text)
        self.dataObject_timeOfUse_saving = json.loads(response[4].text)
        self.dataObject_user_sett = json.loads(response[5].text)
        self.dataObject_heat_pump = json.loads(response[6].text)


        #Peak Period
        # print(self.dataObject_energyEfficiency_peakPeriod)
        # self.compensationAcutal=dataObject_energyEfficiency_peakPeriod['attributes']['compensationActual']['value']
        self.compensationEstimate=self.dataObject_energyEfficiency_peakPeriod['attributes']['compensationEstimate']['value']
        self.compensationGoal=self.dataObject_energyEfficiency_peakPeriod['attributes']['compensationGoal']['value']
        # self.energyReductionActual_peak=dataObject_energyEfficiency_peakPeriod['attributes']['energyReductionActual']['value']
        self.energyReductionEstimate_peak=self.dataObject_energyEfficiency_peakPeriod['attributes']['energyReductionEstimate']['value']
        self.energyReductionGoal_peak=self.dataObject_energyEfficiency_peakPeriod['attributes']['energyReductionGoal']['value']
        self.peakPeriodUseAlgorithm=self.dataObject_energyEfficiency_peakPeriod['attributes']['useAlgorithm']['value']

        self.setWillingness()
        self.setEnergyReduction()
        self.sendDeviceList()
        self.sendDeviceFromHA()
        try:
            self.vip.pubsub.subscribe(peer='pubsub', prefix='fncs/input/house/', 
                                     callback=self.on_match_all)
        except:
            _log.debug("Topic Not found for enery_reduction or minimum disutility")

    def on_match_all(self, peer, sender, bus,  topic, headers, message):
        print("=======Inside Match All=============")

        if (topic == 'fncs/input/house/energy_reduction'):
            print("============PEAK PERIOD=============================")
            self.energyReductionEstimate_peak=str(float(round(message,2)))
            print(self.energyReductionEstimate_peak)

        if (topic == 'fncs/input/house/minimum_disutility'):
            print("============ENERGY REDUCTION=============================")
            self.compensationEstimate = "$"+str(float(round(message,2)))
            print(self.compensationEstimate)
        self.ChangePeakPeriodEnergyCompensation(self.energyReductionEstimate_peak,self.energyReductionGoal_peak,self.compensationEstimate,self.compensationGoal,self.peakPeriodUseAlgorithm)

    def sendDeviceFromHA(self):

        devicename =(self.dataObject_heat_pump['attributes']['friendly_name'])
        pub_topic = 'devices/all/'+ devicename + '/office/skycentrics'
        now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
        headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
        self.vip.pubsub.publish('pubsub',pub_topic,headers,self.dataObject_heat_pump)         

    def sendDeviceList(self):   

        for value in self.dataObject_user_sett["attributes"]["devices"]:
            settings = self.dataObject_user_sett["attributes"]["devices"][str(value)]["settings"]
            pub_topic = 'house/device/details/'+ value

            now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
            headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
            self.vip.pubsub.publish('pubsub',pub_topic,headers,settings)         

    def setWillingness(self):   

        for value in  self.dataObject_connected["attributes"]["devices"]:

            flexibility = self.dataObject_connected["attributes"]["devices"][str(value)]["flexibility"]
            if (flexibility == "low"):
                willingness = 8
            if (flexibility == "medium"):
                willingness = 5
            if (flexibility == "high"):
                willingness = 2
            pub_topic = 'house/'+ value+'/'+value+'_beta'
            # print("-----------------------------------------")
            # print(willingness)
            now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
            headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
            self.vip.pubsub.publish('pubsub',pub_topic,headers,willingness)        
        

    def setEnergyReduction(self):   

        energyReduction = float(self.dataObject_advanced_settings['attributes']['energySavings']['value'])
        pub_topic = 'house/energy_reduction'
        # print("-----------------------------------------")
        # print(energyReduction)
        now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
        headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
        self.vip.pubsub.publish('pubsub',pub_topic,headers,energyReduction)         

    def ChangePeakPeriodEnergyCompensation(self,energyReductionEstimate_peak,energyReductionGoal_peak,compensationEstimate,compensationGoal,peakPeriodUseAlgorithm):

            if self.entityId_energyEfficiencyPeakPeriod_component is None:
                return

            urlServices = self.url+'states/'+ self.entityId_energyEfficiencyPeakPeriod_component
            try:

                jsonMsg = json.dumps({
                        "attributes": {
                           "friendly_name": "Peak Period Energy and Compensation",
                            "compensationEstimate": {
                                "value": compensationEstimate
                            },
                            "compensationGoal": {
                                "value": compensationGoal
                            },
                            "energyReductionEstimate": {
                                "units": "kwh",
                                "value": energyReductionEstimate_peak
                            },
                            "energyReductionGoal": {
                                "units": "kwh",
                                "value": energyReductionGoal_peak
                            },
                            "useAlgorithm": {
                                "value": peakPeriodUseAlgorithm
                            }
                        },
                        "state": self.new_state
                    })
                # print(jsonMsg)
                header = {'Content-Type': 'application/json' ,'x-ha-access':'admin'}
                requests.post(urlServices, data = jsonMsg, headers = header)
                print("Energy efficiency for peak period has been changed")
            except ValueError:
                    pass


    def ChangeTimeOfUseEnergyAndSavings(self,energyReductionActual_timeOfUse,energyReductionEstimate_timeOfUse,energyReductionGoal_timeOfUse,savingsActual,savingsEstimate,savingsGoal,timeOfUseUseAlgorithm):

            if self.entityId_timeOfEnergyUseSaving is None:
                return

            urlServices = self.url+'states/'+ self.entityId_timeOfEnergyUseSaving
            try:
                jsonMsg = json.dumps({
                        "attributes": {
                            "energyReductionActual": {
                                "units": "kwh",
                                "value": energyReductionActual_timeOfUse
                            },
                            "energyReductionEstimate": {
                                "units": "kwh",
                                "value": energyReductionEstimate_timeOfUse
                            },
                            "energyReductionGoal": {
                                "units": "kwh",
                                "value": energyReductionGoal_timeOfUse
                            },
                            "friendly_name": "Time of use energy and savings",
                            "savingsActual": {
                                "value": savingsActual
                            },
                            "savingsEstimate": {
                                "value": savingsEstimate
                            },
                            "savingsGoal": {
                                "value": savingsGoal
                            },
                            "useAlgorithm": {
                                "value": timeOfUseUseAlgorithm
                            }
                        },
                        "state": self.new_state
                    })
                header = {'Content-Type': 'application/json' ,'x-ha-access':'admin'}
                # print(jsonMsg)
                requests.post(urlServices, data = jsonMsg, headers = header)
                print("Energy efficiency for peak period has been changed")
            except ValueError:
                    pass

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



   
            
