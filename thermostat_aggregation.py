from thermostat_iot_control import update_config
from thermal_comfort import ppd

import os
import logging

from flask import Blueprint

from google.cloud import storage
from google.cloud import pubsub_v1
from google.api_core import retry
from yadt import parse_date, apply_tz_toronto, utc_to_toronto, utcnow
from datetime import datetime, timedelta
import pandas as pd
import json
import pickle
import numpy as np
from thermostat_aggregation_utils import *

thermostat_aggregation = Blueprint('thermostat_aggregation', __name__)


cloud_logger = logging

FILENAME = "aggregate.p"
bucket_name = "thermostat_metric_data"
bucket_climacell = "climacell_data"

project_id = os.environ['PROJECT_ID']
subscription_id = 'thermostat_metric_subsciption'


def get_metric_from_bucket(blob):

    json_str = blob.download_as_bytes()
    last_json = metric_str_to_json(json_str)

    return last_json





def create_file(payload, filename):
    blob = bucket.blob(filename)

    blob.upload_from_string(data=payload, content_type='text/plain')

def rename_climacell_columns(data):
    data.rename(columns={
        'humidity': 'Outdoor RH',
        'temp': 'Outdoor Temp.',
        'surface_shortwave_radiation': 'Direct Solar Rad.',
        'wind_speed': 'Wind Speed',
        'wind_direction': 'Wind Direction'
    },
                inplace=True)

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

@thermostat_aggregation.route('/aggregation/', methods=['GET'])
def request_get_aggregation():

    agg2, hourly = get_aggregation_metric_thermostat()
    agg2 = agg2.replace({np.nan: None})
    #print(agg2)

    return {
        "aggregation": agg2.to_dict('records'),
        "hourly": hourly.to_dict('records')
    }

def motion_df_resample(agg):


    m = agg.copy(deep=True)[['motion']]
    m['Occupancy Flag'] = m['motion']
    del m['motion']
    m['Occupancy Flag'] = m['Occupancy Flag'].apply(lambda x: 1 if x else 0)
    m = m.resample('3min').sum()
    # Normalize values
    m['Occupancy Flag'] = (m['Occupancy Flag'] - m['Occupancy Flag'].min()
                            ) / (m['Occupancy Flag'].max() -
                                m['Occupancy Flag'].min())
    # Exponential decay
    x_item = {}
    for x in range(12):
        max = m.index.max()
        next_item = max + pd.Timedelta(value=15, unit='minutes')
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
    agg_quantile = agg_quantile[start_index:end_index][[
        'Occupancy Flag'
    ]]

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

