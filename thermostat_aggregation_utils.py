import pandas as pd
import json
from yadt import utc_to_toronto, utcnow, parse_date, apply_tz_toronto, get_tz
from datetime import datetime, timedelta
import logging
import re

from thermal_comfort import ppd


def get_metric_from_bucket(blob):

    json_str = blob.download_as_bytes()
    last_json = metric_str_to_json(json_str)

    return last_json


def metric_str_to_json(json_str):

    last_json = []
    try:
        j = json.loads(json_str)

        #if 'temperature' in j.keys() and j['temperature'] is None:
        #assert j['temperature'] is not None, json_str
        #logging.warning("Payload doesn't contain temperature value : {}".format(json_str))

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

    if filename.startswith('environment_sensor_basement-'):
        assert 'temp_basement' in metric_dict.keys(), metric_dict
        assert metric_dict.get('temp_basement') is not None


    if 'logs' in metric_dict.keys():
        del metric_dict['logs']
    if 'sound' in metric_dict.keys():
        del metric_dict['sound']

    return metric_dict


def aggregate_to_dataframe(filename, data, thermostat_dataframe, load_date):

    merge = False

    d_dict_list = []
    d_index_list = []

    for d in data:
        if len(thermostat_dataframe) > 0:
            merged = thermostat_dataframe[thermostat_dataframe['filename']==filename]
            if len(thermostat_dataframe) == 0 or len(merged) == 0:
                merge = True
            else:
                continue

        if (filename.startswith("environment_")):
            date_function = date_function_basement
            value_function = value_function_basement
        else:
            date_function = date_function_thermostat
            value_function = value_function_thermostat


        try:
            d_dict = aggregator_item(filename, d, date_function,
                                    value_function)

        except KeyError as ke:
            logging.warning("A key is missing : {} ---- {}".format(
                d, ke))
            continue
            #raise ke


        #if 'temperature' not in d_dict.keys() or isinstance(d_dict['temperature'],float) == False:
        #    continue

        d_dict['filename'] = filename
        d_dict['load_date'] = load_date

        d_dict_list.append(d_dict)
        d_index_list.append(d_dict['dt'])
        #df_data = pd.DataFrame(d_dict, index=[d_dict['dt']])


        #thermostat_dataframe = thermostat_dataframe.append(df_data)
        #thermostat_dataframe = pd.concat([thermostat_dataframe, df_data])
    d_df = pd.DataFrame(d_dict_list, index=d_index_list)
    thermostat_dataframe = pd.concat(
        [thermostat_dataframe, d_df])

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

    select = True
    end = False

    if dt < start_date:
        select = False
        end = True
    else:
        if dt > end_date:
            select = False

    return select, end


def value_function_thermostat(i):

    if 'location' not in i.keys():
        if 'site' in i.keys():
            i['location'] = i['site']
            del i['site']
        else:
            if 'stove_exhaust_temp' in i.keys():
                i['location'] = 'house.basement.stove'
            else:
                raise KeyError('location',i)

    if i.get('location') == 'house.basement.stove':
        if not isinstance(i['stove_exhaust_temp'], float):
            i['stove_exhaust_temp'] = float(i['stove_exhaust_temp'])

        i['Coil Power'] = coil_power(i['stove_exhaust_temp'])
    else:
        if i.get('location') == 'house.kitchen' and 'temperature' in i.keys():
            if not isinstance(i['temperature'], float):
                i['temperature'] = float(i['temperature'])
            ppd_value = ppd(tdb=i['temperature'],
                            tr=i['temperature'],
                            rh=i['humidity'])

            i['PPD'] = ppd_value['ppd']
            i["Indoor Temp. Setpoint"] = get_set_point(i['dt'])
            i["Indoor Temp."] = i['temperature']

            del i['temperature']

            i['MA Temp.'] = 18
            i['Htg SP'] = 22

    if 'sound' in i.keys():
        del i['sound']
    if 'timestamp' in i.keys():
        del i['timestamp']

    return i


def date_function_thermostat(i):
    i['dt'] = datetime.fromtimestamp(i['timestamp'], tz=get_tz())


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
            if f == 'temp' and value_dict[f] is not None:
                value_dict[f] = float(value_dict[f])
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


def find_temperature_original_payload(original_payload):
    t = re.match(r".+temperature:([0-9]+\.[0-9]+)",
                 original_payload)

    temperature = None
    if t is not None:
        t = t.groups()
        if len(t) > 0:
            temperature = float(t[0])



    return temperature


