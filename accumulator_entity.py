import pandas as pd
from utils import utcnow, ceil_dt
from yadt import scan_and_apply_tz

import warnings



class Accumulator_Entity():

    def __init__(self):
        self.temperature = None
        self.dt = None

    def house_keeping(self):
        if self.temperature is not None:
            self.temperature.dropna(axis=0, how='all', inplace=True)

            # TODO temporary data cleanup. Remove after 2020-12-22
            # if 'currentcoil_power' in self.temperature:
            #     for k in list(self.temperature.keys()):
            #         self.temperature[k.replace(
            #             "current", "current_")] = self.temperature.pop(k)

            # # TODO temporary data cleanup. Remove after 2020-12-22
            # if 'currentCoil Power' in self.temperature:
            #     for k in list(self.temperature.keys()):
            #         self.temperature[k.lower().replace(
            #             "current", "current_")
            #             .replace(" ", "_")] = self.temperature.pop(k)

            # # TODO temporary data cleanup. Remove after 2020-12-22
            # if 'current_direct_solar_rad.' in self.temperature:
            #     for k in list(self.temperature.keys()):
            #         self.temperature[k.replace(
            #             ".",
            #             "")] = self.temperature.pop(k)

            # # TODO temporary data cleanup. Remove after 2020-12-22
            # if 'mpcindoor_temp_setpoint' in self.temperature:
            #     for k in list(self.temperature.keys()):
            #         self.temperature[k.replace(
            #                 "mpc", "mpc_")] = self.temperature.pop(k)

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