from .thermostat_aggregation_utils import aggregate_to_dataframe, date_function_thermostat, value_function_thermostat, aggregator_item, metric_str_to_json, value_function_basement, find_temperature_original_payload, aggregate_thermostat_dataframe, check_thermostat_dataframe_up2date, thermostat_dataframe_timeframe, date_selection_realtime, utcnow
from .yadt import parse_date, utc_to_toronto
import pickle
import pandas as pd

def test_aggregate_to_dataframe():
    filename = 'thermostat-20210110-134156'

    data = {}
    with open('test/{}'.format(filename), 'r') as file:
        data['data'] = file.read().replace('\n', '')

    data['filename'] = filename
    data['load_date'] = utcnow()

    data['data'] = metric_str_to_json(data['data'])
    df = pd.DataFrame()
    merge, df = aggregate_to_dataframe([data], df)

    assert utc_to_toronto(df.index.max().to_pydatetime()) == parse_date(
        '2021-01-10T08:41:56.000000-05:00'), utc_to_toronto(
            df.index.max().to_pydatetime())


def test_aggretor_item():
    filename = 'thermostat-20210110-134156'
    with open('test/{}'.format(filename), 'r') as file:
        data = file.read().replace('\n', '')

    item = metric_str_to_json(data)[0]

    metric_dict = aggregator_item(filename, item, date_function_thermostat, value_function_thermostat)

    assert metric_dict['dt'] == parse_date(
        '2021-01-10T08:41:56.000000-05:00'), metric_dict['dt']


def test_find_temperature_original_payload():
    temperature = find_temperature_original_payload(
        "device_id:environment-sensor; location:house.basement; temperature:24.04; humidity:37.41"
    )
    assert temperature is not None, temperature

def test_value_function_basement():

    values = {
        "temperature": None,
        "original_payload" : "device_id:environment-sensor; location:house.basement; temperature:24.04; humidity:37.41"
    }

    assert 'temperature' in values.keys(), values

    result = value_function_basement(values)

    assert 'temp_basement' in result.keys(), result
    assert 'temperature' not in result.keys(), result
    assert result['temp_basement'] is not None, result

def test_value_function_basement_invalid_temp():
    values = {
        "temperature":
        "device_id:environment-sensor; location:house.basement; temperature:21.02",
        "original_payload":
        "device_id:environment-sensor; location:house.basement; temperature:21.02; humidity:38.68"
    }


    result = value_function_basement(values)

    assert result['temp_basement'] == 21.02, result


def test_value_function_basement_temp_in_array():
    # environment_sensor_basement-20201220-151449
    values = {
        "temperature": ["21.02"],
        "original_payload":
        "device_id:environment-sensor; location:house.basement; temperature:21.02; humidity:38.68"
    }

    result = value_function_basement(values)

    assert result['temp_basement'] == 21.02, result




def test_date_selection_realtime():

    dt_start = parse_date('2021-01-09T08:15:00.000000-05:00')
    dt_end = parse_date('2021-01-09T09:15:00.000000-05:00')

    dt_test = parse_date('2021-01-09T10:15:00.000000-05:00')
    select, end = date_selection_realtime(dt_test,dt_end, dt_start)
    assert select == False and end == False, 'After the selected timeframe : end == False({}) & select == False({})'.format(select, end)

    dt_test = parse_date('2021-01-09T09:00:00.000000-05:00')
    select, end = date_selection_realtime(dt_test, dt_end, dt_start)
    assert select == True and end == False, 'Inside the selected timeframe : end == False({}) & select == True({})'.format(
        select, end)

    dt_test = parse_date('2021-01-09T08:00:00.000000-05:00')
    select, end = date_selection_realtime(dt_test, dt_end, dt_start)
    assert select == False and end == True, 'Before the selected timeframe : end == True({}) & select == False({})'.format(
        select, end)


# def test_aggregate_thermostat_dataframe():

#     thermostat_dataframe = pickle.load(open("test/_thermostat_metric_data.p", "rb"))

#     dt_start = parse_date('2021-01-09T08:15:00.000000-05:00')
#     dt_end = parse_date('2021-01-09T09:15:00.000000-05:00')

#     df = thermostat_dataframe_timeframe(thermostat_dataframe, dt_start, dt_end)

#     df, df_motion = aggregate_thermostat_dataframe(df, 'house.kitchen')

#     assert df.index.min() == parse_date('2021-01-09T08:15:00.000000-05:00'), df.index.min()
#     assert df.index.max() == parse_date('2021-01-09T09:15:00.000000-05:00'), df.index.max()
#     assert 'Occupancy Flag' in df, df.columns
#     assert df.isnull().sum().sum() == 0, df.isnull().sum().sum()


def test_check_thermostat_dataframe_up2date():

    thermostat_dataframe = pickle.load(
        open("test/_thermostat_metric_data.p", "rb"))

    dt_start = parse_date('2021-01-09T08:15:00.000000-05:00')
    check = check_thermostat_dataframe_up2date(dt_start, thermostat_dataframe)
    assert check, check