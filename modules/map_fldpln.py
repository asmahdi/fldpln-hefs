import time

import os
# import the mapping and gauge modules from the fldpln package
from fldpln.gauge import *
from fldpln.mapping import *



def ComputeDepthMap(gaugeStageDf, fileName):
    # SNAP GAUGES TO FSPs ---------------------------------------------------
    #------------------------------------------------------------------------

    # [Need to move this to a config file later]
    projectPath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    # set up map folder
    outMapFolderName = 'verd_4gauges_filtered' 

    # tiled library folder
    libFolder =  projectPath + "/data/lib/tile"

    # libraries to be mapped, i.e., gauge stages will be snapped to the FSPs in those libraries.
    libs2Map = ['verdigris'] # 5/27
    # libs2Map = ['neosho'] # lower Neosho on 5/27 and upper Neosho on 5/10

    # Set output folder
    outputFolder = projectPath + "/exports"

    gaugeFspDf = SnapGauges2Fsps(libFolder,libs2Map,gaugeStageDf,snapDist=350,gaugeXField='x',gaugeYField='y',fspColumns=['FspX','FspY','StrOrd','DsDist','SegId','FilledElev']) 

    # calculate gauge FSP's DOF
    gaugeFspDf['Dof'] = gaugeFspDf['stage_elevation'] - gaugeFspDf['FilledElev']

    # keep only necessary columns for gauge FSPs
    gaugeFspDf = gaugeFspDf[['lib_name','FspX','FspY','StrOrd','DsDist','SegId','FilledElev','Dof']] # Note that 'lib_name','FspX', 'FspY' together uniquely identify a FSP!!!

    # Find libs where the gauges are snapped to, and they are the actual libs to map
    libs2Map = gaugeFspDf['lib_name'].drop_duplicates().tolist()

    # END OF SNAPPING GAUGES TO FSPs --------------------------------------
    #----------------------------------------------------------------------

    # INTERPOLATION -------------------------------------------------------
    #---------------------------------------------------------------------- 

    # prepare the DF for storing interpolated FSP DOF
    fspDof = pd.DataFrame(columns=['LibName','FspId','Dof'])

    # prepare DFs for saving interpolated FSPs and their segment IDs
    fspCols = fspInfoColumnNames + ['Dof']
    segIdCols = ['SegId','LibName']
    fsps = pd.DataFrame(columns=fspCols)
    segIds =pd.DataFrame(columns=segIdCols)

    # map each library
    for libName in libs2Map:
        # interpolate DOF for the gauges

        fspIdDof = InterpolateFspDofFromGaugeThroughVolume(libFolder, libName, gaugeFspDf, netType='Filtered',dsPropSegNum=2)
        fspIdDof['LibName'] = libName
        fspDof = pd.concat([fspDof,fspIdDof[['LibName','FspId','Dof']]], ignore_index=True)

        # Keep interpolated FSP DOF for saving later
        fspFile = os.path.join(libFolder, libName, fspInfoFileName)
        fspDf = pd.read_csv(fspFile) 
        fspDf = pd.merge(fspDf,fspDof,how='inner',on=['FspId'])
        fsps = pd.concat([fsps,fspDf], ignore_index=True)
        
        # Keep FSP segment IDs for saving later
        t =  pd.DataFrame(fspDf['SegId'].drop_duplicates().sort_values())
        t['LibName'] = libName
        segIds = pd.concat([segIds,t], ignore_index=True)


    # Save DOF and segment IDs to CSV files
    FspDofFile = os.path.join(outputFolder, 'Interpolated_FSP_DOF.csv')
    SegIdFile = os.path.join(outputFolder, 'Interpolated_SegIds.csv')
    fsps.to_csv(FspDofFile, index=False)
    segIds.to_csv(SegIdFile, index=False)

    # END OF INTERPOLATION ----------------------------------------------------
    #--------------------------------------------------------------------------



    # MAPPING --------------------------------------------------------------------
    #----------------------------------------------------------------------------- 

    # set up map folder
    outMapFolderName = fileName

    # Create folders for storing temp and output map files
    outMapFolder, scratchFolder = CreateFolders(outputFolder,'scratch',outMapFolderName)

    # whether mosaci tiles as a single COG
    mosaicTiles = True #True #False

    # check running time
    startTimeAllLibs = time.time()

    # dict to store lib processing time
    libTime={}

    # map each library
    for libName in libs2Map:
        # check running time
        startTime = time.time()
        
        # select the FSPs within the lib
        fspIdDof = fspDof[fspDof['LibName']==libName][['FspId','Dof']]

        # mapping flood depth
        print(f'Map {libName} ...')
        tileTifs = MapFloodDepthWithTiles(libFolder,libName,'snappy',outMapFolder,fspIdDof,aoiExtent=None)
        print(f'Actual mapped tiles: {tileTifs}')

        # Mosaic all the tiles from a library into one tif file
        if mosaicTiles and not(tileTifs is None):
            print('Mosaic tile maps ...')
            mosaicTifName = outMapFolderName+'.tif'
            # Simplest implementation, may crash with very large raster
            MosaicGtifs(outMapFolder,tileTifs,mosaicTifName,keepTifs=False)
        
        # check time
        endTime = time.time()
        usedTime = round((endTime-startTime)/60,3)
        libTime[libName] = usedTime


    # Show processing time
    # Individual lib processing time
    print('Individual library mapping time:', libTime)
    # total time
    endTimeAllLibs = time.time()
    print('Total processing time (minutes):', round((endTimeAllLibs-startTimeAllLibs)/60,3))

    # END OF MAPPING -------------------------------------------------------------
    #-----------------------------------------------------------------------------

