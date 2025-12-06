
import modules.hefs_client as hefs
import modules.map_fldpln as map_fldpln
import modules.nwps_client as nwps
import pandas as pd

def main():


    gauge01 = "IDPK1"
    gauge02 = "CFVK1"

    hefs_g1 = hefs.HEFSGauge(gauge01)
    g1_flow, date01 = hefs_g1.GetForecastFlowMax(13)

    hefs_g2 = hefs.HEFSGauge(gauge02)
    g2_flow, date02 = hefs_g2.GetForecastFlowMax(13)

    nwps_g1 = nwps.NWPSGauge(gauge01)
    g1_stage = nwps_g1.ConvertFlowToStage(g1_flow)

    nwps_g2 = nwps.NWPSGauge(gauge02)
    g2_stage = nwps_g1.ConvertFlowToStage(g2_flow)

    gaugeInfo01 = nwps_g1.GetGaugeInfo()
    gaugeInfo02 = nwps_g2.GetGaugeInfo()
    absStage01 = g1_stage + nwps_g1.GetAbsoluteGaugeHeight()
    absStage02 = g2_stage + nwps_g2.GetAbsoluteGaugeHeight()
    

    x1,y1 = nwps_g1.GetGaugeProjectedXY()
    x2,y2 = nwps_g2.GetGaugeProjectedXY()

    gaugeStageDf = pd.DataFrame({
        'stationid': [gaugeInfo01["lid"], gaugeInfo02["lid"]],
        'x' : [x1,x2],
        'y' : [y1,y2],
        'stage_elevation' : [absStage01, absStage02]

    })

    exportName = f'verdigris_{gauge01}_{date01}_{gauge02}_{date02}'

    # map_fldpln.ComputeDepthMap(gaugeStageDf, exportName)

    print(f"{gauge01} Date : {date01}")
    print(f'Flow : {g1_flow} | Stage : {g1_stage}')

    print(f"{gauge02} Date : {date02}")
    print(f'Flow : {g2_flow} | Stage : {g2_stage}')




if __name__ == "__main__":
    main()