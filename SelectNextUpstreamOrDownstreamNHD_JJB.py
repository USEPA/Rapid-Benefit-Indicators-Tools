"""
# Tool Name:  Find Next Upstream or Downstream NHD
# Author: Marc Weber and Tad Larsen
# Date: October 3, 2014
# Select upstream or downstream feature from a
# selected NHDPlus feature (stream line or catchment)
"""
# Import system modules
import os, arcpy, sys
#import struct, decimal, itertools
from collections import deque, defaultdict

"""Selection Query String from list
Purpose: return a string for a where clause from a list of field values
"""
def selectStr_by_list(field, lst):
    exp = ''
    for item in lst:
        exp += '"' + field + '" = ' + str(item) + " OR "
    return (exp[:-4])

"""Intersect Boolean
Purpose: returns T/F if two layers intersect at all
"""
def intersect_boolean(lyr1, lyr2):
    arcpy.SelectLayerByLocation_management(lyr1, 'intersect', lyr2)
    cnt = int(arcpy.GetCount_management(lyr1)[0])
    if cnt == 0:
        return False
    else:
        return True

# Main Function
if __name__ == "__main__":
    #ADD CODE TO SELECT Catchment using restoration site
    #InputFC = sys.argv[1] # NHDPlus feature
    InputFC = r"C:\ArcGIS\Local_GIS\NHD_Plus\NHDPlusNationalData\NHDPlusV21_National_Seamless.gdb\NHDPlusCatchment\Catchment" #selection on FC in GDB
    #InputField = sys.argv[2] # Field with COMID or FEATUREID
    InputField = "FEATUREID" #field from feature layer
    Path = arcpy.Describe(InputFC).Path
    arcpy.env.workspace = Path
    #UpDown = sys.argv[3]
    UpDown = "Downstream" #alt = "Upstream"
    #if (InputFC == "Catchment"):
    #    Flow = Path.replace('NHDPlusCatchment','NHDPlusAttributes')+'\PlusFlow.dbf' #replace(*old*, *new*) 
    #else:
    #    Flow = Path.replace('NHDSnapshot\\Hydrography','NHDPlusAttributes')+'\PlusFlow.dbf'
    Flow = Path.replace('\\NHDPlusCatchment','\\PlusFlow')

    RestorationSite = r"L:\Public\jbousqui\Code\Python\Python_Addins\Tier1_pyt\Test_Results\Intermediates2.gdb\Results"

    #make FCs into lyrs
    arcpy.MakeFeatureLayer_management(RestorationSite, "RestorationSite_lyr")
    arcpy.MakeFeatureLayer_management(InputFC, "InputFC_lyr")
    
    try:
        #STEP 1: pull to/from out into memory
        UpCOMs = defaultdict(list)
        DownCOMs = defaultdict(list)
        #FeatureclassName = arcpy.Describe(InputFC).Name #don't think this is used
        arcpy.AddMessage("Gathering info on upstream / downstream relationships")
        with arcpy.da.SearchCursor(Flow, ["FROMCOMID", "TOCOMID"]) as cursor:
            for row in cursor:
                FROMCOMID = row[0]
                TOCOMID = row[1]
                if TOCOMID != 0:
                    UpCOMs[TOCOMID].append(TOCOMID)
                    DownCOMs[FROMCOMID].append(TOCOMID)
        #infile = open(Flow, 'rb')
        #arcpy.AddMessage("Making list from dbf file.")
        #data = list(dbfreader(infile))
        #infile.close()
        #for line in data[2:]:
        #    FROMCOMID=line[0]
        #    TOCOMID=line[3]
        #    UpCOMs[TOCOMID].append(FROMCOMID)
        #    DownCOMs[FROMCOMID].append(TOCOMID)
        #for k in UpCOMs.iterkeys():
        #    for items in UpCOMs[k]:
        #        if items == 0:
        #            UpCOMs[k] = []
        #for k in DownCOMs.iterkeys():
        #    for items in DownCOMs[k]:
        #        if items == 0:
        #            DownCOMs[k] = []
        
        #STEP 2: Get start IDs from input
        #select catchment using restoration site
        arcpy.SelectLayerByLocation_management("InputFC_lyr", 'intersect', "RestorationSite_lyr")
        COMID_lst = [] #set instead? would eliminate duplicates
        with arcpy.da.SearchCursor(InputFC_lyr, [InputField]) as cursor:
            for row in cursor:
                COMID_lst.append(row[0])
#QUESTION: Nest function into each row instead of using list?
        #STEP 3: Use IDs list to find upstream/downstream
        for COMID in COMID_lst:
            if UpDown == "Upstream":
                arcpy.AddMessage("Finding next upstream feature(s)...")
                #stuff = str(UpCOMs[COMID]).strip('[]')
                selection = selectStr_by_list(InputField, UpCOMs[COMID])
            if UpDown == "Downstream":
                arcpy.AddMessage("Finding next downstream feature(s)...")
                #stuff = str(DownCOMs[COMID]).strip('[]')
                selection = selectStr_by_list(InputField, DownCOMs[COMID])
            #arcpy.SelectLayerByAttribute_management(InputFC,"NEW_SELECTION",selection)
            arcpy.MakeFeatureLayer_management(InputFC, "InputFC_lyr", selection, "", "")
#OR IF THERE is no upstream/downstream (reached end of network)
            if outsideTest("InputFC_lyr", boundary) == False:
                #add to selection
                repeat process using current selection
            else:
                FinalSelection
                
            #loop this section until selection is outside of buffer
            #if InputFC is within Buffer == TRUE:
                
        #rows = arcpy.SearchCursor(InputFC)
        #for row in rows:
        #    COMID = (row.getValue("%s"%(InputField)))
            
                if UpDown == "Upstream":
                    stuff = str(UpCOMs[COMID]).strip('[]')
                    string = "\"%s\" IN (%s)"%(InputField,stuff)
                    arcpy.AddMessage("Adding upstream features(s) to selection...")
                    arcpy.SelectLayerByAttribute_management(InputFC,"ADD_TO_SELECTION",string)
                
                if UpDown == "Downstream":
                    stuff = str(DownCOMs[COMID]).strip('[]')
                    string = "\"%s\" IN (%s)"%(InputField,stuff)
                    arcpy.AddMessage("Adding downstream features(s) to selection...")
                    arcpy.SelectLayerByAttribute_management(InputFC,"ADD_TO_SELECTION",string)
        #Else:
                    arcpy.AddMessages("Selection complete")
        arcpy.AddMessage(" ")
    except:
      arcpy.GetMessages()
