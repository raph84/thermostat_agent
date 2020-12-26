from thermostat_iot_control import update_config


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

    if next_action['action'] > 0.6:
        config_dict['heating_state'] = True

    else:
        config_dict['heating_state'] = False

    config = update_config(config_dict,"thermostat1")

    return config_dict['heating_state']
