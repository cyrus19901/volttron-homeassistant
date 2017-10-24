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
record_topic = 'record/'
new_state ='on'
class TransactiveAgent(Agent):
    
    def __init__(self, config_path, **kwargs):
        '''
            Initializes the HASS Switch Agent for communicating with HASS API
            regarding switch components
        ''' 
        super(TransactiveAgent, self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self.url = self.config['url']
        self.deviceList = self.config['device_list']
        self.deviceDictionary={}
        self.energyPoint={}
        self.powerPoint={}
        self.devicePowerStausesDict ={}
        self.deviceEnergyStausesDict ={}
        for d in self.deviceList:
            self.deviceDictionary[d] = []
            self.devicePowerStausesDict[d] = []
            self.deviceEnergyStausesDict[d] = []
            self.energyPoint[d]=[]
            self.powerPoint[d]=[]
        self.startTime= datetime.datetime.utcnow()
        self.energyDevicesStatusesDict={'series':[],'times':[],'time-format': 'h:mm a'}
        self.powerDevicesStatusesDict={'series':[],'times':[],'time-format': 'h:mm a'}
        self.entityId_transactive_component = 'transactive_home.transactive_home'
        self.entityId_connectedDevices_component = 'connected_devices.connected_devices'
        self.entityId_wholeHouse_component = 'whole_house_energy.wholehouse_energy_use_and_cost'
        self.entityId_advancedSetting_component = 'advanced_settings.advanced_settings'
        self.entityId_deviceStatus_component = 'device_statuses.device_statuses'
        self.entityId_user_settings_component = 'user_settings.user_settings'
        self.new_state = self.config['state']
        self.count=0
        self.energyDict = {'series':[],'times':[]}
        energySeries = {'actual':[],'historical':[],'transactive':[]}
        energySeries['actual'] = { 'color':'#ffa450','label':'actual','line-style':'line','points':[]}
        energySeries['historical'] = { 'color':'#696969','label':'historical','line-style':'dash','points':[]}
        energySeries['transactive'] = { 'color':'#1b6630','label':'transactive','line-style':'dash','points':[]}
        self.energyDict['series']= energySeries
        now = datetime.datetime.now()
        future=now
        urlServices = self.url+'states/'+ self.entityId_connectedDevices_component
        for i in range(1,50):
            minute = timedelta(days=6,seconds=0,microseconds=0)
            future = future + minute
            self.energyDict['times'].append(future.isoformat())

        for i in range(1,50):
            self.energyDict['series']['actual']['points'].append(None)

        with open('/home/yingying/git/volttron/examples/TransactiveAgent/transactiveagent/data_set.json') as data_file: 
            data_historical = json.load(data_file)
            for i in data_historical['data']:
                self.energyDict['series']['transactive']['points'].append(float(i['kWh']))

        with open('/home/yingying/git/volttron/examples/TransactiveAgent/transactiveagent/Transactive_data.json') as data_file:   
            data_transactive = json.load(data_file)
            for i in data_transactive['data']:
                self.energyDict['series']['historical']['points'].append(float(i['kWh']))


# Initiate the json in the beginning of the code
        for device_list in self.deviceList:
            device_json = {
                    "energy":0,
                    "flexibility":"high",
                    "participate": True,
                    "power":0,
                    "reset":False,
                    "zone_max":1,
                    "zone_min":0
                    }
            self.deviceDictionary[device_list]= device_json
        self.reset_default = False
        jsonMsg = json.dumps({
                        "attributes": {
                            "devices": self.deviceDictionary,
                            "friendly_name":"Connected Devices",
                        },
                        "state": self.new_state
                    })
        header = {'Content-Type': 'application/json'}
        requests.post(urlServices, data = jsonMsg, headers = header)  

    @PubSub.subscribe('pubsub', '')
    def on_match_all(self, peer, sender, bus,  topic, headers, message):
        ''' This method subscibes to all topics. It simply prints out the 
        topic seen.
        # '''
        counter =1
        future=self.startTime
        future = future + timedelta(minutes=1)
        urlServices_transactive = self.url+'states/'+ self.entityId_transactive_component 
        urlServices_connected_devices = self.url+'states/'+ self.entityId_connectedDevices_component
        urlServices_advance_settings = self.url+'states/'+ self.entityId_advancedSetting_component
        urlServices_wholehouse_energy_useandcost = self.url+'states/'+ self.entityId_wholeHouse_component
        urlServices_user_settings = self.url+'states/'+ self.entityId_user_settings_component

        req_user_settings = grequests.get(urlServices_user_settings)
        results_user_settings = grequests.map([req_user_settings])
        data_user_settings = results_user_settings[0].text
        dataObject_user_sett = json.loads(data_user_settings)
        
        req_advanced_settings = grequests.get(urlServices_advance_settings)
        results_advanced_settings = grequests.map([req_advanced_settings])
        data_advanced_settings = results_advanced_settings[0].text
        dataObject_advanced_settings = json.loads(data_advanced_settings)

        req_wholehouse_energy_useandcost = grequests.get(urlServices_wholehouse_energy_useandcost)
        results_wholehouse_energy_useandcost = grequests.map([req_wholehouse_energy_useandcost])
        data_wholehouse_energy_useandcost = results_wholehouse_energy_useandcost[0].text
        dataObject_wholehouse_energy_useandcost = json.loads(data_wholehouse_energy_useandcost)
        
        req_connected_devices = grequests.get(urlServices_connected_devices)
        results_connected_devices = grequests.map([req_connected_devices])
        data_connected_devices = results_connected_devices[0].text
        dataObject_connected = json.loads(data_connected_devices)

        if ((datetime.datetime.utcnow()) >= future):
            totalEnergy = 0
            totalPower = 0
            zone_max=100
            zone_min =0
            device_name = topic.partition('/')[-1].rpartition('/')[0]

            with open('/home/yingying/git/volttron/examples/TransactiveAgent/config_devices') as device_file: 
                device_dictionary = json.load(device_file)
                print(device_dictionary)
            self.ChangeUserSettings(device_dictionary)

            if (topic == 'house/'+ device_name +'/all'):
                now = datetime.datetime.now()
                timestamp = now.isoformat()
                for device in  self.deviceList:
                    if (device == device_name):
                        load_value = round(message[0]['load(kW)'],2)
                        energy_value = round(message[0]['Energy(kWH)'],2)
                        self.energyPoint[str(device_name)].append(energy_value)
                        self.powerPoint[str(device_name)].append(load_value)
                        self.energyDevicesStatusesDict['times'].append(timestamp)
                        self.powerDevicesStatusesDict['times'].append(timestamp)
                        if (len(self.energyDevicesStatusesDict['times']) == 11):
                            del (self.energyDevicesStatusesDict['times'][0])
                        if (len(self.powerDevicesStatusesDict['times']) == 11):
                            del (self.powerDevicesStatusesDict['times'][0])
                    else :
                        load_value = float(dataObject_connected['attributes']['devices'][str(device)]['power'])
                        energy_value = float(dataObject_connected['attributes']['devices'][str(device)]['energy'])
                    flexibility = dataObject_connected['attributes']['devices'][str(device)]['flexibility']
                    participation = dataObject_connected['attributes']['devices'][str(device)]['participate']
                    reset = dataObject_connected['attributes']['devices'][str(device)]['reset']
#                     if (self.reset_default != reset):
#                         counter = 0
#                         print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
#                         print("the value has been changed for reset")
#                     self.reset_default = reset
# # Adding the section where the OPT out time is defined 
#                     if (reset==True && counter == 0):
#                         timeBeforeTransactive = datetime.datetime.now() + timedelta(days=0,seconds=20,minutes=0)
#                         if (reset == True and datetime.datetime.now() == timeBeforeTransactive)
#                             reset = False
#                             participation = True 
#                         counter = 1

                    device_json = {
                        "energy":energy_value,
                        "flexibility":flexibility,
                        "participate": participation,
                        "power":load_value,
                        "reset":reset,
                        "zone_max":zone_max,
                        "zone_min":zone_min
                        }
                    devicesEnergyStatus_json = {
                        "points": self.energyPoint[str(device_name)]
                        }
                    devicesPowerStatus_json = {
                        "points": self.powerPoint[str(device_name)]
                        }
                    self.devicePowerStausesDict[device_name] = devicesPowerStatus_json
                    self.deviceEnergyStausesDict[device_name] = devicesEnergyStatus_json
                    if (len(self.deviceEnergyStausesDict[device_name]) == 11):
                        del (self.deviceEnergyStausesDict[device_name][0])
                    if (len(self.devicePowerStausesDict[device_name]) == 11):
                        del (self.devicePowerStausesDict[device_name][0])
                    self.energyDevicesStatusesDict['series']= self.deviceEnergyStausesDict
                    self.powerDevicesStatusesDict['series']= self.devicePowerStausesDict
                    self.deviceDictionary[device]= device_json
                    totalEnergy += energy_value
                    totalPower += load_value
                self.ChangeDeviceStatuses(self.energyDevicesStatusesDict,self.powerDevicesStatusesDict)
                self.ChangeConnectedDevicesState(self.deviceDictionary)
                if (self.energyDict['series']['actual']['points'][self.count] == None):
                    self.energyDict['series']['actual']['points'][self.count] =round(totalEnergy,2)
                    self.energyDict['series']['transactive']['points'][self.count] =round(totalEnergy,2)
                    print("the first entry deleted")
                energyDataPlot = {
                    "series":self.energyDict['series'],
                    "time-format": "MM/DD",
                    "times":self.energyDict['times']
                } 
                if (self.count == 50):
                    self.count=0
                self.count = self.count + 1
                gevent.sleep(10)
                self.ChangeTransactiveState(round(totalEnergy,2),round(totalPower,2),energyDataPlot,flexibility,zone_max,zone_min)
                self.startTime =datetime.datetime.utcnow()

        powerSavingValue = dataObject_advanced_settings['attributes']['powerSavings']['value']
        energySavingValue = dataObject_advanced_settings['attributes']['energySavings']['value']
        savingStartTime = dataObject_advanced_settings['attributes']['savingsStartTime']
        savingEndTime = dataObject_advanced_settings['attributes']['savingsEndTime']
        timePeriodStart = dataObject_advanced_settings['attributes']['timePeriodStart']
        timePeriodEnd = dataObject_advanced_settings['attributes']['timePeriodEnd']
        incentives = dataObject_advanced_settings['attributes']['incentives']['value']
        self.ChangeAdvancedSettings(powerSavingValue,energySavingValue,savingStartTime,savingEndTime,timePeriodStart,timePeriodEnd,incentives)

        energyCost_transactive=dataObject_wholehouse_energy_useandcost['attributes']['energyCost']['transactive']
        energyCost_maximum=dataObject_wholehouse_energy_useandcost['attributes']['energyCost']['maximum']
        energyCost_mimimum=dataObject_wholehouse_energy_useandcost['attributes']['energyCost']['minimum']
        energyUse_maximum=dataObject_wholehouse_energy_useandcost['attributes']['energyUse']['maximum']
        energyUse_minimum=dataObject_wholehouse_energy_useandcost['attributes']['energyUse']['minimum']
        energyUse_transactive=dataObject_wholehouse_energy_useandcost['attributes']['energyUse']['transactive']
        if (topic == 'fncs/input/house/energy_reduction'):
            energyUse_transactive=str(float(round(message,2)))
        if (topic == 'fncs/input/house/minimum_disutility'):
            energyCost_transactive = "$"+str(float(round(message,2)))
        self.ChangeWholeHouseEnergyState(energyCost_maximum,energyCost_mimimum,energyCost_transactive,energyUse_maximum,energyUse_minimum,energyUse_transactive,energySavingValue)


    def ChangeTransactiveState(self,overall_energy,overall_power,energyDataPlot,flexibility,zone_max,zone_min):

        if self.entityId_transactive_component is None:
            return
        
        urlServices = self.url+'states/'+ self.entityId_transactive_component
        try:
            jsonMsg = json.dumps({
                    "attributes": {
                        "chartSeries":[{
                            "data": energyDataPlot,
                            "type": "line",
                            "label": "Energy (Kwh)",
                            "id": "transactive-home"
                        }
                        ],
                        "friendly_name": "Transactive Home",
                        "measures":[
                        {
                            "label":"Overall Energy",
                            "unit":"kwh",
                            "value":overall_energy
                        },
                        {
                            "label":"Overall Power",
                            "unit":"kw",
                            "value":overall_power                           
                        }],
                        "friendly_name": "Transactive Home",  
                        "overallflexibility":[
                        {
                            "flexibility" : flexibility,
                            "zone_max" : zone_max,
                            "zone_min" : zone_min
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
            header = {'Content-Type': 'application/json'}
            requests.post(urlServices, data = jsonMsg, headers = header)
            print("Transactive State has been changed")
        except ValueError:
                pass

    def ChangeConnectedDevicesState(self,device_json):

            if self.entityId_connectedDevices_component is None:
                return
            
            urlServices = self.url+'states/'+ self.entityId_connectedDevices_component
            try:
                jsonMsg = json.dumps({
                        "attributes": {
                            "devices": device_json,
                            "friendly_name":"Connected Devices",
                        },
                        "state": self.new_state
                    })
                header = {'Content-Type': 'application/json'}
                requests.post(urlServices, data = jsonMsg, headers = header)
                print("Connected Devices State has been changed")
            except ValueError:
                    pass

    def ChangeDeviceStatuses(self,energyDevicesStatusesDict,powerDevicesStatusesDict):
            
            if self.entityId_deviceStatus_component is None:
                return
            
            urlServices = self.url+'states/'+ self.entityId_deviceStatus_component
            try:
                jsonMsg = json.dumps({
                        "attributes": {
                            "chartSeries":[{
                                "data":energyDevicesStatusesDict,
                                "id":"device-energy",
                                "label":"Energy (Kwh)",
                                "type":"bar",
                                "updateMethod":"update_chart_type"
                                },
                                {
                                "data":powerDevicesStatusesDict,
                                "id":"device-power",
                                "label":"Power (Kw)",
                                "type":"bar",
                                "updateMethod":"update_chart_type"
                            }],
                            "friendly_name":"Device Statuses",
                        },
                        "state": self.new_state
                    })
                header = {'Content-Type': 'application/json'}
                requests.post(urlServices, data = jsonMsg, headers = header)
                print(" Devices Statuses State has been changed")
            except ValueError:
                    pass

    def ChangeAdvancedSettings(self,powerSavingValue,energySavingValue,savingStartTime,savingEndTime,timePeriodStart,timePeriodEnd,incentives):

            if self.entityId_advancedSetting_component is None:
                return
            
            urlServices = self.url+'states/'+ self.entityId_advancedSetting_component
            try:
                jsonMsg = json.dumps({
                        "attributes": {
                             "powerSavings": {
                                "units": "Kw",
                                "value": powerSavingValue,
                                "label":"1"
                            },
                            "savingsEndTime":savingEndTime,
                            "incentives": {
                                "units": "$ per peak period",
                                "value": incentives,
                                "label": "Incentives"
                            },
                            "savingsStartTime":savingStartTime,
                            "timePeriodStart" : timePeriodStart,
                            "friendly_name":"Advanced Settings",
                            "time_of_use_pricing": {
                                "label":"Time of use pricing",
                                "list": [{
                                    "units": "cents per",
                                    "endTime": "17:00 pm",
                                    "value": 15,
                                    "startTime": "10:00 am"
                                }, {
                                    "units": "cents per",
                                    "endTime": "20:00 pm",
                                    "value": 35,
                                    "startTime": "17:00 am"
                                }, {
                                    "units": "cents per",
                                    "endTime": "9:00 am",
                                    "value": 10,
                                    "startTime": "20:00 pm"
                                }],
                            },
                            "timePeriodEnd":timePeriodEnd,
                            "energySavings": {
                                "units": "Kwh",
                                "value": energySavingValue,
                                "label":""
                            },
                        },
                        "state": self.new_state
                    })
                header = {'Content-Type': 'application/json'}
                requests.post(urlServices, data = jsonMsg, headers = header)
                print("Advanced Setting State has been changed")
            except ValueError:
                    pass
    def ChangeUserSettings(self,device_dictionary):

            if self.entityId_user_settings_component is None:
                return
            
            urlServices = self.url+'states/'+ self.entityId_user_settings_component
            try:
                jsonMsg = json.dumps({
                        "attributes":device_dictionary,
                        "state": self.new_state
                    })
                header = {'Content-Type': 'application/json'}
                # requests.post(urlServices, data = jsonMsg, headers = header)
                # print("Advanced Setting State has been changed")
            except ValueError:
                    pass


    def ChangeWholeHouseEnergyState(self,energyCost_maximum,energyCost_mimimum,energyCost_transactive,energyUse_maximum,energyUse_minimum,energyUse_transactive,energySavingValue):

            if self.entityId_wholeHouse_component is None:
                return

            urlServices = self.url+'states/'+ self.entityId_wholeHouse_component
            try:
                jsonMsg = json.dumps({
                        "attributes": {
                            "friendly_name": "Whole-house energy use and cost",
                            "energyCost":{
                                "maximum":energyCost_maximum,
                                "minimum":energyCost_mimimum,
                                "transactive":energyCost_transactive
                            },
                            "energyUse":{
                                "maximum":str(energySavingValue),
                                "minimum":energyUse_minimum,
                                "transactive":energyUse_transactive
                            }
                        },
                        "state": self.new_state
                    })
                header = {'Content-Type': 'application/json'}
                requests.post(urlServices, data = jsonMsg, headers = header)
                print("Whole house energy state has been changed")
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



   
