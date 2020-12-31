from thermostat_iot_control import update_config
from thermal_comfort import ppd

import os
import logging

from flask import Blueprint

from google.cloud import storage
from yadt import parse_date, apply_tz_toronto, utc_to_toronto
from datetime import datetime, timedelta
import pandas as pd
import json
import pickle
import numpy as np

thermostat_aggregation = Blueprint('thermostat_aggregation', __name__)

if 'FLASK_APP' not in os.environ.keys():
    cloud_logger = logging.getLogger("cloudLogger")
else:
    cloud_logger = logging

FILENAME = "aggregate.p"
bucket_name = "thermostat_metric_data"
bucket_climacell = "climacell_data"


def get_metric_from_bucket(blob):

    last_json = []

    try:
        json_str = blob.download_as_bytes()
        j = json.loads(json_str)
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


def aggregator(blob_list, date_function, value_function, date_select_function, end_date, start_date=None):
    aggregation = pd.DataFrame()

    for m in blob_list:
        metric_json = get_metric_from_bucket(m)
        #print(m.name)
        for item in metric_json:

            #need data from filename
            if m.name.startswith('environment_sensor_basement-'):
                item['location'] = 'house.basement'
                str_date = m.name.replace('environment_sensor_basement-','')
                item['dt'] = parse_date(str_date)

            date_function(item)
            metric_dict = value_function(item)

            select, end = date_select_function(metric_dict['dt'], end_date, start_date)
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


def date_selection_realtime(dt, end_date, start_date):
    selection_end = end_date

    select = True
    end = False
    if dt > selection_end:
        #print(dt)
        select = False
        end = True

    return select, end

def get_set_point(date):
    if date.hour >= 21 or (date.hour <= 5 and date.minute >= 30):
        return 18
    else:
        return 22


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


def create_file(payload, filename):
    blob = bucket.blob(filename)

    blob.upload_from_string(data=payload, content_type='text/plain')


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


def rename_climacell_columns(data):
    data.rename(columns={
        'humidity': 'Outdoor RH',
        'temp': 'Outdoor Temp.',
        'surface_shortwave_radiation': 'Direct Solar Rad.',
        'wind_speed': 'Wind Speed',
        'wind_direction': 'Wind Direction'
    },
                inplace=True)


def date_selection_hourly(dt, hourly_end, hourly_start):
    select = False
    end = False


    if dt <= hourly_end and dt >= hourly_start:
        select = True

    if dt > hourly_end:
        end = True

    return select, end


def retrieve_hourly():
    hourly_start = agg2.index.max().to_pydatetime()
    hourly_end = hourly_start + timedelta(hours=4)

    hourly_list = list(
        storage_client.list_blobs(bucket_climacell, prefix='hourly'))


    hourly_list.reverse()

    hourly_agg = aggregator(hourly_list, date_function_climacell,
                            value_function_climacell, date_selection_hourly)
    rename_climacell_columns(hourly_agg)
    hourly_agg


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




@thermostat_aggregation.route('/aggregation/', methods=['GET'])
def request_get_aggregation():

    agg2, hourly = get_aggregation_metric_thermostat()
    agg2 = agg2.replace({np.nan: None})
    #print(agg2)

    return {
        "aggregation": agg2.to_dict('records'),
        "hourly": hourly.to_dict('records')
    }


