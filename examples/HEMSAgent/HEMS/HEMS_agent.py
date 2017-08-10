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

def HEMS_agent(config_path, **kwargs):

    config = utils.load_config(config_path)
    device_config = config['device']['unit']
    campus_building_config = config['device']
    campus_building = dict((key, campus_building_config[key]) for key in ['campus', 'building'])
    campus=campus_building.get('campus')
    building=campus_building.get('building') 
    device_dict = {}
    device_topic_dict = {}
    device_setpoint_dict = {}
   
    for device_name in device_config:
        # device topic
        device_topic = 'devices/' + campus + '/' + building + '/' + device_name + '/all'
        device_topic_dict.update({device_topic: device_name})
        # device full path name
        device = campus + '/' + building + '/' + device_name
        device_dict.update({device: device_name})
        # Initialize device setpoint
        device_setpoint_dict.update({device_name: 999.0})
    
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
            # Initialize subscription functions
#             for device_topic in device_topic_dict:
#                 _log.debug('Subscribing to ' + device_topic)
#                 self.vip.pubsub.subscribe(peer='pubsub',
#                                           prefix=device_topic,
#                                           callback=self.on_receive_message)
                
            # Try only one appliance
            _log.info('Subscribing to ' + device_topic)
            self.vip.pubsub.subscribe(peer='pubsub',
                                      prefix='devices/pnnl/isb1/AC1/all',
                                      callback=self.on_receive_message)
            
            # Test FNCS bridge
#             _log.debug('Subscribing to ' + 'fncs/output/devices/fncsPlayer/all')
#             self.vip.pubsub.subscribe(peer='pubsub',
#                                       prefix='fncs/output/devices/fncsPlayer/all',
#                                       callback=self.on_receive_message_fncs)
            
            # Test historian agent
#             topic_tmpl = "analysis/{campus}/{building}/{unit}"
#             topic1 = topic_tmpl.format(campus=campus,
#                                       building=building,
#                                       unit='AC1')
#             T_coeffs = [1,2,3,4,5]
#             P_coeffs = [10,20,30,40,50]
#             # Create timestamp
#             now = datetime.datetime.utcnow().isoformat(' ')
#             headers = {headers_mod.DATE: now}
#             for idx in xrange(0,2):
#                 T_topic = "T_c" + str(idx)
#                 P_topic = "Q_c" + str(idx)
#                 self.vip.pubsub.publish(
#                     'pubsub', topic1, headers, {T_topic: T_coeffs[idx]})
#                 self.vip.pubsub.publish(
#                     'pubsub', topic1, headers, {P_topic: P_coeffs[idx]})
#             
#             # Check if historian data exists
#             result = self.vip.rpc.call('platform.historian',
#                                            'query',
#                                            topic=topic1[9:] + '/' + T_topic,
#                                            count=2,
#                                            order="LAST_TO_FIRST").get(timeout=1000)
#             print (result)
             
        def on_receive_message(self, peer, sender, bus, topic, headers, message):
            """Subscribe to appliance data and print the data 
            """    
            _log.info("Whole message", topic, message)
            #The time stamp is in the headers
            _log.info('Date', headers['Date'])
            # Find the appliance name
            device = topic.split("/")[-2]
            # Obtain the current setpoint from the message
            setpoint = message[0]['setpoint']
            # Obtain the current temperature from the message
            temperature = message[0]['temperature']
            # Check if need to change setpoint
            # Only change appliance setpoint the first time receiving message from that appliance
            if device_setpoint_dict[device] == 999.0:            
            # Do optimization to find the setpoint
                delta_setpoint = self.energy_reduction(device)
            # Publish the setpoint based on optimization results
                self.use_rpc(setpoint + delta_setpoint, device)
        
        def on_receive_message_fncs(self, peer, sender, bus, topic, headers, message):
            """Subscribe to appliance data and print the data 
            """    
            _log.info("Whole message", topic, message)
            #The time stamp is in the headers
            _log.info('Date', headers['Date'])

        def energy_reduction(self, devicename): 
            
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
            print(sol['x'])
            
            if devicename == 'AC1':
                res = sol['x'][0]*3/Coefficient_1
            elif devicename == 'AC2':
                res = sol['x'][1]*3/Coefficient_2
            elif devicename == 'WH1':
                res = sol['x'][2]*3/Coefficient_3
                
            return res
            
            
        def use_rpc(self, setpointVal, device):
            
            msg_device = campus + '/' + building + '/' + device
            
            try: 
                start = str(datetime.datetime.now())
                end = str(datetime.datetime.now() + datetime.timedelta(minutes=1))
                   
                msg = [
                   [msg_device,start,end]
                   ]
                taskName = 'task_setpoint_' + device
                result = self.vip.rpc.call(
                                           'platform.actuator', 
                                           'request_new_schedule',
                                           agent_id, 
                                           taskName,
                                           'LOW',
                                           msg).get(timeout=10)
                _log.info("schedule result", result)
            except Exception as e:
                print ("Could not contact actuator. Is it running?")
                print(e)
             
            try:
                if result['result'] == 'SUCCESS':
                    result = self.vip.rpc.call(
                                           'platform.actuator', 
                                           'set_point',
                                           agent_id, 
                                           msg_device + '/setpoint',
                                           str(setpointVal)).get(timeout=10)
                    _log.info("Set result", result)
                    
                    device_setpoint_dict[device] = setpointVal

            except Exception as e:
                _log.info ("Expected to fail since there is no real device to set")
                _log.info(e)      

        
    Agent.__name__ = 'HEMSAgent'    
    return HEMS_agent_test(**kwargs)
              
def main(argv=sys.argv):
    '''Main method called by the eggsecutable.'''
    try:
        utils.vip_main(HEMS_agent)
    except Exception as e:
        print e
        _log.exception('unhandled exception')


if __name__ == '__main__':
    # Entry point for script
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        pass
   
            
            