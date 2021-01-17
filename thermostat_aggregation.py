from thermostat_iot_control import update_config
from thermal_comfort import ppd

import os
import logging

from flask import Blueprint

from google.cloud import storage
from google.cloud import pubsub_v1
from google.api_core import retry
from yadt import parse_date, apply_tz_toronto, utc_to_toronto, utcnow, ceil_dt, floor_date
from datetime import datetime, timedelta
import pandas as pd
import json
import pickle
import numpy as np
from thermostat_aggregation_utils import *

thermostat_aggregation = Blueprint('thermostat_aggregation', __name__)



FILENAME = "aggregate.p"
THERMOSTAT_DATAFRAME = "_thermostat_metric_data.p"
bucket_name = "thermostat_metric_data"
bucket_climacell = "climacell_data"

project_id = os.environ['PROJECT_ID']
subscription_id = 'thermostat_metric_subsciption'


@thermostat_aggregation.route('/aggregation/', methods=['GET'])
def request_get_aggregation():

    agg2, hourly = get_aggregation_metric_thermostat()
    agg2 = agg2.replace({np.nan: None})
    #print(agg2)

    return {
        "aggregation": agg2.to_dict('records'),
        "hourly": hourly.to_dict('records')
    }


def get_aggregation_metric_thermostat(skip_agg=False):

    # Instantiates a client
    storage_client = storage.Client()
    # The name for the new bucket
    bucket = storage_client.bucket("thermostat_metric_data")

    b = bucket.get_blob(THERMOSTAT_DATAFRAME)

    b.temporary_hold = True
    b.patch()
    pickle_load = b.download_as_bytes()
    thermostat_dataframe = pickle.loads(pickle_load)


    agg2_now = utcnow()
    dt_end = floor_date(agg2_now, minutes=15)
    dt_start = dt_end - timedelta(hours=5)


    check_thermostat_dataframe_up2date(dt_end, thermostat_dataframe)

    df = thermostat_dataframe_timeframe(thermostat_dataframe,
                                                dt_start, dt_end)

    df, m = aggregate_thermostat_dataframe(df)

    logging.info("Downloading latest realtime weather...")
    realtime_list = list(storage_client.list_blobs(bucket_climacell, prefix='realtime'))
    realtime_list.reverse()
    realtime_agg = aggregator(realtime_list, date_function_climacell,
                                value_function_climacell,
                                date_selection_realtime, dt_end, dt_start
                                )

    assert len(realtime_agg) > 0, "Realtime weather missing"

    rename_climacell_columns(realtime_agg)
    nan_realtime = realtime_agg.isnull().sum().sum()
    if nan_realtime > 0:
        logging.warning(
            "NaN values in realtime_agg : {}. interpolate to fill the gaps...".
            format(nan_realtime))
        realtime_agg.interpolate(limit=8, inplace=True)
        nan_realtime = realtime_agg.isnull().sum().sum()

    if nan_realtime > 0:
        logging.warning("Still have NaN values in realtime climacell data : {}".format(nan_realtime))
    #assert nan_realtime == 0, "Still have NaN values in realtime climacell data : {}".format(
    #    nan_realtime)


    df = pd.merge_asof(df, realtime_agg,
                        left_index=True,
                        right_index=True,
                        direction="nearest")



    hourly_start = dt_start - timedelta(days=1)
    hourly_end = dt_end + timedelta(hours=18)

    hourly_list = list(storage_client.list_blobs(bucket_climacell, prefix='hourly'))
    hourly_list.reverse()

    logging.info("Downloading latest hourly weather forecast...")
    hourly_agg = aggregator(hourly_list, date_function_climacell, value_function_climacell, date_selection_hourly, hourly_end, hourly_start)
    rename_climacell_columns(hourly_agg)

    # TODO : Duplicate? drop first

    #Sometime climacell has missing values
    if hourly_agg.isnull().sum().sum() > 0:
        logging.warn('NaN value in hourly weather forecast : {} --- {}'.format(
            hourly_agg.isnull().sum().sum(),hourly_agg))
        hourly_agg.interpolate(limit=6, inplace=True)
    hourly_agg = hourly_agg.resample('15Min').interpolate(method='linear')
    hourly_agg = hourly_agg.merge(m, left_index=True, right_index=True)
    hourly_agg = hourly_agg.copy(deep=True)[hourly_agg.index > df.index.max()]
    hourly_agg = hourly_agg.head(12)
    #del hourly_agg['dt']

    if len(hourly_agg) < 12:
        logging.warning(
            "Not enought hourly forecast : {}. MPC model will likely fail.".
            format(len(hourly_agg)))

    #agg2.interpolate(limit=6, inplace=True)

    nan_hourly = hourly_agg.isnull().sum()

    hourly_validate, hourly_failed_sequence = validate_index_sequence(hourly_agg)
    df_validate, df_failed_sequence = validate_index_sequence(df)
    assert hourly_validate, '; '.join(x.to_pydatetime().isoformat() for x in hourly_failed_sequence)
    assert df_validate, '; '.join(x.to_pydatetime().isoformat() for x in df_failed_sequence)


    logging.info("Data aggregation done.")


    return df, hourly_agg

def aggregate_next_action_result(next_action, action_date):

    # Instantiates a client
    storage_client = storage.Client()
    # The name for the new bucket
    bucket = storage_client.bucket(bucket_name)
    b = bucket.get_blob(THERMOSTAT_DATAFRAME)
    b.temporary_hold = True
    b.patch()
    pickle_load = b.download_as_bytes()
    agg2 = pickle.loads(pickle_load)

    last_item_index = agg2.index.max()

    #TODO assert now +- 30 minutes

    df_next_action = pd.DataFrame(next_action, index=[action_date])
    agg2.append(df_next_action)
    #agg2 = agg2[agg2['heating_state'].notna()]

    logging.info(agg2.tail(2).to_dict('records'))

    logging.info("Uploading next_action result aggregation...")
    pickle_dump = pickle.dumps(agg2)
    b = bucket.get_blob(THERMOSTAT_DATAFRAME)
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
    start_origin = start

    logging.info("Begin pull-thermostat-metric at : {}".format(start.isoformat()))

    load_date = utcnow()

    while (utcnow() - start < delta) and (utcnow() - start_origin < timedelta(seconds=120)):

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

                #########################################
                # Still receiving msg. Reset the timeout
                #########################################
                start = utcnow() + timedelta(seconds=1)
                #########################################


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
                        blob.name, data, thermostat_dataframe, load_date)

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