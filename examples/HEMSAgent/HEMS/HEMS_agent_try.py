import datetime
import logging
import sys
import uuid
import math

from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod

from volttron.platform.messaging import topics, headers as headers_mod

from cvxopt import matrix, solvers

utils.setup_logging()
_log = logging.getLogger(__name__)
__version__ = '0.1'

def DatetimeFromValue(ts):
    ''' Utility for dealing with time
    '''
    if isinstance(ts, (int, long)):
        return datetime.utcfromtimestamp(ts)
    elif isinstance(ts, float):
        return datetime.utcfromtimestamp(ts)
    elif not isinstance(ts, datetime):
        raise ValueError('Unknown timestamp value')
    return ts

def HEMS_agent_try(config_path, **kwargs):

    config = utils.load_config(config_path)
    device_config = config['device']['units']
    house = config['device']['house']
    device_dict = {}
    device_topic_dict = {}
    device_setpoint_dict = {}
    device_setpoint_val_dict = {}
    device_setpoint_val_ori_dict = {}
    device_load_topic_dict = {}
    device_load_val_dict = {}
    device_energy_dict = {}
   
    for device_name in device_config:
        # setpoints topic
        setpointName = device_config[device_name][0]
        setpoint_topic = 'fncs/output/devices/fncs_Test/' + house + '/all'
        device_setpoint_dict.update({device_name: setpointName})
        device_setpoint_val_dict.update({device_name: 0.0})
        device_setpoint_val_ori_dict.update({device_name: 0.0})
        
        # Load topic full path
        loadName = device_config[device_name][1]
        load_topic = 'fncs/output/devices/fncs_Test/' + device_name + '/' + loadName
        device_load_topic_dict.update({device_name: load_topic})
        device_load_val_dict.update({device_name: 0.0})
        
        # Intialize device energy consumption
        device_energy_dict.update({device_name: 0.0})
        
    agent_id = config.get('agentid', 'HEMS_agent')

    class HEMS_agent_test(Agent):
        '''This agent is used to adjsust setpoint of appliances so that
        minimum disutility price can be achieved. 
        '''
    
        def __init__(self, **kwargs):
            super(HEMS_agent_test, self).__init__(**kwargs)
    
        @Core.receiver('onsetup')
        def setup(self, sender, **kwargs):
            self._agent_id = config['agentid']
        
        @Core.receiver('onstart')            
        def startup(self, sender, **kwargs):
            # Initialize subscription function to change setpoints
            _log.info('Subscribing to ' + setpoint_topic)
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix=setpoint_topic,
                                      callback=self.on_receive_setpoint_message_fncs)
            
            # Initialize subscription function to record current loads from appliances
            self.loadChangeTime = {}
            self.energyCalculated = {}
            for device_name in device_load_topic_dict:
                _log.info('Subscribing to ' + device_load_topic_dict[device_name])
                self.vip.pubsub.subscribe(peer='pubsub',
                                          prefix=device_load_topic_dict[device_name],
                                          callback=self.on_receive_load_message_fncs)
                self.loadChangeTime[device_name] = datetime.datetime.now()
                self.energyCalculated[device_name] = False
            
            #Set energy consumption time starts at 30 minutes after simulation begins, and lasts for 30 minutes
            self.startEnergyReduction = datetime.datetime.now() + datetime.timedelta(minutes=30)
            self.endEnergyReduction = datetime.datetime.now() + datetime.timedelta(minutes=60)
            _log.info('Energy reduction starts from: {}.'.format(str(self.startEnergyReduction)))
            _log.info('Energy reduction ends at: {}.'.format(str(self.endEnergyReduction)))
                        
        def on_receive_setpoint_message_fncs(self, peer, sender, bus, topic, headers, message):
            """Subscribe to appliance setpoint and change the data accordingly 
            """    
            _log.info("Whole message", topic, message)
            #The time stamp is in the headers
            _log.info('Date', headers['Date'])
            # Find the appliance name
            device = topic.split("/")[-2]
            # Obtain the current setpoint from the message for each device
            for device_name in device_config:
                try:
                    setpoint = message[0][device_name]
                    device_setpoint_val_dict.update({device_name: setpoint})
                except Exception as e:
                    _log.exception('Topic:%s is not given in Message at the begining of the simulation\n'%(device_name, message))

        @Core.periodic(60)
        def change_setpoints(self):
            ''' This method publishes updated setpoint when the energy reduction starts
            '''            
            # Check if energy reduction time arrives
            if (self.energyReduced == False) and (datetime.datetime.now() >= self.startEnergyReduction):
                _log.info("At time %s energy reduction begins" %str(datetime.datetime.now()))
                self.energyReduced = True
                self.energy_reduction()
            
            # CHeck if energy reduction time ends
            if datetime.datetime.now() >= self.endEnergyReduction:
                index = 0
                for device_name in device_setpoint_dict:
                    # Publish the original setpoints:
                    pub_topic = 'fncs/input/house/' + device_setpoint_dict[device_name]
                    self.vip.pubsub.publish('pubsub', pub_topic, headers, device_setpoint_val_ori_dict[device_name])
                    index += 1 
                    # Also update final energy consumption values
                    load_curr = device_load_val_dict[device_name]
                    energy_ori = device_energy_dict[device_name]
                    energy_update = energy_ori + load_curr * (self.endEnergyReduction - self.loadChangeTime[device_name]) / 3600
                    device_energy_dict.update({device_name: energy_update})
                    _log.info('unit %s total energy consumption is %f'%(device_name, device_energy_dict[device_name]))
          
        def on_receive_load_message_fncs(self, peer, sender, bus, topic, headers, message):
            """Subscribe to appliance loads and record the load data accordingly 
            """               
            # Find the appliance name
            device_name = topic.split("/")[-2]
            _log.info('unit %s changes load at time %s'%(device_name, str(datetime.datetime.now())))
            
            # Check if energy consumption calculation starts
            if (datetime.datetime.now() >= self.startEnergyReduction) and (datetime.datetime.now() <= self.endEnergyReduction):
                load_curr = device_load_val_dict[device_name]
                energy_ori = device_energy_dict[device_name]
                if (self.loadChangeTime[device_name] < self.startEnergyReduction): 
                    energy_update = energy_ori + load_curr * (datetime.datetime.now() - self.startEnergyReduction) / 3600
                else:
                    energy_update = energy_ori + load_curr * (datetime.datetime.now() - self.loadChangeTime[device_name]) / 3600
                device_energy_dict.update({device_name: energy_update})
                
            # Update device load (kW)
            device_load_val_dict.update({device_name: message[0]})
            self.loadChangeTime[device_name] = datetime.datetime.now()

        def energy_reduction(self): 
            
            lambda_E = 0.5
            beta_1 = 9.0
            beta_2 = 12.0
            beta_3 = 6
            
            P_total = 2
            
            P_rec1_max = float(55.181/(3.6*10)/3)
            P_rec2_max = float(42.646/(3.6*10)/3)
            P_rec3_max = float(46.376/(3.6*10)/3)
            
            Coefficient_1 = 692074/(3.6*math.pow(10,6))
            Coefficient_2 = 721164/3.6*math.pow(10,6)
            Coefficient_3 = 470545/3.6*math.pow(10,6)
            
            # solve the optimization problem
            P = matrix([[float(6*beta_1), 0.0, 0.0], [0.0, float(6*beta_2), 0.0], [0.0, 0.0, float(6*beta_3)]])
            q = matrix([-lambda_E, -lambda_E, -lambda_E])
            G = matrix([[-1.0, 1.0, 0.0, 0.0, 0.0, 0.0], [0.0, 0.0, -1.0, 1.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0, -1.0, 1.0]])
            h = matrix([0, P_rec1_max, 0, P_rec2_max, 0, P_rec3_max])
            A = matrix([3.0, 3.0, 3.0], (1, 3))
            b = matrix(2.0)
            sol = solvers.qp(P,q,G,h,A,b)
#             print(sol['x'])
            
            index = 0
            for device_name in device_setpoint_dict:
                setpoint = device_setpoint_val_dict[device_name]
                diff = sol['x'][index]*3/Coefficient_1
                device_setpoint_val_ori_dict.update({device_name: setpoint})
                device_setpoint_val_dict.update({device_name: setpoint + diff})
                # Publish the changed setpoints:
                pub_topic = 'fncs/input/house/' + device_setpoint_dict[device_name]
                self.vip.pubsub.publish('pubsub', pub_topic, headers, setpoint + diff)
                index += 1           
                
    Agent.__name__ = 'HEMSAgent'    
    return HEMS_agent_test(**kwargs)
              
def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(HEMS_agent_try)
    except Exception as e:
        print e
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
   
            
            