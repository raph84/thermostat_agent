from thermostat_iot_control import update_config
from flask import current_app


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

    if float(next_action['action']) > 0.6:
        current_app.logger.info("Next action decision factor {}; Heating_state needs to be True.")
        config_dict['heating_state'] = True
    else:
        config_dict['heating_state'] = False

    config = update_config(config_dict,"thermostat1")

    return config_dict['heating_state']
