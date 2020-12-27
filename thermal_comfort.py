from flask import Blueprint
import json
from flask import current_app
import os

from thermostat_accumulate import get_accumulate

from pythermalcomfort.models import pmv_ppd
from pythermalcomfort.psychrometrics import v_relative
from pythermalcomfort.utilities import met_typical_tasks

thermal_comfort = Blueprint('thermal_comfort', __name__)



@thermal_comfort.route('/ppd/', methods=['GET'])
def retrieve_ppd():

    result = ppd()

    return result


def ppd(tdb=25,
        tr=25,
        rh=50,
        met=1.2,
        clo=0.5,
        wme=0):
    """Calculate PMV and PPD
    Arguments
    tdb : Dry bulb air temp
    tr : mean radiant temp
    vr : relative air velocity
    rh : relative humidity
    met : metabolic rate
    clo : clothing insulation

    Reference values for met : 
    - 'Cooking': 1.8
    - 'Filing, seated': 1.2
    - 'House cleaning': 2.7
    - 'Reading, seated': 1.0
    - 'Reclining': 0.8¸
    - 'Seated, quiet': 1.0
    - 'Sleeping': 0.7
    - 'Typing': 1.1
        from pythermalcomfort.utilities import met_typical_tasks
        print(met_typical_tasks['Filing, standing'])
    """
    accumulate = get_accumulate(
                    load=1, hold=False,
                    logger = current_app.logger
                ).to_dict()['accumulation'][0]
    
    result = ppd_from_accumulation_data(accumulation = accumulate)
    
    return result


def ppd_from_accumulation_data(accumulation):
    v_r = v_relative(v=0.1, met=1.2)

    results = pmv_ppd(
        tdb=accumulation['temperature'],  #25
        tr=accumulation['temperature'],  #25
        vr=v_r,
        rh=accumulation['humidity'],  #50
        met=met_typical_tasks['Seated, quiet'],
        clo=0.5,
        wme=0,
        standard="ISO")
    print(results)

    return {"ppd": results['ppd']}