def get_aggregation_metric_thermostat():

    # Instantiates a client
    storage_client = storage.Client()
    # The name for the new bucket
    bucket = storage_client.bucket("thermostat_metric_data")

    b = bucket.get_blob(FILENAME)

    b.temporary_hold = True
    b.patch()
    pickle_load = b.download_as_bytes()
    agg2 = pickle.loads(pickle_load)

    #agg2 = pd.DataFrame()

    end_date = utc_to_toronto(agg2.index.max().to_pydatetime())
    #end_date = parse_date("2020-12-30T08:43:00-0500")

    cloud_logger..info("Downloading latest thermostat metrics...")
    metric_list = list(storage_client.list_blobs(bucket_name, prefix='thermostat'))
    metric_list.reverse()
    thermostat_agg = aggregator(metric_list, date_function_thermostat, value_function_thermostat, date_selection_realtime, end_date)
    thermostat_agg.rename(columns={'temperature': 'Indoor Temp.'}, inplace=True)


    end_date = utc_to_toronto(thermostat_agg.index.min().to_pydatetime())

    if len(thermostat_agg) > 0:
        cloud_logger..info("New thermostat metric to aggregate : {}".format(thermostat_agg.index.min()))

        cloud_logger..info("Downloading latest basement metrics...")
        basement_list = list(storage_client.list_blobs(bucket, prefix='environment_sensor_basement-'))
        basement_list.reverse()
        basement_agg = aggregator(basement_list, date_function_basement,
                                  value_function_basement,
                                  date_selection_realtime,
                                  end_date - timedelta(hours=1))
        basement_agg = basement_agg.resample('15Min').mean()

        cloud_logger..info("Downloading latest realtime weather...")
        realtime_list = list(storage_client.list_blobs(bucket_climacell, prefix='realtime'))
        realtime_list.reverse()
        realtime_agg = aggregator(realtime_list, date_function_climacell,
                                  value_function_climacell,
                                  date_selection_realtime,
                                  end_date - timedelta(hours=1))
        rename_climacell_columns(realtime_agg)


        stove = thermostat_agg.copy(deep=True)[thermostat_agg['location'] == 'house.basement.stove'][['stove_exhaust_temp', 'Coil Power']]
        t_a = thermostat_agg.copy(deep=True)[thermostat_agg['location'] != 'house.basement.stove']
        # t_a.sort_values('dt', inplace=True)
        # stove.sort_values('dt', inplace=True)
        del t_a['stove_exhaust_temp']
        del t_a['location']
        del t_a['Coil Power']
        #agg = pd.merge_asof(t_a, stove, left_on='dt', right_on='dt', direction="nearest")
        agg = pd.merge_asof(t_a, stove, left_index = True, right_index = True, direction="nearest")

        #agg.set_index('dt', inplace=True)

        #agg.sort_values('dt',inplace=True)
        #realtime_agg.sort_values('dt',inplace=True)
        #agg = pd.merge_asof(agg, realtime_agg,left_on='dt',right_on='dt',direction="nearest")
        if len(realtime_agg) > 0:
            agg = pd.merge_asof(agg, realtime_agg,
                                left_index=True,
                                right_index=True,
                                direction="nearest")
        #agg.set_index('dt', inplace=True)
        agg = agg[~agg.index.duplicated(keep='first')]
        agg_x = agg.resample('15Min').mean()
        print("Duplicate agg_x : {}".format(agg_x.index.duplicated().sum()))

        m = agg.copy()[['motion']]
        m['Occupancy Flag'] = m['motion']
        del m['motion']
        m['Occupancy Flag'] = m['Occupancy Flag'].apply(lambda x: 1 if x else 0)
        m = m.resample('3min').sum()
        # Normalize values
        m['Occupancy Flag'] = (m['Occupancy Flag'] - m['Occupancy Flag'].min()
                               ) / (m['Occupancy Flag'].max() -
                                    m['Occupancy Flag'].min())
        # Exponential decay
        m['Occupancy Flag'] = m['Occupancy Flag'].ewm(halflife='6Min',
                                                      times=m.index).mean()
        m = m[['Occupancy Flag']].resample('15min').sum()
        # Values bellow 50 quantile will be False
        m['quantile'] = m['Occupancy Flag'].quantile(q=0.50)
        m['Occupancy Flag'] = m.apply(
            lambda x: True if x['Occupancy Flag'] > x['quantile'] else False,
            axis=1)
        del m['quantile']

        agg_x = agg_x.merge(m, left_index=True, right_index=True)
        agg_x = agg_x.merge(basement_agg, left_index=True, right_index=True)
        #agg_x['dt'] = agg_x.index.values
        #agg_x['dt'] = agg_x['dt'].apply(lambda x: utc_to_toronto(x.to_pydatetime()).isoformat())

        agg2 = agg2.append(agg_x)
        agg2['dt'] = agg2.index.values
        agg2['dt'] = agg2['dt'].apply(
            lambda x: utc_to_toronto(x.to_pydatetime()).isoformat())

        dup_agg2 = agg2.index.duplicated().sum()
        if dup_agg2 > 0:
            print("Duplicate agg_x : {}".format(dup_agg2))
            cloud_logger..warn("Duplicate agg_x : {}".format(dup_agg2))

        cloud_logger..info("Uploading aggregation results...")
        pickle_dump = pickle.dumps(agg2)
        b = bucket.get_blob(FILENAME)
        b.temporary_hold = False
        b.patch()
        b.upload_from_string(data=pickle_dump, content_type='text/plain')



    hourly_start = agg2.index.max().to_pydatetime() - timedelta(minutes=45)
    hourly_end = hourly_start + timedelta(hours=4)

    hourly_list = list(storage_client.list_blobs(bucket_climacell, prefix='hourly'))
    hourly_list.reverse()

    cloud_logger..info("Downloading latest hourly weather forecast...")
    hourly_agg = aggregator(hourly_list, date_function_climacell, value_function_climacell, date_selection_hourly, hourly_end, hourly_start)
    rename_climacell_columns(hourly_agg)
    hourly_agg = hourly_agg.resample('15Min').interpolate(method='linear')
    hourly_agg['Occupancy Flag'] = False
    #del hourly_agg['dt']


    agg2.interpolate(limit=6, inplace=True)

    nan_agg2 = agg2.isnull().sum()
    nan_hourly = hourly_agg.isnull().sum()

    #agg2 = agg2.append(hourly_agg)

    cloud_logger..info("Data aggregation done.")

    return agg2, hourly_agg