import pandas as pd
import json
from yadt import utc_to_toronto, utcnow, parse_date, apply_tz_toronto
from datetime import datetime

from thermal_comfort import ppd

def dofloat(number):
    return float(number)

def metric_str_to_json(json_str):

    last_json = []
    try:
        j = json.loads(json_str, parse_int=dofloat)
        #j['dt'] = apply_tz_toronto(datetime.fromtimestamp(j['timestamp']))

        #if len(list(j.keys())) > 0:
        #    if 'sound' in j.keys():
        #        del j['sound']
        #    if 'timestamp'
        #    del j['timestamp']
        if isinstance(j, list):
            for item in j:
                last_json.append(item)
        else:
            last_json.append(j)

    except json.JSONDecodeError:
        pass

    return last_json


def aggregator_item(filename, item, date_function, value_function):
    #need data from filename
    if filename.startswith('environment_sensor_basement-'):
        item['location'] = 'house.basement'
        str_date = filename.replace('environment_sensor_basement-', '')
        item['dt'] = parse_date(str_date)



    date_function(item)
    metric_dict = value_function(item)

    if 'logs' in metric_dict.keys():
        del metric_dict['logs']
    if 'sound' in metric_dict.keys():
        del metric_dict['sound']

    return metric_dict


def aggregate_to_dataframe(filename, data, thermostat_dataframe):

    merge = False

    for d in data:

        if (filename.startswith("environment_")):
            date_function = date_function_basement
            value_function = value_function_basement
        else:
            date_function = date_function_thermostat
            value_function = value_function_thermostat

        d_dict = aggregator_item(filename, d, date_function,
                                 value_function_thermostat)

        df_data = pd.DataFrame(d_dict, index=[d_dict['dt']])
        if 'temperature' in df_data:
            df_data['temperature'] = df_data['temperature'].astype(float)
        if 'humidity' in df_data:
            df_data['humidity'] = df_data['humidity'].astype(float)
        if 'stove_exhaust_temp' in df_data:
            df_data['stove_exhaust_temp'] = df_data['stove_exhaust_temp'].astype(
                float)

        if filename == 'thermostat-20210105-170817' or filename == 'thermostat-20210105-170814':
            print(df_data)

        if len(thermostat_dataframe) > 0:
            merged = df_data.merge(thermostat_dataframe,
                                   how='left',
                                   indicator=True)
            merged = merged[merged['_merge'] == 'left_only']


        if len(thermostat_dataframe) == 0 or len(merged) > 0:
            merge = True
            thermostat_dataframe = thermostat_dataframe.append(df_data)

    return merge, thermostat_dataframe


def aggregator(blob_list,
               date_function,
               value_function,
               date_select_function,
               end_date,
               start_date=None):
    aggregation = pd.DataFrame()

    for m in blob_list:
        logging.debug("Downloading {}".format(m.name))
        metric_json = get_metric_from_bucket(m)
        logging.debug("Importing {} items...".format(len(metric_json)))
        if len(metric_json) > 0:
            for item in metric_json:

                metric_dict = aggregator_item(m.name, item, date_function,
                                              value_function)

                select, end = date_select_function(metric_dict['dt'], end_date,
                                                   start_date)
                if select:
                    df = pd.DataFrame(metric_dict, index=[metric_dict['dt']])
                    aggregation = aggregation.append(df)

                if end:
                    break
            if end:
                break

    if 'dt' in aggregation:
        aggregation.set_index('dt', inplace=True)
        aggregation.sort_index(inplace=True)

    return aggregation


def date_selection_realtime(dt, end_date, start_date):
    selection_end = end_date

    select = True
    end = False
    if dt > selection_end:
        #print(dt)
        select = False
        end = True

    return select, end


def value_function_thermostat(i):

    if i['location'] == 'house.basement.stove':
        i['Coil Power'] = coil_power(i['stove_exhaust_temp'])
    else:
        if i['location'] == 'house.kitchen':
            ppd_value = ppd(tdb=i['temperature'],
                            tr=i['temperature'],
                            rh=i['humidity'])

            i['PPD'] = ppd_value['ppd']
            i["Indoor Temp. Setpoint"] = get_set_point(i['dt'])

            i['MA Temp.'] = 18
            i['Htg SP'] = 22

    if 'sound' in i.keys():
        del i['sound']
    if 'timestamp' in i.keys():
        del i['timestamp']

    return i


def date_function_thermostat(i):
    i['dt'] = apply_tz_toronto(datetime.fromtimestamp(i['timestamp']))


def date_function_climacell(i):
    #print(i)
    i['dt'] = parse_date(i['observation_time']['value'])
    del i['observation_time']
    #"observation_time": {"value": "2020-10-18T21:15:02.777Z"}}¸


def value_function_climacell(i):
    #print(i)
    field = [
        'temp', 'humidity', 'wind_speed', 'wind_direction',
        'surface_shortwave_radiation'
    ]
    if 'observation_time' in i.keys():
        field.append('observation_time')
    else:
        field.append('dt')

    value_dict = {}

    for f in field:
        if f != 'dt':
            value_dict[f] = i[f]['value']
        else:
            value_dict[f] = i[f]

    return value_dict


def date_selection_hourly(dt, hourly_end, hourly_start):
    select = False
    end = False

    if dt <= hourly_end and dt >= hourly_start:
        select = True

    if dt > hourly_end:
        end = True

    return select, end


def date_selection_realtime(dt, end_date, start_date):
    selection_end = end_date

    select = True
    end = False
    if dt < selection_end:
        #print(dt)
        select = False
        end = True

    return select, end


def value_function_basement(i):

    i['temp_basement'] = i['temperature']
    i["Sys Out Temp."] = i['temp_basement']
    del i['temperature']
    del i['original_payload']

    return i


def date_function_basement(i):
    return


def get_set_point(date):
    if date.hour >= 21 or (date.hour <= 5 and date.minute >= 30):
        return 18
    else:
        return 22


def coil_power(stove_exhaust_temp):
    max_coil_power = 10613.943465
    min_coil_power = 0.0
    max_stove_exhaust_temp = 130.0

    if stove_exhaust_temp > 30:
        coil_power = (stove_exhaust_temp *
                      max_coil_power) / max_stove_exhaust_temp
    else:
        coil_power = 0

    return coil_power