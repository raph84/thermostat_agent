# To add a new cell, type '# %%'
# To add a new markdown cell, type '# %% [markdown]'
# %%
from IPython import get_ipython

# %%
import os
os.environ[
    "GOOGLE_APPLICATION_CREDENTIALS"] = "C:\\Users\\T834432\\Documents\\personnel\\thermostat\\thermostat-agent\\thermostat-292016-05700c0efdbe__.json"
os.environ["PROJECT_ID"] = "thermostat-292016"
os.environ["ACTION_THRESHOLD"] = "1.0"

from google.cloud import storage
#from thermostat import get_metric_list_from_bucket, bucket_name, storage_client
from yadt import parse_date, apply_tz_toronto
from datetime import datetime, timedelta
import pandas as pd
import json
import pickle
import numpy as np

# Instantiates a client
storage_client = storage.Client()
# The name for the new bucket
bucket = storage_client.bucket("thermostat_metric_data")

# %%
b = bucket.get_blob('_thermostat_metric_data.p')

pickle_load = b.download_as_bytes()
thermostat_metric_data = pickle.loads(pickle_load)
thermostat_metric_data.sort_index(inplace=True)
#thermostat_metric_data['hash'] = pd.util.hash_pandas_object(thermostat_metric_data)
#thermostat_metric_data = thermostat_metric_data[~thermostat_metric_data.duplicated(keep='first')]
thermostat_metric_data

# %%
import pandas as pd
from yadt import scan_and_apply_tz, utcnow
import json
from datetime import datetime
from thermostat_aggregation_utils import aggregate_to_dataframe, metric_str_to_json

from tqdm import tqdm

from os import listdir
from os.path import isfile, join

#thermostat_metric_data = pd.DataFrame()
#onlyfiles = [f for f in listdir('dump') if isfile(join('dump', f))]
#onlyfiles.reverse()

onlyfiles = [
    f for f in listdir('dump') if isfile(join('dump', f)) and (f.startswith(
        'thermostat-') or f.startswith('environment_sensor_basement-'))
]

existing_files = set(thermostat_metric_data['filename'].tolist())
onlyfiles = set(onlyfiles) - existing_files

print(f"Files to process : {len(onlyfiles)}")

load_date = utcnow()

exist = 0
processed = 0
for f in tqdm(onlyfiles):

    with open('dump/' + f, 'r') as file:
        data = file.read().replace('\n', '')
        #print(f)
        try:
            last_json = metric_str_to_json(data)

            merge, thermostat_metric_data = aggregate_to_dataframe(
                f, last_json, thermostat_metric_data, load_date)

            if merge:
                #print(f"Import {f}")
                processed = processed + 1
            else:
                #print(f"PASS - {f}")
                exist = exist + 1

            #if exist > 200:
            #break

        except Exception as e:
            raise e
            #else:
            #    pass
            #print(data)

thermostat_metric_data

raise Exception

# %%
thermostat_metric_data[thermostat_metric_data['filename'].str.startswith(
    'environment')].index.max()

# %%
thermostat_metric_data['location']

# %%
#thermostat_metric_data['location'] = thermostat_metric_data.apply(lambda x : x['site'] if pd.isna(x['location']) else x['location'], axis = 1)
#thermostat_metric_data = thermostat_metric_data[~thermostat_metric_data.duplicated(keep='first')]
thermostat_metric_data.sort_index(inplace=True)
thermostat_metric_data

# %%
pickle_dump = pickle.dumps(thermostat_metric_data)
b = bucket.blob('_thermostat_metric_data.p')
b.temporary_hold = False
b.patch()
b.upload_from_string(data=pickle_dump, content_type='text/plain')

# %%
pickle.dump(thermostat_metric_data, open("test/_thermostat_metric_data.p",
                                         "wb"))

# %%
thermostat_metric_data[thermostat_metric_data['location'] == 'house.basement']

# %%
onlyfiles = [
    f for f in listdir('dump')
    if isfile(join('dump', f)) and f.startswith('environment')
]
x = onlyfiles.index('environment_sensor_basement-20201220-151228')
del onlyfiles[:x]
len(onlyfiles)

# %%
get_ipython().run_line_magic('load_ext', 'autoreload')
get_ipython().run_line_magic('autoreload', '2')

# %%

pickle_dump = pickle.dumps(onlyfiles)
b = bucket.blob('thermostat_metric_list.p')

b.upload_from_string(data=pickle_dump, content_type='text/plain')

# %%
b = bucket.get_blob('thermostat_metric_list.p')

pickle_load = b.download_as_bytes()
test = pickle.loads(pickle_load)
test

# %%
pd.util.hash_pandas_object(test)

# %%
pd.util.hash_pandas_object(test)

# %%

# %%
t = thermostat_metric_data[thermostat_metric_data['location'] ==
                           'house.basement.stove'].copy(deep=True)
t

# %%
