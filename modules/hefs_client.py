import requests
import datetime

API_ENDPOINT = "https://api.water.noaa.gov/hefs/v1"

class HEFSGauge:
    def __init__(self, gaugeId:str):
        self.session = requests.Session()

        # Gauge ID is equvalent to location_id in the API
        self.gaugeId = gaugeId.upper()

    def _GetLatestForecastDatetime(self):
        query_params = {
            "location_id": self.gaugeId,
            "parameter_id": "QINE",
            "limit": 2

        }   
        response = self.session.get(f"{API_ENDPOINT}/ensembles", params=query_params)
        latest_forecast_datetime = response.json()[0][0].get('forecast_datetime')
        return latest_forecast_datetime

    
    def GetForecastFlowMean(self):
        parameters_id = "QINE"
        query_params = {
            "parameter_id": parameters_id,
            "location_id": self.gaugeId
            #"forecast_datetime": '2025-11-26T01:43:26.268Z'
        }   
        response = self.session.get(f"{API_ENDPOINT}/hydrograph-quantiles", params=query_params)
        
        first_forecast = response.json()['value_set'][0]['quantile_values'][5]
        return first_forecast
    
    def GetForecastFlowMax(self, forecast_interval):

        last_forecast_datetime = self._GetLatestForecastDatetime()

        parameters_id = "QINE"
        query_params = {
            "parameter_id": parameters_id,
            "location_id": self.gaugeId,
            "forecast_datetime": last_forecast_datetime
        }   
        response = self.session.get(f"{API_ENDPOINT}/hydrograph-quantiles", params=query_params)
        
        first_forecast = response.json()['value_set'][forecast_interval]['max_value']
        forecast_time = response.json()['value_set'][forecast_interval]['valid_datetime']
        return (first_forecast, forecast_time)
    

