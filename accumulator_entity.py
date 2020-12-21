import pandas as pd
from utils import utcnow, ceil_dt

import warnings



class Accumulator_Entity():

    def __init__(self):
        self.temperature = None
        self.dt = None

    def house_keeping(self):
        self.temperature.dropna(axis=0, how='all', inplace=True)

    def temp_dict(self,
                  temp=None,
                  humidity=None,
                  motion=None,
                  stove_exhaust_temp=None,
                  temp_basement=None):
        t = {
            "temperature": temp,
            "humidity": humidity,
            "stove_exhaust_temp": stove_exhaust_temp,
            "motion": motion,
            "temp_basement": temp_basement
        }

        return t

    def add_temperature2(self, d, value_dict={}):
        df_t = pd.DataFrame(value_dict, index=[d])
        if self.temperature is not None:
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
        resp_df['dt'] = pd.to_datetime(resp_df.index)
        resp_df['dt'] = resp_df['dt'].apply(lambda x: x.isoformat())
        resp_df.sort_index(inplace=True)
        r = resp_df.to_dict(orient='records')
        resp = {
            "dt": self.dt.isoformat(),
            "temperature": r
        }

        return resp