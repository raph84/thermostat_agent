from datetime import datetime
from pytz import timezone
import pytz
import iso8601
from utils import utcnow, ceil_dt, get_tz, get_utc_tz
from accumulator_entity import Accumulator_Entity
from google.cloud import storage
import pickle
import pandas as pd
import json
import numpy as np

import warnings

from yadt import scan_and_apply_tz, utc_to_toronto



class Accumulator():


    PREFIX = "accumulator-"
    bucket_name = "thermostat_metric_data"

    class A:
        def __init__(self, entity, blob):
            self.entity = entity
            self.blob = blob

        def release(self):
            try:
                self.blob.temporary_hold = False
                self.blob.patch()
            except:
                print("There was no hold.")

    def __init__(self, logger):

        self.logger = logger

        self.entities = []
        # Instantiates a client
        self.storage_client = storage.Client()
        # The name for the new bucket
        self.bucket = self.storage_client.bucket(self.bucket_name)

    def __del__(self):
        for e in self.entities:
            print("Accumulator deletion")
            e.release()

    def get_filename(self, dt):
        filename = dt.isoformat()
        filename = self.PREFIX + filename
        return filename

    def store_and_release(self,single=True):

        for e in self.entities:
            e.entity.house_keeping()
            pickle_dump = pickle.dumps(e.entity)

            e.blob = self.bucket.get_blob(e.blob.name)
            e.blob.upload_from_string(data=pickle_dump)
            e.release()
            if single:
                break

    def create_and_store(self):
        entity = Accumulator_Entity()
        entity.dt = ceil_dt(utcnow(), 15)

        filename = self.get_filename(entity.dt)

        blob = self.bucket.blob(filename)
        pickle_dump = pickle.dumps(entity)
        blob.upload_from_string(data=pickle_dump)

        a = Accumulator.A(entity, blob)

        return a

    def load(self, n=1, hold=False):
        self.entities = []
        blobs = list(
            self.storage_client.list_blobs(self.bucket_name,
                                           prefix=self.PREFIX))

        if len(blobs) >= n:
            rng = range(-1, 0 - int(n) - 1, -1)
            for i in rng:
                b = self.bucket.get_blob(blobs[i].name)
                if (b.temporary_hold):
                    now = utcnow()
                    while b.temporary_hold:
                        elapse = utcnow() - now
                        if elapse.seconds >= 10:
                            b.temporary_hold = False
                            b.patch()
                        b = self.bucket.get_blob(blobs[i].name)


                pickle_load = b.download_as_bytes()
                e = pickle.loads(pickle_load)

                a = Accumulator.A(e, b)
                self.entities.append(a)
        else:
            a = self.create_and_store()

            self.entities = self.entities.append(a)


        last_date = self.entities[0].entity.dt
        now = utcnow()
        if last_date.day != now.day:
            a = self.create_and_store()
            self.entities = self.entities.append(a)


    def add_temperature2(self, d, value_dict={}):
        value_present = False
        for k in list(value_dict.keys()):
            if value_dict.get(k) is not None:
                if isinstance(value_dict.get(k), (bool)):
                    value_dict[k] = int(value_dict.get(k))
                if not isinstance(value_dict.get(k), (int, float)) or k == 'timestamp':
                    self.logger.warn(
                        "Accumulator only accepts int, float or boolean - {} : {}"
                        .format(k, value_dict.get(k)))
                    del value_dict[k]
                else:
                    value_present = True

        if not value_present:
            raise ValueError

        self.load(n=1, hold=True)

        part = ceil_dt(d, 15)
        if self.entities[0].entity.dt < part:
            self.logger.info(
                "Last partition was for {}. Now we need a new one for {}.".
                format(self.entities[0].entity.dt.isoformat(),
                       part.isoformat()))

            self.entities = [self.create_and_store()]

        self.entities[0].entity.add_temperature2(d, value_dict=value_dict)
        self.store_and_release()
        try:
            self.entities[0].blob.temporary_hold = True
            self.entities[0].blob.patch()
        except Exception as ex:
            self.logger.warn("Blob HOLD failed : {}".format(ex))


    def add_temperature(self, d, temp=None, humidity=None, motion=None, stove_exhaust_temp=None, temp_basement=None):
        """ Deprecated
            Please use add_temperature(self, d, value_dict={}):
        """
        warnings.warn(
            "add_temperature(self, d, temp=None, humidity=None, motion=None, stove_exhaust_temp=None, temp_basement=None) is deprecated",
            DeprecationWarning,
            stacklevel=2)

        if temp is None and humidity == None and motion == None and stove_exhaust_temp == None and temp_basement == None:
            raise ValueError

        self.load(n=1, hold=True)

        part = ceil_dt(d, 15)
        if self.entities[0].entity.dt < part:
            self.logger.info(
                "Last partition was for {}. Now we need a new one for {}.".
                format(self.entities[0].entity.dt.isoformat(), part.isoformat()))

            self.entities = [self.create_and_store()]

        self.entities[0].entity.add_temperature(d, temp, humidity, motion, stove_exhaust_temp, temp_basement)
        self.store_and_release()
        try:
            self.entities[0].blob.temporary_hold = True
            self.entities[0].blob.patch()
        except Exception as ex:
            self.logger.warn("Blob HOLD failed : {}".format(ex))

    def to_dict(self):
        # resp = []
        # for e in self.entities:
        #     resp.append(e.entity.to_dict())
        df = self.to_df().replace({np.nan: None})
        df['dt'] = df.index.values
        df['dt'] = df['dt'].apply(lambda x: utc_to_toronto(x).isoformat())
        if 'timestamp' in df:
            del df['timestamp']
        return {"accumulation":df.to_dict('records')}

    def to_json_records(self):
        records_dict = self.to_dict()
        response = ''
        for i in records_dict['accumulation']:

            response = response + json.dumps(i) + '\n'

        return response

    def to_df(self):
        df = pd.DataFrame()
        for e in self.entities:
            df = df.append(e.entity.temperature)
        df.sort_index(inplace=True)
        df = df.applymap(lambda x: np.nan if x is None else x)

        if 'motion' in df:
            m = df['motion'].copy(deep=True)
            m = m.apply(lambda x: 1 if x else 0)
            m = m.resample('3min').sum()
            m = (m - m.mean()) / (m.max() - m.min())
            m = m.apply(lambda x: x + 1)
            m = m.ewm(halflife='6Min', times=m.index).mean()
            m = m.apply(lambda x: x - 1)
            m = m.resample('15min').sum()
            # TODO percentile
            temp = (m.max() - m.min()) / 2
            m = m.apply(lambda x: True if x >= temp else False)

            del df['motion']
            df = df.resample('15Min').mean().interpolate('linear')
            df = df.merge(m, left_index=True, right_index=True)

        else:
            df = df.resample('15Min').mean().interpolate('linear')
            df['motion'] = False

        df['current_occupancy_flag'] = df['motion']


        return df