def get_aggregation_metric_thermostat(skip_agg=False):

    # Instantiates a client
    storage_client = storage.Client()
    # The name for the new bucket
    bucket = storage_client.bucket("thermostat_metric_data")

    b = bucket.get_blob(FILENAME)

    b.temporary_hold = True
    b.patch()
    pickle_load = b.download_as_bytes()
    agg2 = pickle.loads(pickle_load)

    if skip_agg == False:

        agg2_now = utcnow()
        if agg2.index.max() > agg2_now:
            # We might have new data to aggregate for this last 15 minutes.
            logging.warning("")
            agg2.drop(index=agg2.index.max())



        end_date = utc_to_toronto(agg2.index.max().to_pydatetime())
        end_date_motion = end_date - timedelta(hours=3)
        #end_date = parse_date("2020-12-30T08:43:00-0500")

        cloud_logger.info("Downloading latest thermostat metrics back to {}...".format(end_date.isoformat()))
        metric_list = list(storage_client.list_blobs(bucket_name, prefix='thermostat'))
        metric_list.reverse()
        thermostat_agg = aggregator(metric_list, date_function_thermostat,
                                    value_function_thermostat,
                                    date_selection_realtime, end_date_motion)
        thermostat_agg.rename(columns={'temperature': 'Indoor Temp.'}, inplace=True)


        #end_date = utc_to_toronto(thermostat_agg.index.min().to_pydatetime())
        end_date = thermostat_agg.index[thermostat_agg.index.searchsorted(end_date)]

        thermostat_agg_motion = thermostat_agg.copy(deep=True)
        thermostat_agg = thermostat_agg[end_date:thermostat_agg.index.max()]

        if len(thermostat_agg) > 0:
            cloud_logger.info("New thermostat metric to aggregate back to : {}".format(thermostat_agg.index.min()))

            cloud_logger.info("Downloading latest basement metrics...")
            basement_list = list(storage_client.list_blobs(bucket, prefix='environment_sensor_basement-'))
            basement_list.reverse()
            basement_agg = aggregator(basement_list, date_function_basement,
                                    value_function_basement,
                                    date_selection_realtime,
                                    end_date - timedelta(hours=1))
            basement_agg = basement_agg.resample('15Min').mean()

            cloud_logger.info("Downloading latest realtime weather...")
            realtime_list = list(storage_client.list_blobs(bucket_climacell, prefix='realtime'))
            realtime_list.reverse()
            realtime_agg = aggregator(realtime_list, date_function_climacell,
                                    value_function_climacell,
                                    date_selection_realtime,
                                    end_date - timedelta(hours=1))

            rename_climacell_columns(realtime_agg)
            # TODO: check NaN from climacell

            realtime_agg.interpolate(limit=6, inplace=True)

            nan_realtime = realtime_agg.isnull().sum().sum()
            #if nan_realtime ­­>0:
            #    logging.error("Null values in realtime climacell data : {}".format(realtime_agg.is_null().sum()))

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

            ##
            m = motion_df_resample(thermostat_agg_motion)
            ##

            agg_x = agg_x.merge(m, left_index=True, right_index=True)
            agg_x = agg_x.merge(basement_agg, left_index=True, right_index=True)
            agg_x = agg_x.drop(index=agg2.index, errors='ignore')
            #agg_x['dt'] = agg_x.index.values
            #agg_x['dt'] = agg_x['dt'].apply(lambda x: utc_to_toronto(x.to_pydatetime()).isoformat())

            agg2 = agg2.append(agg_x)
            agg2['dt'] = agg2.index.values
            agg2['dt'] = agg2['dt'].apply(
                lambda x: utc_to_toronto(x.to_pydatetime()).isoformat())

            dup_agg2 = agg2.index.duplicated().sum()
            if dup_agg2 > 0:
                cloud_logger.warning("Duplicate agg_x : {}".format(dup_agg2))
                dup_agg2 = agg2.copy(deep=True)
                dup_agg2['dup'] = dup_agg2.index.duplicated(keep=False)
                dup_agg2 = dup_agg2[dup_agg2['dup']]
                dup_agg2.sort_index(inplace=True)
                logging.info(dup_agg2.to_dict('records'))
                agg2 = agg2[~agg2.index.duplicated(keep='first')]



            cloud_logger.info("Uploading aggregation results...")
            pickle_dump = pickle.dumps(agg2)
            b = bucket.get_blob(FILENAME)
            b.temporary_hold = False
            b.patch()
            b.upload_from_string(data=pickle_dump, content_type='text/plain')

    else:
        logging.warning("No aggregation has been done. ship_agg == True.")

    hourly_start = agg2.index.max().to_pydatetime() - timedelta(minutes=60)
    hourly_end = hourly_start + timedelta(hours=7)

    hourly_list = list(storage_client.list_blobs(bucket_climacell, prefix='hourly'))
    hourly_list.reverse()

    cloud_logger.info("Downloading latest hourly weather forecast...")
    hourly_agg = aggregator(hourly_list, date_function_climacell, value_function_climacell, date_selection_hourly, hourly_end, hourly_start)
    rename_climacell_columns(hourly_agg)

    #Sometime climacell has missing values
    hourly_agg.interpolate(limit=6, inplace=True)

    hourly_agg = hourly_agg.resample('15Min').interpolate(method='linear')
    if 'm' in locals():
        hourly_agg = hourly_agg.merge(m, left_index=True, right_index=True)
    else:
        hourly_agg['Occupancy Flag'] = False
    hourly_agg = hourly_agg.drop(index=agg2.index, errors='ignore')
    hourly_agg = hourly_agg.head(13)
    #del hourly_agg['dt']

    if len(hourly_agg) >= 12:
        logging.info("Number of hourly forecast items (should be at least 12) : {}".format(len(hourly_agg)))
    else:
        logging.error("Not enought hourly forecast : {}. MPC model will likely fail.")

    #agg2.interpolate(limit=6, inplace=True)

    nan_agg2 = agg2.isnull().sum().sum()
    nan_hourly = hourly_agg.isnull().sum()

    hourly_validate, hourly_failed_sequence = validate_index_sequence(hourly_agg)
    agg2_validate, agg2_failed_sequence = validate_index_sequence(agg2)
    assert hourly_validate, '; '.join(x.to_pydatetime().isoformat() for x in hourly_failed_sequence)
    assert agg2_validate, '; '.join(x.to_pydatetime().isoformat() for x in agg2_failed_sequence)

    if nan_agg2 > 0:
        logging.error("Null values in data aggregation : {}".format(
            agg2.isnull().sum()))

    cloud_logger.info("Data aggregation done.")


    return agg2, hourly_agg

