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
        self.entityId_climate_heatpump = 'climate.heatpump'

        self.entityId_energyEfficiencyPeakPeriod_component = 'energy_efficiency.peak_period_energy_and_compensation'
        self.entityId_user_settings_component = 'user_settings.user_settings'
        self.entityId_timeOfEnergyUseSaving = 'time_of_use.time_of_use_energy_and_savings'
        self.url = self.config['url']
        self.data  = []
        self.data2  = []
        self.new_state = self.config['state']

#Moving some from the transactive agent 
    @Core.periodic(1)
    def accessService(self):
        urlServices_energyEfficiencyPeakPeriod = self.url+'states/'+ self.entityId_energyEfficiencyPeakPeriod_component
        urlServices_timeOfUseEnergyUseSaving = self.url+'states/'+ self.entityId_timeOfEnergyUseSaving
        urlServices_user_settings = self.url+'states/'+ self.entityId_user_settings_component
        self.urlServices_transactive = self.url+'states/'+ self.entityId_connectedDevices_component 
        self.urlServices_advanced_settings = self.url+'states/'+ self.entityId_advancedSettings_component
        self.urlServices_user_settings = self.url+'states/'+ self.entityId_userSettings_component
        self.urlServices_climate_heatpump = self.url+'states/'+ self.entityId_climate_heatpump

        req_user_settings = grequests.get(urlServices_user_settings)
        results_user_settings = grequests.map([req_user_settings])
        data_user_settings = results_user_settings[0].text
        dataObject_user_sett = json.loads(data_user_settings)

        req_timeOfUse_saving = grequests.get(urlServices_timeOfUseEnergyUseSaving)
        results_timOfUse_saving = grequests.map([req_timeOfUse_saving])
        data_timeOfUse_saving = results_timOfUse_saving[0].text
        dataObject_timeOfUse_saving = json.loads(data_timeOfUse_saving)

        req_energyEfficiencyPeakPeriod = grequests.get(urlServices_energyEfficiencyPeakPeriod)
        results_energyEfficiencyPeakPeriod = grequests.map([req_energyEfficiencyPeakPeriod])
        data_energyEfficiencyPeakPeriod = results_energyEfficiencyPeakPeriod[0].text
        dataObject_energyEfficiency_peakPeriod = json.loads(data_energyEfficiencyPeakPeriod)

        #Peak Period
        self.compensationAcutal=dataObject_energyEfficiency_peakPeriod['attributes']['compensationActual']['value']
        self.compensationEstimate=dataObject_energyEfficiency_peakPeriod['attributes']['compensationEstimate']['value']
        self.compensationGoal=dataObject_energyEfficiency_peakPeriod['attributes']['compensationGoal']['value']
        self.energyReductionActual_peak=dataObject_energyEfficiency_peakPeriod['attributes']['energyReductionActual']['value']
        self.energyReductionEstimate_peak=dataObject_energyEfficiency_peakPeriod['attributes']['energyReductionEstimate']['value']
        self.energyReductionGoal_peak=dataObject_energyEfficiency_peakPeriod['attributes']['energyReductionGoal']['value']
        self.peakPeriodUseAlgorithm=dataObject_energyEfficiency_peakPeriod['attributes']['useAlgorithm']['value']

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
        self.ChangePeakPeriodEnergyCompensation(self.energyReductionActual_peak,self.energyReductionEstimate_peak,self.energyReductionGoal_peak,self.compensationAcutal,self.compensationEstimate,self.compensationGoal,self.peakPeriodUseAlgorithm)

    def sendDeviceFromHA(self):

        urlStates = self.urlServices_climate_heatpump
        req = grequests.get(urlStates)
        results = grequests.map([req])
        data = results[0].text
        dataObject = json.loads(data)
        devicename =(dataObject['attributes']['friendly_name'])
        pub_topic = 'devices/all/'+ devicename + '/office/skycentrics'
        now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
        headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
        self.vip.pubsub.publish('pubsub',pub_topic,headers,dataObject)         

    def sendDeviceList(self):   

        urlStates = self.urlServices_user_settings
        req = grequests.get(urlStates)
        results = grequests.map([req])
        data = results[0].text
        dataObject = json.loads(data)
        for value in dataObject["attributes"]["devices"]:
            settings = dataObject["attributes"]["devices"][str(value)]["settings"]
            pub_topic = 'house/device/details/'+ value

            now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
            headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
            self.vip.pubsub.publish('pubsub',pub_topic,headers,settings)         

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
            # print("-----------------------------------------")
            # print(willingness)
            now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
            headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
            self.vip.pubsub.publish('pubsub',pub_topic,headers,willingness)        
        

    def setEnergyReduction(self):   

        urlStates = self.urlServices_advanced_settings
        req = grequests.get(urlStates)
        results = grequests.map([req])
        data = results[0].text
        dataObject = json.loads(data)
        energyReduction = float(dataObject['attributes']['energySavings']['value'])
        pub_topic = 'house/energy_reduction'
        # print("-----------------------------------------")
        # print(energyReduction)
        now = datetime.datetime.utcnow().isoformat(' ') + 'Z'
        headers = {headers_mod.TIMESTAMP: now, headers_mod.DATE: now}
        self.vip.pubsub.publish('pubsub',pub_topic,headers,energyReduction)         

    def ChangePeakPeriodEnergyCompensation(self,energyReductionActual_peak,energyReductionEstimate_peak,energyReductionGoal_peak,compensationAcutal,compensationEstimate,compensationGoal,peakPeriodUseAlgorithm):

            if self.entityId_energyEfficiencyPeakPeriod_component is None:
                return

            urlServices = self.url+'states/'+ self.entityId_energyEfficiencyPeakPeriod_component
            try:

                jsonMsg = json.dumps({
                        "attributes": {
                           "friendly_name": "Peak Period Energy and Compensation",
                            "compensationActual": {
                                "value": compensationAcutal
                            },
                            "compensationEstimate": {
                                "value": compensationEstimate
                            },
                            "compensationGoal": {
                                "value": compensationGoal
                            },
                            "energyReductionActual": {
                                "units": "kwh",
                                "value": energyReductionActual_peak
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
                header = {'Content-Type': 'application/json'}
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
                header = {'Content-Type': 'application/json'}
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



   
            
