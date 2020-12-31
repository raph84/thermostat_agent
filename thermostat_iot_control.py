from flask import Blueprint
from google.cloud import iot_v1
import json
from flask import current_app
import logging
import os

thermostat_iot_control = Blueprint('thermostat_iot_control', __name__)

if 'FLASK_APP' not in os.environ.keys():
    cloud_logger = logging.getLogger("cloudLogger")
else:
    cloud_logger = logging

project_id = 'raph-iot'
cloud_region = 'us-central1'
registry_id = 'thermostat-registry'
# device_id = 'your-device-id'


@thermostat_iot_control.route('/device/<device_id>', methods=['GET'])
def retrieve_config(device_id):
    project_id = 'raph-iot'
    cloud_region = 'us-central1'
    registry_id = 'thermostat-registry'

    client = iot_v1.DeviceManagerClient()
    device_path = client.device_path(project_id, cloud_region, registry_id, device_id)

    configs = client.list_device_config_versions(request={"name": device_path})

    # for config in configs.device_configs:
    #     print(
    #         "version: {}\n\tcloudUpdateTime: {}\n\t data: {}".format(
    #             config.version, config.cloud_update_time, config.binary_data
    #         )
    #     )
    last_config = configs.device_configs[0].binary_data
    last_config_dict = json.loads(last_config)

    return last_config_dict, configs.device_configs[0].version


def get_config_next_version(device_id):
    last_config, last_version = retrieve_config(device_id)
    print(last_config)
    print(last_version)
    return last_config, last_version


@thermostat_iot_control.route('/device/<device_id>', methods=['PATCH'])
def update_config_request(device_id):
    # project_id = 'YOUR_PROJECT_ID'
    # cloud_region = 'us-central1'
    # registry_id = 'your-registry-id'
    # device_id = 'your-device-id'
    config_dict = {}

    heating_state = request.args.get('heating_state', None)
    if heating_state is not None:
        config_dict['heating_state'] = heating_state
        
    config = update_config(config_dict, device_id)


    return config

def update_config(config_dict,device_id):

    config, version = get_config_next_version(device_id)
    print("Updating config version {} for device : {}".format(
        version, device_id))
    # config= 'your-config-data'
    print("Set device configuration")
    client = iot_v1.DeviceManagerClient()
    device_path = client.device_path(project_id, cloud_region, registry_id,
                                     device_id)

    update_needed = False
    cloud_logger.info("Config_dict : {}".format(config_dict))
    for k in config_dict.keys():
        cloud_logger.info("Processing config : {}".format(k))
        if config_dict[k] is not None:
            if k in config.keys():
                if config[k] != config_dict[k]:
                    config[k] = config_dict[k]
                    update_needed = True
                else:
                    cloud_logger.info("Config key {} is already set to {}. No update required.".format(k, config[k]))
            else:
                cloud_logger.warn("Config key {} non existant.".format(k))

    if update_needed:
        data = json.dumps(config).encode("utf-8")

        device_config = client.modify_cloud_to_device_config(
            request={
                "name": device_path,
                "binary_data": data,
                "version_to_update": version
            })
    else:
        cloud_logger.info("No config update required. Config already up 2 date.")

    return config