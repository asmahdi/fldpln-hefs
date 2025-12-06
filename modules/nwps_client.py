import requests
import json
from typing import List, Tuple, Optional, Dict, Any
from pyproj import Transformer
# Define the type for a single Rating Curve point (Flow, Stage)
RatingPoint = Tuple[float, float]

API_ENDPOINT = "https://api.water.noaa.gov/nwps/v1"

class NWPSGauge:

    def __init__(self, gaugeId:str):
        self.session = requests.Session()
        self.gaugeId = gaugeId.upper()
        self.cache: Dict[str, List[RatingPoint]] = {}
        self.baseAPI = f"{API_ENDPOINT}/gauges/{self.gaugeId}"
        self.gaugeInfo = {}


    # Coordinate conversion function
    def _Gcs2Pcs(self,lat, lon, fromEpsgCode, toEpsgCode):
        transformer = Transformer.from_crs(f"EPSG:{fromEpsgCode}", f"EPSG:{toEpsgCode}", always_xy=True)
        x, y = transformer.transform(lon, lat) 
        return (x, y)
    
    def NgsVerticalDatumConversion(self, lat, lon, hDatum, inVertDatum, outVertDatum, orthoHt, heightUnit):
        # if hDatum != 'NAD83(1986)':
        #     raise ValueError("This function only supports hDatum 'NAD83(1986)'")
        
        if inVertDatum not in ['NGVD29', 'NAVD88']:
            raise ValueError("inVertDatum must be either 'NGVD29' or 'NAVD88'")
        
        if heightUnit not in ['meters', 'feet']:
            raise ValueError("heightUnit must be either 'meters' or 'feet'")
        
        url = "https://geodesy.noaa.gov/api/ncat/llh"
        params = {
            'lat': lat,
            'lon': lon,
            'inDatum': hDatum,
            'outDatum': hDatum,
            'inVertDatum': inVertDatum,
            'outVertDatum': outVertDatum,
            'orthoHt': orthoHt/ 3.28084 if heightUnit == 'feet' else orthoHt,
        }
        
        response = requests.get(url, params=params)
        
        if response.status_code != 200:
            raise Exception(f"Error fetching data from NGS service: {response.status_code}")
        
        data = response.json()
        
        if 'destOrthoht' not in data:
            raise Exception("Output orthometric height not found in response")

        if data['heightUnits'] == 'm':
            if heightUnit == 'feet':
                outOrthoHt = float(data['destOrthoht']) * 3.28084
            else:
                outOrthoHt = float(data['destOrthoht']) 
        else:
            if heightUnit == 'meters':
                outOrthoHt = float(data['destOrthoht']) / 3.28084
            else:
                outOrthoHt = float(data['destOrthoht'])

        return outOrthoHt


    def _FetchRatingCurve(self ) -> List[RatingPoint]:

        response = self.session.get(self.baseAPI+"/ratings?sort=ASC")
        response.raise_for_status()
        ratings= response.json()['data']

        rating_curve: List[RatingPoint] = []
        for point in ratings:
            flow = point.get('flow')
            stage = point.get('stage')
            if flow is not None and stage is not None:
                rating_curve.append((flow, stage))
        
        rating_curve = sorted(rating_curve, key=lambda x:x[0])

        self.cache[self.gaugeId] = rating_curve
        return rating_curve
    
    def _InterpolateFlowToStage(self, flow, curve):
        pointsCount = len(curve)

        if pointsCount < 2:
            return None
        
        # Curve is already sorted by flow (Q)
        Q_min, H_min = curve[0]
        Q_max, H_max = curve[-1]
        
        # 1. Handle edge cases (flow outside the known range)
        if flow <= Q_min:
            return H_min 
        
        if flow >= Q_max:
            return H_max

        # 2. Find the two bounding points
        Q_low, H_low = curve[0]
        
        # Iterate to find the segment where Q_low < flow < Q_high
        for i in range(1, pointsCount):
            Q_high, H_high = curve[i]
            if flow < Q_high:
                # Found the bounding segment
                break
            Q_low, H_low = Q_high, H_high
        
        # 3. Apply Linear Interpolation
        if Q_high == Q_low:
             return H_low 

        # Interpolation Formula
        H_forecast = H_low + (flow - Q_low) * (H_high - H_low) / (Q_high - Q_low)

        return H_forecast
        
    def ConvertFlowToStage(self, flow: float) -> Optional[float]:
        """
        The main public method. Takes a gauge ID and a flow value, fetches/caches 
        the rating curve, and returns the corresponding stage.
        """
        
        # 1. Check Cache
        if self.gaugeId not in self.cache:
            # 2. If not cached, fetch and parse the data
            curve = self._FetchRatingCurve()
            if curve is None:
                print(f"Error: Conversion failed for {self.gaugeId}. Could not load rating curve.")
                return None
            self.cache[self.gaugeId] = curve
        
        # 3. Retrieve curve from cache
        rating_curve = self.cache[self.gaugeId]
        
        # 4. Perform conversion
        return self._InterpolateFlowToStage(flow, rating_curve)
    

    def GetGaugeInfo(self):
        response = self.session.get(self.baseAPI)
        response.raise_for_status()

        data = response.json()

        self.gaugeInfo["lid"] = data["lid"]
        self.gaugeInfo["usgsId"] = data["usgsId"]
        self.gaugeInfo["vDatum"] = data["datums"]["vertical"]["value"][0]["abbrev"]
        self.gaugeInfo["vDatumElevation"] = data["datums"]["vertical"]["value"][0]["value"]
        self.gaugeInfo["lat"] = data["latitude"]
        self.gaugeInfo["lon"] = data["longitude"]
        self.gaugeInfo["hDatum"] = "NAD27"
        self.gaugeInfo["hDatumEPSG"] = 4267

        return self.gaugeInfo
    
    def GetGaugeProjectedXY(self):
        self.GetGaugeInfo()
        return self._Gcs2Pcs(self.gaugeInfo["lat"], self.gaugeInfo["lon"], self.gaugeInfo["hDatumEPSG"], 26914)

        

    def _ConvertVerticalDatumToNAVD88(self):
        self.GetGaugeInfo()

        # Project coordinates to UTM 14N NAD83 (EPSG:26914) from EPSG 4269 [!!needs automation!!]
        x, y = self._Gcs2Pcs(self.gaugeInfo["lat"], self.gaugeInfo["lon"], self.gaugeInfo["hDatumEPSG"], 26914)
        
        # Convert vertical datum to NAVD88 if necessary
        if self.gaugeInfo['vDatum'] == 'NGVD29':
            navd88_elevation = self.NgsVerticalDatumConversion(
                self.gaugeInfo["lat"],
                self.gaugeInfo["lon"],
                self.gaugeInfo['hDatum'],
                'NGVD29',
                'NAVD88',
                self.gaugeInfo["vDatumElevation"],
                'feet'
            )
        else:
            navd88_elevation = self.gaugeInfo['vDatumElevation']
        
        return navd88_elevation


    def GetAbsoluteGaugeHeight(self):
        return self._ConvertVerticalDatumToNAVD88()     


    
