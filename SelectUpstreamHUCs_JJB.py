"""
# Tool Name:  Find Upstream
# Author: Marc Weber
# Date: October 15, 2009
# Code to leverage HUC12_DS attribute in national WBD dataset
# and collect all upstream HUC as values in a dictionary
"""
# Import system modules
import os, arcpy, sys
import struct, decimal, itertools
from collections import deque, defaultdict
from arcpy import da

def children(token, tree):
    "returns a list of every child"
    visited = set()
    to_crawl = deque([token])
    while to_crawl:
        current = to_crawl.popleft()
        if current in visited:
            continue
        visited.add(current)
        node_children = set(tree[current])
        to_crawl.extendleft(node_children - visited)
    return list(visited)

    
#Main Function
if __name__ == "__main__":
    InputFC = sys.argv[1] # HUC12 geodatabase feature
    InputHUC = sys.argv[2] # Field indicating selected HUC
    #InputDownHUC = sys.argv[3] # Field indicating HUC downstream
    Path = arcpy.Describe(InputFC).Path
    FileGDBName = os.path.basename(Path)
    #arcpy.env.workspace = Path
    Flow = Path.replace('\\NHDPlusCatchment','\\PlusFlow')
    try:
        #STEP 1: pull to/from out into memory
        UpCOMs = defaultdict(list)
        DownCOMs = defaultdict(list)
        arcpy.AddMessage("Gathering info on upstream / downstream relationships")
        with arcpy.da.SearchCursor(Flow, ["FROMCOMID", "TOCOMID"]) as cursor:
            for row in cursor:
                FROMCOMID = row[0]
                TOCOMID = row[1]
                if TOCOMID != 0:
                    UpCOMs[TOCOMID].append(TOCOMID)
                    DownCOMs[FROMCOMID].append(TOCOMID)
        #arcpy.AddMessage(" ")
        arcpy.AddMessage("/n" + "Finding All Upstream Features for " + Flow + "/n")
        #arcpy.AddMessage(" ")
        #arcpy.da.SearchCursor(inputFC, [InputHUC, InputDownHUC]) as cursor:
        #    for row in cursor:
        #    HUC12 = row[0]
        #    Down_HUC = row[1]
        #    upHUCs[Down_HUC] = HUC12

        UpHUCs = defaultdict(list)
        #FeatureclassName = arcpy.Describe(InputFC).Name
        HUCList = [] # this list holds rid of selected features
        arcpy.da.SearchCursor(inputFC, [InputHUC]) as cursor:
            for row in cursor:
                HUCList.append(row[0])
            
        #parse through each huc12 in WBD feature dataset
        #rows = arcpy.SearchCursor('%s/%s'%(Path,FeatureclassName))
        #arcpy.AddMessage("Gathering info on HUC upstream / downstream relationships")
        #for row in rows:
        #    HUC12=row.getValue("%s"%(InputHUC))
        #    Down_HUC=row.getValue("%s"%(InputDownHUC))
        #    UpHUCs[Down_HUC] = HUC12
            
        Full_HUCs = dict()
        for item in HUCList:
            Full_HUCs[item] = childern(item, UpCOMs)
            arcpy.AddWarning(str(len(Full_HUCs[item])) + " selected features being processed.  If this is too many, hit Cancel." + "/n")
        #arcpy.AddWarning(str(count) + " Selected features being processed.  If this is too many, hit Cancel.")

        #HUCList.append('170702040305')
        for keys in Full_HUCs.keys():
            stuff = str(Full_HUCs[keys]).strip('[]')
            for stuff in Full_HUCs[hucs]:
                string = "\"%s\" IN (%s)"%(InputHUC,stuff)
                arcpy.AddMessage("Adding catchments to selection...")
                arcpy.SelectLayerByAttribute_management(InputFC, "ADD_TO_SELECTION", string)
    except:
      arcpy.GetMessages()





