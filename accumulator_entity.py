import pandas as pd
import numpy as np
from utils import utcnow, ceil_dt
from yadt import scan_and_apply_tz, get_tz

import warnings


def check_index(df):
    if 'datetime64[ns, America/Toronto]' not in str(df.index.dtype):
        df = df.reset_index()
        df['index'] = df['index'].apply(
            lambda x: get_tz().localize(x.replace(tzinfo=None)))
        df = df.set_index(['index'])

    return df


class Accumulator_Entity():

    def __init__(self, logger):
        self.temperature = None
        self.dt = None


    def house_keeping(self):
        if self.temperature is not None:
            self.temperature.dropna(axis=0, how='all', inplace=True)
        self.temperature = check_index(self.temperature)




    def temp_dict(self,
                  temp=None,
                  humidity=None,
                  motion=None,
                  stove_exhaust_temp=None,
                  temp_basement=None):

        warnings.warn(
            "add_temperature(self, d, temp=None, humidity=None, motion=None, stove_exhaust_temp=None, temp_basement=None) is deprecated",
            DeprecationWarning,
            stacklevel=2)


        t = {
            "temperature": temp,
            "humidity": humidity,
            "stove_exhaust_temp": stove_exhaust_temp,
            "motion": motion,
            "temp_basement": temp_basement
        }

        return t




    def add_temperature2(self, d, value_dict={}):
        value_dict = scan_and_apply_tz(value_dict)
        df_t = pd.DataFrame(value_dict, index=[d])
        df_t = df_t.applymap(lambda x: np.nan if x is None else x)
        if "occupancy_flag" in self.temperature:
            self.temperature["occupancy_flag"].apply(lambda x: 0 if x.isnan() else x)

        if self.temperature is not None:
            df_t = check_index(df_t)
            self.temperature = check_index(self.temperature)
            self.temperature = self.temperature.append(df_t)
        else:
            self.dt = ceil_dt(d, 15)
            self.temperature = df_t


    def add_temperature(self, d, temp=None, humidity=None, motion=None, stove_exhaust_temp=None, temp_basement=None):
        warnings.warn(
            "add_temperature(self, d, temp=None, humidity=None, motion=None, stove_exhaust_temp=None, temp_basement=None) is deprecated",
            DeprecationWarning,
            stacklevel=2)

        t = self.temp_dict(temp,
                           humidity,
                           motion,
                           stove_exhaust_temp,
                           temp_basement)
        df_t = pd.DataFrame(t, index=[d])

        if self.temperature is not None:
            self.temperature = self.temperature.append(df_t)
        else:
            self.dt = ceil_dt(d, 15)
            self.temperature = df_t

    def to_dict(self):
        resp_df = self.temperature

        #TODO Remove after 2020-12-22
        resp_df = resp_df.applymap(lambda x: np.nan if x is None else x)
        resp_df['dt'] = pd.to_datetime(resp_df.index)
        resp_df['dt'] = resp_df['dt'].apply(lambda x: x.isoformat())
        resp_df.sort_index(inplace=True)
        r = resp_df.to_dict(orient='records')
        resp = {
            "dt": self.dt.isoformat(),
            "temperature": r
        }

        return resp