def value_function_basement(i):

    if 'temperature' not in i.keys() or i['temperature'] is None:
        if 'original_payload' in i.keys():
            i['temperature'] = find_temperature_original_payload(i['original_payload'])
            if i['temperature'] == None:
                logging.warning(
                    "Cannot fin temperature value from original_payload : {}".
                    format(i['original_payload']))

    if isinstance(i['temperature'], str):
        t = find_temperature_original_payload(i['temperature'])
        if isinstance(t, float):
            i['temperature'] = t
        else:
            logging.warning("Invalid temperature value : {}".format(i['temperature']))


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


def thermostat_dataframe_timeframe(thermostat_dataframe, dt_start, dt_end):
    dt_start = dt_start - timedelta(minutes=15)
    df = thermostat_dataframe.loc[dt_start:dt_end]

    return df


def aggregate_thermostat_dataframe(thermostat_dataframe):

    df = thermostat_dataframe[thermostat_dataframe['location'].isin(['house.kitchen', 'house.basement.stove', 'house.basement'])]
    assert len(df[df['location'] == 'house.basement.stove']) > 0, len(
        df[df['location'] == 'house.basement.stove'])
    assert len(df[df['location'] == 'house.basement']) > 0, len(
        df[df['location'] == 'house.basement'])


    df.sort_index(inplace=True)

    df_motion = motion_df_resample(df)
    
    df['Sys Out Temp.'] = df['Sys Out Temp.'].apply(lambda x : float(x)).interpolate(method='time')
    df = df.resample('15Min', label='right').mean()

    df = df.merge(df_motion, left_index=True, right_index=True)

    return df, df_motion


def check_thermostat_dataframe_up2date(start_date, thermostat_dataframe):

    t_df_max = utc_to_toronto(thermostat_dataframe.index.max().to_pydatetime())
    now_diff = start_date - t_df_max
    assert now_diff<= timedelta(
        seconds=240), "thermostat_dataframe data is too old : {}".format(
            now_diff.total_seconds())

    return True


def motion_df_resample(agg):

    m = agg.copy(deep=True)[['motion']]
    m['Occupancy Flag'] = m['motion']
    del m['motion']
    m['Occupancy Flag'] = m['Occupancy Flag'].apply(lambda x: 1 if x else 0)
    m = m.resample('3min').sum()
    # Normalize values
    m['Occupancy Flag'] = (m['Occupancy Flag'] - m['Occupancy Flag'].min()) / (
        m['Occupancy Flag'].max() - m['Occupancy Flag'].min())
    # Exponential decay
    x_item = {}

    # Add 12 episodes of 15 minutes each
    episode = 12
    # Currently resampled at 3 minutes per episodes
    episode = episode * 5

    for x in range(episode):
        max = m.index.max()
        next_item = max + pd.Timedelta(value=3, unit='minutes')
        m = m.append(pd.DataFrame(data=x_item, index=[next_item]))

    m['Occupancy Flag'] = m['Occupancy Flag'].ewm(halflife='6Min',
                                                  times=m.index).mean()
    agg_quantile = m.copy(deep=True)[['Occupancy Flag']]
    m = m[['Occupancy Flag']].resample('15min').sum()

    start_index = agg_quantile.index.min()
    end_index = agg_quantile.index[agg_quantile.index.searchsorted(
        start_index + pd.Timedelta(value=3, unit='hours'))]
    logging.info(
        "Evaluate motion threshold quantile with subset from {} to {}.".format(
            start_index.to_pydatetime().isoformat(),
            end_index.to_pydatetime().isoformat()))
    agg_quantile = agg_quantile[start_index:end_index][['Occupancy Flag']]

    # TODO : Rolling quantile on the whole dataset

    # Values bellow 50 quantile will be False
    m['quantile'] = agg_quantile['Occupancy Flag'].quantile(q=0.75)
    m['Occupancy Flag'] = m.apply(
        lambda x: True if x['Occupancy Flag'] > x['quantile'] else False,
        axis=1)
    del m['quantile']

    return m


def validate_index_sequence(df):
    delta = timedelta(minutes=15)
    list_index = df.index.values.tolist()
    last_index_item = list_index.pop()
    validate = True
    failed_sequence = []
    for i in list_index:
        if i - last_index_item == delta:
            validate = False
            failed_sequence.append(i)

    return validate, failed_sequence

def rename_climacell_columns(data):
    data.rename(columns={
        'humidity': 'Outdoor RH',
        'temp': 'Outdoor Temp.',
        'surface_shortwave_radiation': 'Direct Solar Rad.',
        'wind_speed': 'Wind Speed',
        'wind_direction': 'Wind Direction'
    },
                inplace=True)