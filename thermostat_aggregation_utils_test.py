from thermostat_aggregation_utils import value_function_basement, find_temperature_original_payload


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