def aggregate_next_action_result(next_action):

    # Instantiates a client
    storage_client = storage.Client()
    # The name for the new bucket
    bucket = storage_client.bucket(bucket_name)
    b = bucket.get_blob(FILENAME)
    b.temporary_hold = True
    b.patch()
    pickle_load = b.download_as_bytes()
    agg2 = pickle.loads(pickle_load)

    last_item_index = agg2.index.max()

    #TODO assert now +- 30 minutes

    df_next_action = pd.DataFrame(next_action, index=[last_item_index])
    agg2.update(df_next_action)
    #agg2 = agg2[agg2['heating_state'].notna()]

    cloud_logger.info(agg2.tail(1).to_dict('records'))

    cloud_logger.info("Uploading next_action result aggregation...")
    pickle_dump = pickle.dumps(agg2)
    b = bucket.get_blob(FILENAME)
    b.temporary_hold = False
    b.patch()
    b.upload_from_string(data=pickle_dump, content_type='text/plain')

    return agg2.tail(1)


def get_file_from_bucket(filename):
    # Instantiates a client
    storage_client = storage.Client()
    # The name for the new bucket
    bucket = storage_client.bucket(bucket_name)

    b = bucket.get_blob(filename)
    data = b.download_as_bytes()

    return data


@thermostat_aggregation.route('/pull-thermostat-metric/', methods=['POST'])
def aggregate_metric_thermostat():



    NUM_MESSAGES = 10

    # Instantiates a client
    storage_client = storage.Client()
    # The name for the new bucket
    bucket = storage_client.bucket(bucket_name)

    blob_thermostat_metric_data = bucket.get_blob('_thermostat_metric_data.p')
    blob_thermostat_metric_data.temporary_hold = True
    blob_thermostat_metric_data.patch()
    dump_dataframe = blob_thermostat_metric_data.download_as_bytes()
    thermostat_dataframe = pickle.loads(dump_dataframe)

    updates = 0
    delta = timedelta(seconds=10)
    start = utcnow() + timedelta(seconds=1)


    while utcnow() - start < delta:

        subscriber = pubsub_v1.SubscriberClient()
        # The `subscription_path` method creates a fully qualified identifier
        # in the form `projects/{project_id}/subscriptions/{subscription_id}`
        subscription_path = subscriber.subscription_path(project_id,
                                                        subscription_id)


        # Wrap the subscriber in a 'with' block to automatically call close() to
        # close the underlying gRPC channel when done.
        with subscriber:

            # The subscriber pulls a specific number of messages. The actual
            # number of messages pulled may be smaller than max_messages.
            response = subscriber.pull(
                request={
                    "subscription": subscription_path,
                    "max_messages": NUM_MESSAGES
                },
                retry=retry.Retry(deadline=10),
            )

            ack_ids = []
            for message in response.received_messages:

                # Still receiving msg. Reset the timeout
                start = utcnow() + timedelta(seconds=1)

                if message.message.attributes[
                        'eventType'] == 'OBJECT_FINALIZE' and (
                            message.message.attributes['objectId'].startswith(
                                'thermostat-')
                            or message.message.attributes['objectId'].
                            startswith('environment_sensor')):

                    logging.info(f"Received {message.message.attributes['objectId']}.")
                    blob = bucket.get_blob(message.message.attributes['objectId'])

                    data = get_metric_from_bucket(blob)
                    merge, thermostat_dataframe = aggregate_to_dataframe(
                        blob.name, data, thermostat_dataframe)

                    if merge :
                        updates = updates + 1


                    ack_ids.append(message.ack_id)

                else:
                    # Not the msg we are looking for
                    logging.info(f"PASS - {message.message.attributes['objectId']}")
                    ack_ids.append(message.ack_id)


            if len(ack_ids) > 0 :
                # Acknowledges the received messages so they will not be sent again.
                subscriber.acknowledge(request={
                    "subscription": subscription_path,
                    "ack_ids": ack_ids
                })

            print(
                f"Received and acknowledged {len(response.received_messages)} messages from {subscription_path}."
            )

    logging.info("Msg pulling done.")



    logging.info("{} items have been added.".format(updates))
    blob_thermostat_metric_data.temporary_hold = False
    blob_thermostat_metric_data.patch()

    if updates > 0:
        thermostat_dataframe = thermostat_dataframe.sort_index()
        logging.info("Saving thermostat_dataframe...")
        pickle_dump = pickle.dumps(thermostat_dataframe)
        blob_thermostat_metric_data.upload_from_string( data=pickle_dump, content_type='text/plain')

    return ('Loaded {} metric(s).'.format(updates), 204)