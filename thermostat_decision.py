from thermostat_iot_control import update_config
from flask import current_app
import os
import logging

ACTION_THRESHOLD = float(os.environ.get('ACTION_THRESHOLD',0.75))

if 'FLASK_APP' not in os.environ.keys():
    cloud_logger = logging.getLogger("cloudLogger")
else:
    cloud_logger = logging

def heating_decision(next_action):


    '''
    {
        "action": 0.2544361719199427,
        "indoor_temp": 21.230010384615387,
        "indoor_temp_setpoint": 22,
        "occupancy_flag": true,
        "sat_stpt": 0.2544361719199427,
        "sys_out_temp": 23.78
    }
    '''
    config_dict = {}
    action = float(next_action['action'])

    cloud_logger..info("Next action : {} ; Threshold : {}".format(
        next_action['action'], ACTION_THRESHOLD))

    if float(next_action['action']) > ACTION_THRESHOLD:

        config_dict['heating_state'] = True
    else:
        config_dict['heating_state'] = False

    cloud_logger..info(
        "Next action decision factor {}; Heating_state needs to be {}.".format(
            next_action['action'], config_dict['heating_state']))

    config = update_config(config_dict,"thermostat1")

    return config_dict['heating_state']
