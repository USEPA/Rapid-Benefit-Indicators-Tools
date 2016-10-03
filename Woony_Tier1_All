"""
# Name: Tier 1 Rapid Benefit Indicator Assessment
# Purpose: Calculate values for benefit indicators using wetland restoration site polygons
#          and a variety of other input data
# Author: Justin Bousquin
#
# Version Notes:
# Developed in ArcGIS 10.3
# v26 implemented setParam to streamline arcpy.Parameter
# Date: 8/18/2016
"""

import sys, os
from decimal import *
import arcpy
from arcpy import env
from arcpy import da

arcpy.env.parallelProcessingFactor = "100%" #won't matter in most cases

###########FUNCTIONS###########
"""Set Input Parameter
Purpose: returns arcpy.Parameter for provided string, setting defaults for missing."""
def setParam(str1, str2, str3, str4, str5):
    lst = [str1, str2, str3, str4, str5]
    defLst = ["Input", "name", "GpFeatureLayer", "Required", "Input"]
    i = 0
    for str_ in lst:
        if str_ =="":
            lst[i]=defLst[i]
        i+=1       
    return arcpy.Parameter(
        displayName = lst[0],
        name = lst[1],
        datatype = lst[2],
        parameterType = lst[3],
        direction = lst[4])

"""Global Timer
Purpose: returns the message and calc time since the last time the function was used."""
#Function Notes: used during testing to compare efficiency of each step
def exec_time(start, message):
    end = time.clock()
    comp_time = end - start
    arcpy.AddMessage("Run time for " + message + ": " + str(comp_time))
    start = time.clock()
    return start

"""Unique Values
Purpose: returns a sorted list of unique values"""
#Function Notes: used to find unique field values in table column
def unique_values(table, field):
    with arcpy.da.SearchCursor(table, [field]) as cursor:
        return sorted({row[0] for row in cursor if row[0]})

"""Check Spatial Reference
Purpose: checks that a second spatial reference matches the first and re-projects if not."""
#Function Notes: Either the original FC or the re-projected one is returned
def checkSpatialReference(alphaFC, otherFC):
    alphaSR = arcpy.Describe(alphaFC).spatialReference
    otherSR = arcpy.Describe(otherFC).spatialReference
    if alphaSR.name != otherSR.name:
        #e.g. .name = u'WGS_1984_UTM_Zone_19N' for Projected Coordinate System = WGS_1984_UTM_Zone_19N
        arcpy.AddMessage("Spatial reference for " + otherFC + " does not match.")
        try:
            path = os.path.dirname(alphaFC)
            newName = os.path.basename(otherFC)
            output = path + os.sep + newName[:-4] + "_prj.shp"
            arcpy.Project_management(otherFC, output, alphaSR)
            fc = output
            arcpy.AddMessage("File was re-projected and saved as " + fc)
        except:
            arcpy.AddMessage("Warning: spatial reference could not be updated.")
            fc = otherFC
    else:
        fc = otherFC
    return fc

"""Donut Buffer
Purpose: takes inside buffer and creates outside buffers. Ensures ORIG_FID is correct."""
#Function Notes: there can be multiple buffer distances, but must be list
def buffer_donut(FC, outFC, buf, units):
    FCsort = FC[:-4] + "_2.shp" #the buffers should all be in the outTbl folder
    arcpy.Sort_management(FC, FCsort, [["ORIG_FID", "ASCENDING"]]) #sort FC by ORGI_FID
    arcpy.MultipleRingBuffer_analysis(FCsort, outFC, buf, units, "Distance", "NONE", "OUTSIDE_ONLY") #new buffer
    arcpy.Delete_management(FCsort) #Delete intermediate FC
    return outFC

"""Buffer Contains
Purpose: returns number of points in buffer as list"""
#Function Notes:
#Example: lst = buffer_contains(view_50, addresses)
def buffer_contains(poly, pnts):
    lst = []
    poly_out = poly[:-4] + "_2.shp" #check to be sure this is created in outTbl folder
    arcpy.SpatialJoin_analysis(poly, pnts, poly_out, "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "INTERSECT", "", "")
    lst = field_to_lst(poly_out, ["ORIG_FID", "Join_Count"])
    arcpy.Delete_management(poly_out)
    
    return lst
"""Buffer Population
Purpose: returns sum of raster cells in buffer as list"""
#Function Notes: Currently works on raster of population total (not density)
#Function Notes: Requires Spatial Analyst (look into rasterstats as alternative?)
#https://pcjericks.github.io/py-gdalogr-cookbook/raster_layers.html
def buffer_population(poly, popRaster):
    lst = []
    tempDBF = poly[:-4]+"_pop.dbf"
    arcpy.sa.ZonalStatisticsAsTable(poly, "FID", popRaster, tempDBF, "", "SUM")
    lst = field_to_lst(tempDBF, ["FID_", "SUM"]) #"AREA" "OID" "COUNT"
    arcpy.Delete_management(tempDBF)
    return lst

"""Percent Cover
Purpose:"""
#Function Notes:
def percent_cover(poly, bufPoly):
    arcpy.MakeFeatureLayer_management(poly, "polyLyr")
    lst=[]
    orderLst=[]
    #add handle for when no overlap?
    with arcpy.da.SearchCursor(bufPoly, ["SHAPE@", "ORIG_FID"]) as cursor:
        for row in cursor:
            totalArea = Decimal(row[0].getArea("PLANAR", "SQUAREMETERS"))
            arcpy.SelectLayerByLocation_management("polyLyr", "INTERSECT", row[0])
            lyrLst = []
            with arcpy.da.SearchCursor("polyLyr", ["SHAPE@"]) as cursor2:
                for row2 in cursor2:
                    interPoly = row2[0].intersect(row[0], 4) #dimension = 4 for polygon
                    interArea = Decimal(interPoly.getArea("PLANAR", "SQUAREMETERS"))
                    lyrLst.append((interArea/totalArea)*100)
            lst.append(sum(lyrLst))
            orderLst.append(row[1])
    #arcpy.Delete_management(polyD)
    #fix above cleanup
    orderLst, lst = (list(x) for x in zip(*sorted(zip(orderLst, lst)))) #sort by ORIG_FID
    return lst

"""Read Field to List
Purpose:"""
#Function Notes: if field is: string, 1 field at a time; list , 1 field at a time or 1st field is used to sort
#Example: lst = field_to_lst("table.shp", "fieldName")
def field_to_lst(table, field):
    lst = []
    if type(field) == str:
        with arcpy.da.SearchCursor(table, [field]) as cursor:
            for row in cursor:
                lst.append(row[0])
    elif type(field) == list:
        if len(field) == 1:
            with arcpy.da.SearchCursor(table, field) as cursor:
                for row in cursor:
                    lst.append(row[0])
        else: #first field is used to sort, second field returned as list
            orderLst = []
            with arcpy.da.SearchCursor(table, field) as cursor:
                for row in cursor:
                    orderLst.append(row[0])
                    lst.append(row[1])
            orderLst, lst = (list(x) for x in zip(*sorted(zip(orderLst, lst))))
    else:
        arcpy.AddMessage("Something went wrong with the field to list function")
    return lst

"""Add List to Field
Purpose: """
#Function Notes: 1 field at a time
#Example: lst_to_field(featureClass, "fieldName", lst)
def lst_to_field(table, field, lst):
    i=0
    with arcpy.da.UpdateCursor(table, [field]) as cursor:
        for row in cursor:
            row[0] = lst[i]
            i+=1
            cursor.updateRow(row)            

"""Calculate Weighted View Score
Purpose: list of weighted view scores."""
#Function Notes: Does not currently test that the lists are of equal length
def view_score(lst_50, lst_100):
    lst =[]
    i=0
    #add test for equal length of lists?
    #if len(lst_50) != len(lst_100):
    #   arcpy.AddMessage("Error in view score function, unequal list lengths")
    #   break
    for item in lst_50:
       lst.append(lst_50[i] * 0.7 + lst_100[i] * 0.3)
       i+=1
    return lst

"""Where clause from list
Purpose: Create where clause using a list of fields"""
def clause_from_list(fieldLst, field):
    start_qry = '"' + field + '" = '
    end_qry = ' OR '
    qry = ''
    for item in fieldLst:
        qry_item = start_qry + str(item) + end_qry
        qry = qry + qry_item
    whereClause = qry[:-4]
    return whereClause

"""Custom Error Message
Purpose: error message shortcut"""
def error_message(text):
    arcpy.AddMessage("ERROR occured while " + text + ".")
###########MODULES############
############VIEWS#############
"""VIEW_MODULE1: creates buffers around the site and determines how many people are in those buffers"""
def VIEW_MODULE1(path, outTbl, addresses, popRaster):
    start = time.clock() #start the clock for module
    #set variables
    viewArea = path + "view"
    view_50, view_100 = viewArea + "_50.shp", viewArea + "_100.shp" #50 and 100m buffers

    #create buffers 
    arcpy.Buffer_analysis(outTbl, view_50, "50 Meters") #buffer each site by 50-m
    buffer_donut(view_50, view_100, [50], "Meters") #distance past original buffer

    #calculate number benefitting in buffers
    if addresses is not None: #address based method
        addresses = checkSpatialReference(outTbl, addresses) #check projections
        
        lst_view_50 = buffer_contains(view_50, addresses)
        lst_view_100 = buffer_contains(view_100, addresses)
        lst_view_score = view_score(lst_view_50, lst_view_100) #calculate weighted scores

        start=exec_time(start, "scenic views analysis: 3.2 How Many Benefit? -analysis using addresses")
        #cleanup
        arcpy.Delete_management(view_50)
        arcpy.Delete_management(view_100)
    elif popRaster is not None: #population based method
        lst_view_50 = buffer_population(view_50, popRaster)
        lst_view_100 = buffer_population(view_100, popRaster)
        lst_view_score = view_score(lst_view_50, lst_view_100) #calculate weighted scores
        
        start=exec_time(start, "scenic views analysis: 3.2 How Many Benefit? - analysis using a population Raster")
    else: #should already be handled before calling module
        arcpy.AddMessage("No address or population data available for analysis")
    return lst_view_50, lst_view_100, lst_view_score, addresses

"""VIEW_MODULE2: creates buffers around the site and determines if trails or roads cross through those buffers"""
def VIEW_MODULE2(path, outTbl, trails, roads):
    start = time.clock() #start the clock for module
    rteLst = []
    viewArea = path + "view"
    view_100_int = viewArea + "_v100int.shp"
    #generate a complete 100m buffer
    arcpy.Buffer_analysis(outTbl, view_100_int, "100 Meters")
    
    if trails is not None:
        trails = checkSpatialReference(outTbl, trails) #check projections
        lst_view_trails_100 = buffer_contains(view_100_int, trails) #trails in buffer?
        if roads is not None:
            roads = checkSpatialReference(outTbl, roads) #check projections
            lst_view_roads_100 = buffer_contains(view_100_int, roads) #roads in buffer?
            i=0
            for item in lst_view_trails_100:
                if (lst_view_trails_100[i] == 0) and (lst_view_roads_100[i] == 0):
                    rteLst.append("NO")
                    i+=1
                else:
                    rteLst.append("YES")
                    i+=1
        else:
            for item in lst_view_trails_100:
                if (item == 0):
                    rteLst.append("NO")
                else:
                    rteLst.append("YES")     
    elif roads is not None:
        roads = checkSpatialReference(outTbl, roads) #check projections
        lst_view_roads_100 = buffer_contains(view_100_int, roads) #roads in buffer?

        for i in lst_view_roads_100:
            if (i == 0):
                rteLst.append("NO")
            else:
                rteLst.append("YES")
    return rteLst

"""VIEW_MODULE3: Substitutes/Scarcity"""
def VIEW_MODULE3(path, outTbl, wetlandsOri):
    start = time.clock() #start the clock for module
    wetlandsOri = checkSpatialReference(outTbl, wetlandsOri) #check projections
    wetlands_dis = path + "wetland_dis.shp"
#FIX next line, cannot create output wetlands_dis (L:\Public\jbousqui\Code\Python\Python_Addins\Tier1_pyt\Test_Results\wetlands_dis.shp)
    arcpy.Dissolve_management(wetlandsOri, wetlands_dis) #Dissolve wetlands fields
    wetlandsOri = wetlands_dis

    view_200 = path + "view200.shp" #200m buffer
    #make a 200m buffer that doesn't include the site
    arcpy.MultipleRingBuffer_analysis(outTbl, view_200, 200, "Meters", "Distance", "NONE", "OUTSIDE_ONLY")
    lst_view_Density = percent_cover(wetlandsOri, view_200) #wetlands in 200m
    start=exec_time(start, "scenic views analysis: 3.3B Scarcity")
    return lst_view_Density, view_200 #200m buffer is used later

"""VIEW_MODULE4: complements"""
def VIEW_MODULE4(path, outTbl, landUse, view_200, fieldLst, field):
    start = time.clock() #start the clock for module
    landUse = checkSpatialReference(outTbl, landUse) #check projections
                
    if view_200 is None: #create buffer called view_200 if it doesn't already exist
        view_200 = outTbl[:-4] + "view200.shp"
        arcpy.MultipleRingBuffer_analysis(outTbl, view_200, 200, "Meters", "Distance", "NONE", "OUTSIDE_ONLY")

    arcpy.MakeFeatureLayer_management(landUse, "lyr")
    whereClause = clause_from_list(fieldLst, field) #construct query from field list
    arcpy.SelectLayerByAttribute_management("lyr", "NEW_SELECTION", whereClause) #reduce to desired LU
    landUse2 = outTbl[:-4] + "_comp.shp"
    arcpy.Dissolve_management("lyr", landUse2, field) #reduce to unique
    
    lst_comp = buffer_contains(view_200, landUse2) #number of unique LU in LU list which intersect each buffer
    return lst_comp

##############################
###########TOOLBOX############
class Toolbox(object):
    def __init__(self):
        self.label = "Indicator Tools"
        self.alias = "Tier_1"
        # List of tool classes associated with this toolbox
        self.tools= [Tier_1_Flood, Tier_1_Scenic_views, Tier_1_SocialEquity_Tool,
                     Tier_1_Reliability_Tool, Tier_1_Indicator_Tool, Report_Generator_Tool, LCCBuffer]

#############################  
###########FLOODING##########
class Tier_1_Flood (object):
    def __init__(self):
        self.label = "Tier 1 Flood Damage Reduction" 
        self.description = "This tool performs the Tier 1 Indicators assessment " + \
                           "for flood reduction benefits on a desired set of wetlands or wetlands restoration sites"

    def getParameterInfo(self):
    #Define IN/OUT parameters
        restorationSites = setParam("Restoration Site Polygons", "in_poly", "", "", "")
        addresses = setParam("Address Points", "in_pnts", "", "Optional", "")#beneficiaries points
        popRast = setParam("Population Raster", "popRast", "DERasterDataset", "Optional", "")#beneficiaries raster
        #special datasets (only appear if boxes are checked)
        floodZone = setParam("FEMA Flood Polygons", "Flood_Zone", "", "Optional", "")
        #flood stream? #Need some way to tell what is downstream
        #wetlands
        existingWetlands = setParam("Other Wetland Polygons","in_poly","","","")
        #roads?
        dams = setParam("Dams or Levees", "in_subs", "", "", "")
        #outputs
        outTbl = setParam("Output", "outTable", "DEFeatureClass", "", "Output")
        #could code this as a folder or updated wetland shp instead, info table?
        #could be made optional with an over write default
        params = [restorationSites, addresses, popRast, floodZone, existingWetlands, dams, outTbl]
        return params

    def isLicensed(self):
        return True
    def updateParameters(self, params):
        return
    def updateMessages(self, params):
        return
    
    def execute(self, params, messages):
        start = time.clock() #start the clock
        #define variables from user inputs
        wetlands = params[0].valueAsText
        addresses = params[1].valueAsText
        popRast = params[2].valueAsText
        flood_zone = params[3].valueAsText
        ExistingWetlands = params[4].valueAtText
        subs = params[5].valueAsText
        outTbl = params[6].valueAsText
        
        path = os.path.dirname(outTbl) + os.sep
        
        #Copy wetlands in for results
        arcpy.CopyFeatures_management(wetlands, outTbl)

        start=exec_time(start, "intiating variables")
        
        #set variables
        outTbl_flood = path + "int_flood.dbf"
        floodArea = path + "int_FloodArea"

        flood_area = floodArea + ".shp"
        flood_areaB = floodArea + "temp.shp" #buffers
        assets = floodArea + "_assets.shp"
                    
        #step 1: check that there are people in the flood zone
        if addresses is not None:         #if using addresses
            addresses = checkSpatialReference(outTbl, addresses) #check spatial ref
            flood_zone = checkSpatialReference(outTbl, flood_zone) #check spatial ref
            arcpy.Clip_analysis(addresses, flood_zone, assets)
            tot_cnt = arcpy.GetCount_management(assets)
            if int(tot_cnt.getOutput(0)) <= 0:
                arcpy.AddMessage("No addresses were found within the flooded area")
                #add error handel to fail if assets has no entries
        elif popRaster is not None:
            error_message("Nothing to do with input yet")
            #add error handel to fail if floodarea contains no population    
        else:
            error_message("no population inputs")#add error

        #step 2: buffer each site by 5 miles
        arcpy.Buffer_analysis(outTbl, flood_areaB, "2.5 Miles")
        #step 3: clip the buffer to flood polygon
        arcpy.Clip_analysis(flood_areaB, flood_zone, flood_area)
        
        #step 3B: calculate flood area as benefitting percentage
        arcpy.AddField_management(flood_area, "area", "Double")
        arcpy.AddField_management(flood_area, "area_pct", "Double")
        arcpy.CalculateField_management(flood_area, "area", "!SHAPE.area!", "PYTHON_9.3", "")

        with arcpy.da.UpdateCursor(flood_area, ["area_pct", "area", "BUFF_DIST"]) as cursor:
            #BUFF_DIST is used rather than 25 sq miles because it is in the datum units used for area calculation
            #if BUFF_DIST is field in wetlands it was renamed by index in flood_area
            for row in cursor:
                row[0] = row[1]/(math.pi*((row[2]**2)))
                cursor.updateRow(row)
                
        #step 4: calculate number of people benefitting.
        #arcpy.SpatialJoin_analysis(flood_area, assets, outTbl_flood, "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "CONTAINS", "", "")
        lst_flood_cnt = buffer_contains(flood_area, assets) #count addresses in buffer/flood

        start=exec_time(start, "flood analysis")

#service quality
        #calculate area of each restoration site
        siteAreaLst =[]
        with arcpy.da.SearchCursor(outTbl_flood, ["SHAPE@"]) as cursor:
            for row in cursor:
                siteAreaLst.append(row[0].getArea("GEODESIC", "ACRES"))

#Scarcity
        #3.3.B scarcity
        if ExistingWetlands is not None:
            ExistingWetlands = checkSpatialReference(outTbl, ExistingWetlands) #check spatial ref
            lst_floodRet_Density = percent_cover(ExistingWetlands, flood_areaB) #analysis for scarcity
                        
        #Substitutes
        subs = checkSpatialReference(outTbl, subs)
        #list how many dams/levees in flood of buffersmanagement(outTbl, "Flood_sub", "Double")
        lst_to_field(outTbl, "Flood_cnt", lst_subs_cnt)
                                   
        arcpy.AddMessage("Flood Module Complete")
        #lst_subs_cnt = buffer_contains(flood_areaB, subs) # all subs in 2.5 miles
        lst_subs_cnt = buffer_contains(flood_area, subs) #only subs in flood zone
                                           
#final step, move results to results file
#count of beneficiaries = lst_flood_cnt
        arcpy.AddField_management(outTbl, "Flood_cnt", "Double")
        lst_to_field(outTbl, "Flood_cnt", lst_flood_cnt)
#area of each site = siteAreaLst
        arcpy.AddField_management(outTbl, "Flood_acr", "Double")
        lst_to_field(outTbl, "Flood_acr", siteAreaLst)
#scarcitty at each site =lst_floodRet_Density
        arcpy.AddField_management(outTbl, "FScarcity", "Double")
        lst_to_field(outTbl, "Fscarcity", lst_floodRet_Density)
#subs at each site = lst_subs_cnt
        arcpy.AddField_management(outTbl, "Flood_sub", "Double")
        lst_to_field(outTbl, "Flood_sub", lst_subs_cnt)

#cleanup
        arcpy.Delete_management(flood_areaB)
        arcpy.Delete_management(flood_area)
        arcpy.Delete_management(assets)
                                   
        arcpy.AddMessage("Flood Module Complete")
#############################
#########SCENIC VIEWS########
class Tier_1_Scenic_views (object):
    def __init__(self):
        self.label = "Tier 1 Scenic Views" 
        self.description = "This tool performs the Tier 1 Indicators assessment " + \
                           "for scenic view benefits on a desired set of wetlands or wetlands restoration sites"

    def getParameterInfo(self):
    #Define IN/OUT parameters
        RestorationSites = setParam("Restoration Site Polygons", "in_poly", "", "", "") #sites
        addresses = setParam("Address Points", "in_pnts", "","Optional", "") #beneficiaries points
        popRast = setParam("Population Raster", "popRast", "DERasterDataset", "Optional", "") #beneficiaries raster
        roads = setParam("Roads (streets, highways, etc.)", "roads", "", "Optional", "")
        trails = setParam("Trails (hiking, biking, etc.)", "trails", "", "Optional", "")
        #pre-existing wetlands
        preWetlands = setParam("Wetland Polygons", "in_wet", "", "Optional", "")
        landUse = setParam("Land use or greenspace Polygons", "land_use","", "Optional", "")       
        fieldLULC = setParam("Landuse Field", "LULCFld", "Field", "Optional", "")
        #outputs
        outTbl = setParam("Output", "outTable", "DEFeatureClass", "Required", "Output")
        #could code this as a folder or updated wetland shp instead, info table?
        #could be made optional with an over write default
        params = [RestorationSites, addresses, popRast, roads, trails, preWetlands, landUse, fieldLULC, outTbl]
        return params

    def isLicensed(self):
        return True
    def updateParameters(self, params):
        return
    def updateMessages(self, params):
        return
    
    def execute(self, params, messages):
        start = time.clock() #start the clock

        sites = params[0].valueAsText
        addresses = params[1].valueAsText
        popRaster = params[2].valueAsText
        roads = params[3].valueAsText
        trails = params[4].valueAsText
        wetlandsOri = params[5].valueAsText
        landUse = params[6].valueAsText
        fieldLst = params[7].valueAsText
        outTbl = params[8].valueAsText
        path = os.path.dirname(ouTbl)
        
        if addresses is not None or popRaster is not None:
            lst_view_100, lst_view_50, lst_view_score, addresses = VIEW_MODULE1(path, outTbl, addresses, popRaster)     
            start=exec_time(start, "scenic views analysis: 3.2 How Many Benefit?")
        else:
            arcpy.AddMessage("No address or population raster available for analysis")
        if (trails is not None) or (roads is not None):
            rteLst = VIEW_MODULE2(path, outTbl, trails, roads)
        else:
            arcpy.AddMessage("No Roads or trails available to determine 3.2.3 for Views")
        start=exec_time(start, "scenic views analysis: 3.2 How Many Benefit?")
        if wetlandsOri is not None:
            lst_view_Density, view_200 = VIEW_MODULE3(path, outTbl, wetlandsOri)
        else:
            arcpy.AddMessage("No wetlands available to determine 3.3.B Substitutes and Scarcity for Views")
            view_200 = None
        if landUse is not None: #analysis for complements
            lst_comp = VIEW_MODULE4(path, outTbl, landUse, view_200, fieldLst, field)
        else:
            arcpy.AddMessage("No Landuse available to determine 3.3.C Complements for Views")
        ####add results to table###
        arcpy.AddField_management(outTbl, "VCnt_100", "Double") #lst_view_100
        arcpy.AddField_management(outTbl, "VCnt_50", "Double") #lst_view_50
        arcpy.AddField_management(outTbl, "VScore", "Double") #lst_view_score
        arcpy.AddField_management(outTbl, "V_YN_3_2", "TEXT") #rteLst
        arcpy.AddField_management(outTbl, "Vscarcity", "Double") #lst_view_Density
        arcpy.AddField_management(outTbl, "Vcomp_cnt", "Double") #lst_comp
                  
        lst_to_field(outTbl, "VCnt_100", lst_view_100)
        lst_to_field(outTbl, "VCnt_50", lst_view_50)
        lst_to_field(outTbl, "VScore", lst_view_score)
        lst_to_field(outTbl, "V_YN_3_2", rteLst)
        lst_to_field(outTbl, "Vscarcity", lst_view_Density)
        lst_to_field(outTbl, "Vcomp_cnt", lst_comp)
#############################
########SOCIAL EQUITY########
class Tier_1_SocialEquity_Tool (object):
    def __init__(self):
        self.label = "Tier 1 Social Equity" 
        self.description = "This tool performs the Tier 1 Social Equity Indicators assessment " + \
                           "on a desired set of wetlands or wetlands restoration sites"

    def getParameterInfo(self):
    #Define IN/OUT parameters
        #sites
        RestorationSites = setParam("Restoration Site Polygons", "in_poly", "", "", "")
        SocialVulnerability = setParam("SoVI", "sovi_poly", "", "", "")
        #user must select 1 field to base calculation on
        SoVI_Field = setParam("SoVI Score", "SoVI_ScoreFld","Field", "", "")
        #distance beneficiaries travel
        distance = setParam("Buffer Distance", "bufferUnits", "GPLinearUnit", "", "")
        #outputs
        outTbl = setParam("Output", "outTable", "DETable", "", "Output")
        #could code this as a folder or updated wetland shp instead, info table?
        #could be made optional with an over write default
        
	#Set the FieldsList to be filtered by the list from the feature dataset
        SoVI_Field.parameterDependencies = [SocialVulnerability.name]
        distance.parameterDependencies = [RestorationSites.name]

        #set defaults
        SoVI_Field.defaultEnvironmentName = "SoVI0610_1"
        #distance = "2.5 Miles"
        
        #Set drop downs to be disabled initially
        #SoVI_Field.enabled = False
        
        params = [RestorationSites, SocialVulnerability, SoVI_Field, distance, outTbl]

        return params

    def isLicensed(self):
        return True
    def updateParameters(self, params):
        return
    def updateMessages(self, params):
        return
    
    def execute(self, params, messages):
        start = time.clock() #start the clock

        #define variables from user inputs
        sites = params[0].valueAsText
        sovi = params[1].valueAsText
        field = params[2].valueAsText
        bufferDist = params[3].valueAsText
        outTbl = params[4].valueAsText

        #field = "SoVI0610_1"
        #dist = "2.5"
        #units = "Miles"
        #bufferDist = dist + " " + units
        
        #copy sites as outTbl
        arcpy.CopyFeatures_management(sites , outTbl)
        #check projections
        sovi = checkSpatialReference(outTbl, sovi)
        
        #make layer for Poly
        arcpy.MakeFeatureLayer_management(sovi, "soviLyr")
        #FC copy of sovi buffers
        tempPoly = outTbl[:-4] + "SoviTemp.shp"

        #buffer site by user specified distance
        buf = outTbl[:-4] + "sovi.shp"
        arcpy.Buffer_analysis(sites, buf, bufferDist)

        #add fields for each unique in field?
        fieldLst = unique_values(sovi, field)
        arcpy.AddMessage("There are " + str(len(fieldLst)) + " unique values for " + field + ".")
        for itemRaw in fieldLst:
            item = itemRaw.replace(" ", "_")[0:9]
            arcpy.AddField_management(outTbl, item, "DOUBLE", "", "", "", itemRaw, "", "", "")
            whereClause = field + " = '" + item + "'"
            arcpy.SelectLayerByAttribute_management("soviLyr", "NEW_SELECTION", whereClause)
            pct_lst = percent_cover("soviLyr", buf)
            lst_to_field(outTbl, item, pct_lst)
            
#############################
#########RELIABILITY#########
class Tier_1_Reliability_Tool (object):
    def __init__(self):
        self.label = "Tier 1 Reliability" 
        self.description = "This tool performs the Tier 1 Site Reliability Indicators assessment " + \
                           "on a desired set of wetlands or wetlands restoration sites"

    def getParameterInfo(self):
    #Define IN/OUT parameters
        #sites
        RestorationSites = setParam("Restoration Site Polygons", "in_poly", "", "", "")
        Conservation = setParam("Conservation lands", "cons_poly", "", "", "")
        Conserve_Field = setParam("Conservation Field", "Conservation_Field", "Field", "", "")
        #user must select 1 field to base calculation on
        #good values
        useType1 = setParam("First Conservation Type", "Conservation_Type1", "GPString", "Optional", "")
        useType2 = setParam("Second Conservation Type", "Conservation_Type2", "GPString", "Optional", "")
        useType3 = setParam("Third Conservation Type", "Conservation_Type3", "GPString", "Optional", "")
        useType4 = setParam("Fourth Conservation Type", "Conservation_Type4", "GPString", "Optional", "")
        useType5 = setParam("Fifth Conservation Type", "Conservation_Type5", "GPString", "Optional", "")
        #Bad values?
        threatType1 = setParam("First Threat Type", "Threat_Type1", "GPString", "Optional", "")
        #distance beneficiaries travel
        distance = setParam("Buffer Distance", "bufferUnits", "GPLinearUnit", "", "")
        #outputs
        outTbl = setParam("Output", "outTable", "DEFeatureClass", "", "Output")
#could code this as a folder or updated wetland shp instead, info table?
#could be made optional with an over write default
        
        #Set the List to be filtered by the list from the feature dataset
        Conserve_Field.parameterDependencies = [Conservation.name]
        distance.parameterDependencies = [RestorationSites.name]
        
        #set drop downs to be disabled initially
        useType2.enabled = False
        useType3.enabled = False
        useType4.enabled = False
        useType5.enabled = False
        
        params = [RestorationSites, Conservation, Conserve_Field, useType1, useType2,
                  useType3, useType4, useType5, threatType1, distance, outTbl]
        
        return params

    def isLicensed(self):
        return True
    def updateParameters(self, params):
        #Modify the values and properties of parameters before internal validation is performed.
        #Called whenever a parameter is changed.
        if params[2].altered:
            in_poly = params[1].valueAsText
            TypeField = params[2].valueAsText
            result = unique_values(in_poly, TypeField)
            params[3].filter.list = result
            params[8].filter.list = result
            if params[3].altered:
                params[4].enabled = True
                #update result to remove entry
                params[4].filter.list = result
                if params[4].altered:
                    params[5].enabled = True
                    params[5].filter.list = result
                    if params[5].altered:
                        params[6].enabled = True
                        params[6].filter.list = result
                        if params[6].altered:
                            params[7].enabled = True
                            params[7].filter.list = result

        return
    def updateMessages(self, params):
        #may need to add
        return
    
    def execute(self, params, messages):
        start = time.clock() #start the clock

        #define variables from user inputs
        sites = params[0].valueAsText
        cons_poly = params[1].valueAsText
        field = params[2].valueAsText
        use1 = params[3].valueAsText
        use2 = params[4].valueAsText
        use3 = params[5].valueAsText
        use4 = params[6].valueAsText
        use5 = params[7].valueAsText
        threat1 = params[8].valueAsText
        bufferDist = params[9].valueAsText
        outTbl = params[10].valueAsText

        #copy sites as outTbl
        arcpy.CopyFeatures_management(sites , outTbl)
        #check projections
        sovi = checkSpatialReference(outTbl, cons_poly)

        #buffer site by user specified distance
        buf = outTbl[:-4] + "conser.shp"
        arcpy.Buffer_analysis(sites, buf, bufferDist)

        whereClause = "" #empty string

        start=exec_time(start, "Reliability assessment initialized")
        
        #make selection from FC based on fields to include
        arcpy.MakeFeatureLayer_management(cons_poly, "consLyr")

        #select conservation use types
        use_lst = [use1, use2, use3, use4, use5]
        for use in use_lst:
            if use != None:
                whereClause = whereClause + " OR " + field + " = '" + use + "'"
        whereClause = whereClause[3:] #remove first " OR "
        arcpy.SelectLayerByAttribute_management("consLyr", "NEW_SELECTION", whereClause)

        #determine percent of buffer which is each conservation type
        pct_lst = percent_cover("consLyr", buf)
        arcpy.AddField_management(outTbl, "Conserved", "DOUBLE")
        lst_to_field(outTbl, "Conserved", pct_lst)

        start=exec_time(start, "Percent conserved use types calculated")
        
        #select threat use types
        threat_lst = [threat1]
        for threat in threat_lst:
            whereClause = whereClause + " OR " + field + " = '" + threat + "'"
        whereClause = whereClause[3:] #remove first " OR "
        arcpy.SelectLayerByAttribute_management("consLyr", "NEW_SELECTION", whereClause)
            
        #determine percent of buffer which is each threat type
        pct_lst = percent_cover("consLyr", buf)
        arcpy.AddField_management(outTbl, "Threatened", "DOUBLE")
        lst_to_field(outTbl, "Threatened", pct_lst)

        start=exec_time(start, "Percent threatend use types calculated")

        arcpy.AddMessage("Reliability assessment complete.")

################################
#########INDICATOR_TOOL#########       
class Tier_1_Indicator_Tool (object):
    def __init__(self):
        self.label = "Tier 1 Indicator Tools" 
        self.description = "This tool performs the Tier 1 Indicators assessment on a desired" + \
                           "set of wetlands or wetlands restoration sites."

    def getParameterInfo(self):
    #Define IN/OUT parameters
        sites = setParam("Restoration Site Polygons", "in_poly", "", "", "")#sites
        addresses = setParam("Address Points", "in_pnts", "", "Optional", "")#beneficiaries points
        popRast = setParam("Population Raster", "popRast", "DERasterDataset", "Optional", "")#beneficiaries raster
        #check boxes for services the user wants to assess
        serviceLst=["Reduced Flooding", "Scenic Views", "Environmental Education", "Bird Watching", "Recreation"]
        view = setParam(serviceLst[1], "view", "GPBoolean", "Optional", "")
        edu = setParam(serviceLst[2], "edu", "GPBoolean", "Optional", "")
        bird = setParam(serviceLst[3], "bird", "GPBoolean", "Optional", "")
        rec = setParam(serviceLst[4], "rec", "GPBoolean", "Optional", "")
        #special datasets (only appear if boxes are checked)
        edu_inst = setParam("Educational Institution Points", "edu_inst", "", "Optional", "")
        bus_stp = setParam("Bus Stop Points", "bus_stp", "", "Optional", "") #could it accomodate lines too?
        trails = setParam("Trails (hiking, biking, etc.)", "trails", "", "Optional", "")
        roads = setParam("Roads (streets, highways, etc.)", "roads", "", "Optional", "")
        #pre-existing wetlands
        preWetlands = setParam("Wetland Polygons", "in_wet", "", "Optional", "")#pre-existing wetlands
        landUse = setParam("Land use or greenspace Polygons", "land_use", "", "Optional", "")
        fieldLULC = setParam("Landuse Field", "LULCFld", "Field", "Optional", "")
#list of fields from table
        #outputs
        outTbl = setParam("Output", "outTable", "DETable", "", "Output")
        #could code this as a folder or updated wetland shp instead, info table?
        #could be made optional with an over write default

        #report = setParam("Report (optional)", "report", "DEMapDocument", "Optional", "Output")

        #dependencies
        fieldLULC.parameterDependencies = [landUse.name]
        
        params = [sites, addresses, popRast, view, edu, bird, rec, edu_inst, bus_stp, trails, roads, preWetlands, landUse, fieldLULC, outTbl]
        return params

    def isLicensed(self):
        return True
    def updateParameters(self, params):
        return
    def updateMessages(self, params):
        return
    
    def execute(self, params, messages):
        start = time.clock() #start the clock
        
        #define variables from user inputs
        sites = params[0].valueAsText
        addresses = params[1].valueAsText
        popRaster = params[2].valueAsText
        view = params[3].value
        edu = params[4].value
        bird = params[5].value
        rec = params[6].value
        edu_inst = params[7].valueAsText
        bus_Stp = params[8].valueAsText
        trails = params[9].valueAsText
        roads = params[10].valueAsText
        wetlandsOri = params[11].valueAsText
        landUse = params[12].valueAsText
        LULCfield = params[13].valueAsText
        outTbl = params[14].valueAsText
        #report = params[15].valueAsText

        #use outTbl path to create GBD for intermediates
        path = os.path.dirname(outTbl) + os.sep
        #outTblName = os.path.basename(out)       
        #arcpy.CreateFileGDB_management(path, "Intermediates", "CURRENT")
        #outTbl = path + "\\Intermediates.gbd\\" + outTblName
        #Copy wetlands in for results

#these variables will come from front end in future
        fieldLst =[430, 410, 162, 161] #add this as front end parameter

        field = LULCfield #field = "LCLU"

        arcpy.CopyFeatures_management(sites , outTbl) #should s

        #if addresses is None and popRaster is not None:
        if popRaster is not None:
            arcpy.CheckOutExtension("Spatial")

        start=exec_time(start, "intiating variables")
#####VIEWS#####
        if view == True:
            if addresses is not None or popRaster is not None:
                lst_view_100, lst_view_50, lst_view_score, addresses = VIEW_MODULE1(path, outTbl, addresses, popRaster)     
                start=exec_time(start, "scenic views analysis: 3.2 How Many Benefit?")
            else:
                arcpy.AddMessage("No address or population raster available for analysis")
            if (trails is not None) or (roads is not None):
                rteLst = VIEW_MODULE2(path, outTbl, trails, roads)
            else:
                arcpy.AddMessage("No Roads or trails available to determine 3.2.3 for Views")
            start=exec_time(start, "scenic views analysis: 3.2 How Many Benefit?")
            if wetlandsOri is not None:
                lst_view_Density, view_200 = VIEW_MODULE3(path, outTbl, wetlandsOri)
            else:
                arcpy.AddMessage("No wetlands available to determine 3.3.B Substitutes and Scarcity for Views")
                view_200 = None
            if landUse is not None: #analysis for complements
                lst_comp = VIEW_MODULE4(path, outTbl, landUse, view_200, fieldLst, field)
            else:
                arcpy.AddMessage("No Landuse available to determine 3.3.C Complements for Views")
            ####add results to table###
            arcpy.AddField_management(outTbl, "VCnt_100", "Double") #lst_view_100
            arcpy.AddField_management(outTbl, "VCnt_50", "Double") #lst_view_50
            arcpy.AddField_management(outTbl, "VScore", "Double") #lst_view_score
            arcpy.AddField_management(outTbl, "V_YN_3_2", "TEXT") #rteLst
            arcpy.AddField_management(outTbl, "Vscarcity", "Double") #lst_view_Density
            arcpy.AddField_management(outTbl, "Vcomp_cnt", "Double") #lst_comp
                      
            lst_to_field(outTbl, "VCnt_100", lst_view_100)
            lst_to_field(outTbl, "VCnt_50", lst_view_50)
            lst_to_field(outTbl, "VScore", lst_view_score)
            lst_to_field(outTbl, "V_YN_3_2", rteLst)
            lst_to_field(outTbl, "Vscarcity", lst_view_Density)
            lst_to_field(outTbl, "Vcomp_cnt", lst_comp)
            
        else: #if Views is not run, set all lists to None. This was temporarily removed
            arcpy.AddMessage("Scenic View Benefits not assessed")
            #lst_view_100 = None
            #lst_view_50 = None
            #lst_view_score = None
            #rteLst = None
            #lst_view_Density = None
            #lst_comp = None

#####EDUCATION#####            
        if edu == True:
            #set variables
            outTbl_edu = path + "edu.dbf"
            eduArea = path + "eduArea.shp"
            
            #1 overlay with edu_inst
            if edu_inst is not None:
                #arcpy.AddMessage("Educational Institution Points Detected") #acknowledge dataset
                edu_inst = checkSpatialReference(outTbl, edu_inst) #check spatial ref
                arcpy.Buffer_analysis(outTbl , eduArea, "0.25 Miles") #buffer each site by 0.25 miles
                lst_edu_cnt = buffer_contains(eduArea, edu_inst) #list how many schools in buffer
                
            #Move info
                arcpy.AddField_management(outTbl, "Edu_cnt", "Double")
                lst_to_field(outTbl, "Edu_cnt", lst_edu_cnt)
            else:
                arcpy.AddMessage("No Educational Institution Points available for analysis")
                
            start=exec_time(start, "value for educational institutions: " + str(edu))

            #3.3.B scarcity
            if wetlandsOri is not None:
                wetlandsOri = checkSpatialReference(outTbl, wetlandsOri) #check spatial ref
                edu_2 = path + "edu2.shp" #buffer 1/2 mile
                
                arcpy.Buffer_analysis(outTbl, edu_2, "0.5 Miles") #not a circle

                lst_edu_Density = percent_cover(wetlandsOri, edu_2) #analysis for scarcity

        #export results to results table
                arcpy.AddField_management(outTbl, "Escarcity", "Double")
                lst_to_field(outTbl, "Escarcity", lst_edu_Density)
            else:
                arcpy.AddMessage("No pre-existing wetlands to determine scarcity")

#####BIRDS#####   
        if bird == True:
            birdArea = path + "birdArea.shp" #set variable
            arcpy.Buffer_analysis(outTbl , birdArea, "0.2 Miles") #buffer each site by 0.2 miles
            
            if addresses is not None:
                edu_inst = checkSpatialReference(outTbl, edu_inst) #check spatial ref
                lst_bird_cnt = buffer_contains(birdArea, addresses) #count addresses in buffer
                start=exec_time(start, "bird watching analysis: 3.2 How Many Benefit? - analysis using a addresses")
                
        #check for population raster
            elif popRaster is not None:
                lst_bird_cnt = buffer_population(birdArea, popRaster)
                start=exec_time(start, "bird watching analysis: 3.2 How Many Benefit? - analysis using a population Raster")
            else:
                arcpy.AddMessage("No address or population raster available for analysis")

#add all results directly from lists at end
            arcpy.AddField_management(outTbl, "BirdCnt", "Double")
            lst_to_field(outTbl, "BirdCnt", lst_bird_cnt)
            start=exec_time(start, "value for bird Booleaan: " + str(bird))
                
            #step 4: are there roads or trails?
            if trails or roads is not None:
                rteLstBird = []
                if trails is not None:
                    trails = checkSpatialReference(outTbl, trails) #check projections
                    lst_bird_trails = buffer_contains(birdArea, trails)
                    if roads is not None:
                        roads = checkSpatialReference(outTbl, roads) #check projections
                        lst_bird_roads = buffer_contains(birdArea, roads)
                        i=0
                        for item in lst_bird_trails:
                            if (lst_bird_trails[i] == 0) or (lst_bird_roads[i] == 0):
                                rteLstBird.append("NO")
                                i+=1
                            else:
                                rteLstBird.append("YES")
                                i+=1       
                    else:
                        for item in lst_bird_trails:
                            if (item == 0):
                                rteLstBird.append("NO")
                            else:
                                rteLstBird.append("YES")
                                
                elif roads is not None:
                    roads = checkSpatialReference(outTbl, roads) #check projections
                    lst_bird_roads = buffer_contains(birdArea, roads)
                    for item in lst_bird_roads:
                        if (item == 0):
                            rteLstBird.append("NO")
                        else:
                            rteLstBird.append("YES")
#add all results directly from lists at end
                arcpy.AddField_management(outTbl, "B_YN_3_2", "TEXT")
                lst_to_field(outTbl, "B_YN_3_2", rteLstBird)

            else:
                arcpy.AddMessage("No Roads or trails available to determine 3.2.3 for Views")    

#####RECREATION#####                        
        if rec == True:
            ###set variables###
            recArea = path + "recArea"

            rec_500m, rec_1000m, rec_10000m= recArea + "_03mi.shp", recArea + "_05mi.shp", recArea + "_6mi.shp" #buffer names
            rec_06, rec_1, rec12 = recArea + "_Add_06mi.shp", recArea + "_Add_1mi.shp", recArea + "_Add_12mi.shp" #scarcirt buffer names
            
            #step 1: buffer each site by 500m, 1km, and 10km
            arcpy.Buffer_analysis(outTbl , rec_500m, "0.333333 Miles")
            buffer_donut(rec_500m, rec_1000m, [0.166667], "Miles")
            buffer_donut(rec_1000m , rec_10000m, [5.666667], "Miles")
            
            #step 2: overlay
            if addresses is not None: #address based method
                lst_rec_cnt_03 = buffer_contains(rec_500m, addresses)
                lst_rec_cnt_05 = buffer_contains(rec_1000m, addresses)
                lst_rec_cnt_6 = buffer_contains(rec_10000m, addresses)

                start=exec_time(start, "value for recreation Buffer analysis using addresses: " + str(rec))

            elif popRaster is not None: #check for population raster
                lst_rec_cnt_03 = buffer_population(rec_500m, popRaster)
                lst_rec_cnt_05 = buffer_population(rec_1000m, popRaster)
                lst_rec_cnt_6 = buffer_population(rec_10000m, popRaster)

                start=exec_time(start, "value for recreation buffer analysis using a population Raster: " + str(rec))
                
            else:
                arcpy.AddMessage("No address or population raster available for analysis")

                ###add to outTable###
                arcpy.AddField_management(outTbl, "RCnt_03", "Double")
                lst_to_field(outTbl, "RCnt_03", lst_rec_cnt_03)
                arcpy.AddField_management(outTbl, "RCnt_05", "Double")
                lst_to_field(outTbl, "RCnt_05", lst_rec_cnt_05)
                arcpy.AddField_management(outTbl, "RCnt_6", "Double")
                lst_to_field(outTbl, "RCnt_6", lst_rec_cnt_6)

                start=exec_time(start, "value for updating table: " + str(rec))
                
            start=exec_time(start, "value for recreation extent of market: " + str(rec))

            if bus_Stp is not None:
                rteLst_rec_bus = []
                bus_Stp = checkSpatialReference(outTbl, bus_Stp) #check projections

                lst_rec_bus = buffer_contains(rec_500m, bus_Stp) #bus stops in 500m
                for i in lst_rec_bus:
                    if (i == 0):
                        rteLst_rec_bus.append("NO")
                    else:
                        rteLst_rec_bus.append("YES")
#add results at end
                arcpy.AddField_management(outTbl, "R_YN_3_22", "TEXT") #update table with new results
                lst_to_field(outTbl, "R_YN_3_22", rteLst_rec_bus)

                start=exec_time(start, "bus stops in walking distance: ")
            else:
                arcpy.AddMessage("Bus stop data were not entered")
                
            if trails is not None:
                rteLst_rec_trails = []
                trails = checkSpatialReference(outTbl, trails) #check projections
                lst_rec_trails = buffer_contains(rec_500m, trails) #bike trails in 500m
                for i in lst_rec_trails:
                    if (i == 0):
                        rteLst_rec_trails.append("NO")
                    else:
                        rteLst_rec_trails.append("YES")
#add results at end
                arcpy.AddField_management(outTbl, "R_YN_3_23", "TEXT") #update table with new results
                lst_to_field(outTbl, "R_YN_3_23", rteLst_rec_trails)

                start=exec_time(start, "trails in walking distance: ")
            else:
                arcpy.AddMessage("trails data were not entered")
                
            if landUse is not None:
                landUse = checkSpatialReference(outTbl, landUse) #check projections
                landuseTEMP = path + os.sep + "landuse_dis.shp" #for dissolve
                
            #area around site which is green space
            #1) use fieldLst and field to identify greenspace

                whereClause = clause_from_list(fieldLst, field)
                arcpy.MakeFeatureLayer_management(landUse, "lyr")
                arcpy.SelectLayerByAttribute_management("lyr", "NEW_SELECTION", whereClause) #reduce to desired LU
                arcpy.Dissolve_management("lyr", landuseTEMP, field)
                #from that landuse selection create a table of neighbors
#                neighborTbl = recArea + "land.dbf"
#                arcpy.PolygonNeighbors_analysis("lyr", neighborTbl, "", "", "BOTH_SIDES", "", "", "")
                
                #from that landuse selection make a selection that overlaps with each site
                #numpy solution
#                import numpy
#                arr=arcpy.da.TableToNumPyArray(neighborTbl, ["src_FID", "nbr_FID"])

#                arr[arr['src_FID']==149]['nbr_FID']]#neighbor FIDs to FID 149

                #arcpy.CopyFeatures_management(lyr_as_fc, "lyr")
                #arcpy.AddField_managment(lyr_as_fc,  "area_acre", "DOUBLE")
                #arcpy.MakeFeatureLayer_management(lyr_as_fc, "lyr2")
                
#                for site in sites: #fix this
#                    neighbors = []
#                    site_lyr = arcpy.SelectLayerByLocation_management("lyr", "INTERSECT", site)
#                    with arcpy.da.SearchCursor(site_lyr, ["FID"]) as cursor:
#                        for row in cusor:
#                            neighbors.append(arr[arr['src_FID']==row[0]]['nbr_FID']]).tolist())
#                    unq_neighbors = set([item for sublist in neighbors for item in sublist]) #add FID?
#                    start_qry = '"FID" = '
#                    end_qry = ' OR '
#                    qry = ''
#                    for neighbor in unq_neighbors:
#                        qry_item = start_qry + str(item) + end_qry
#                        qry = qry + qry_item
#                    whereClause = qry[:-4]
#                    arcpy.SelectLayersByAttribute_management("lyr2", "NEW_SELECTION", whereClause) #select neighbor IDs
                        
            #2) find adjacent to site in landUse
                #site_landuse = recArea + "site_land.shp"
                #arcpy.SpatialJoin_analysis("lyr", sites, site_landuse, "JOIN_ONE_TO_MANY", "KEEP_ALL", "", "INTERSECT", "", "")

                #step 1: buffer each site by double original buffer
                arcpy.Buffer_analysis(outTbl, rec_06, "0.666666 Miles")
                arcpy.Buffer_analysis(outTbl, rec_1, "1 Miles")
                arcpy.Buffer_analysis(outTbl, rec12, "12 Miles")

                #calculate buffer areas in m2
                #arcpy.AddField_management(rec_06, "area_m2", "DOUBLE")
                #arcpy.CalculateField_management(rec_06, "area_m2", "!SHAPE.area@SQUAREMETERS!", "PYTHON_9.3", "")

                #arcpy.AddField_management(rec_1, "area_m2", "DOUBLE")
                #arcpy.CalculateField_management(rec_1, "area_m2", "!SHAPE.area@SQUAREMETERS!", "PYTHON_9.3", "")

                #arcpy.AddField_management(rec12, "area_m2", "DOUBLE")
                #arcpy.CalculateField_management(rec12, "area_m2", "!SHAPE.area@SQUAREMETERS!", "PYTHON_9.3", "")
                                                  
                #analysis for scarcity using "lyr"
                lst_rec_06_Density = percent_cover(landuseTEMP, rec_06)
                #arcpy.Intersect_analysis([landUse, rec_06], landUse3)
                #arcpy.AddField_management(landUse3, "scarce", "Double")

                lst_rec_1_Density = percent_cover(landuseTEMP, rec_1)
                #arcpy.Intersect_analysis([landUse, rec_1], landUse4)
                #arcpy.AddField_management(landUse4, "scarce", "Double")

                lst_rec_12_Density = percent_cover(landuseTEMP, rec12)
                #arcpy.Intersect_analysis([landUse, rec12], landUse5)
                #arcpy.AddField_management(landUse5, "scarce", "Double")

                #export results to outTable
                arcpy.AddField_management(outTbl, "Rscarc_06", "DOUBLE")
                lst_to_field(outTbl, "Rscarc_06", lst_rec_06_Density)

                arcpy.AddField_management(outTbl, "Rscarc_1", "DOUBLE")
                lst_to_field(outTbl, "Rscarc_1", lst_rec_1_Density)

                arcpy.AddField_management(outTbl, "Rscarc_12", "DOUBLE")
                lst_to_field(outTbl, "Rscarc_12", lst_rec_12_Density)
            
            #with arcpy.da.UpdateCursor(landUse3, ["Density", "SHAPE@", "area_m3"]) as cursor:
                #for row in cursor:
                    #row[0] = (row[1].getArea("PLANAR", "SQUAREMETERS")/row[2])*100
                    #cursor.updateRow(row)
            #with arcpy.da.UpdateCursor(landUse4, ["Density", "SHAPE@", "area_m3"]) as cursor:
                #for row in cursor:
                    #row[0] = (row[1].getArea("PLANAR", "SQUAREMETERS")/row[2])*100
                    #cursor.updateRow(row)
            #with arcpy.da.UpdateCursor(landUse5, ["Density", "SHAPE@", "area_m3"]) as cursor:
                #for row in cursor:
                    #row[0] = (row[1].getArea("PLANAR", "SQUAREMETERS")/row[2])*100
                    #cursor.updateRow(row)
        #final step, move results to results file
        #field_lst =[]
        #if flood == True:
            #field_lst.append()
        #if view == True:
            #field_lst.append()
        #if edu == True:
            #field_lst.append()
        #if bird == True:
            #"Join_Count"
            #field_lst.append()
        #if rec == True:
            #field_lst.append()
        #for field in field_lst:
            #"number in 500m" = "Join_Count"
            #"number in 1km" = "Join_Count"
            #arcpy.AddField_management(outTbl, field, "Double")
            else:
                arcpy.AddMessage("Landuse not entered to analyze scarcity")
                
            arcpy.AddMessage("Done running script you crazy mf")


class LCCBuffer(object):
    def __init__(self):
        self.label = "Buffer Extract (Bird Habitat)"
        self.description = 	"This tool creates a buffer around potential restoration sites " + \
                                "and determines how much of that buffer is each landuse type. "
        
    def getParameterInfo(self):
#Define parameters
        in_landuse = setParam("Input Landuse Polygons", "in_landuse", "DEFeatureClass", "", "")
        IDfield = setParam("Landuse Unique ID Field", "LULC_ID", "Field", "Optional", "")
        sitePnts = setParam("Site Point Locations", "sitePnts", "DEFeatureClass", "", "")
        buffer1 = setParam("First Buffer Distance", "bufferUnits", "GPLinearUnit", "", "")      
        buffer2 = setParam("Second Buffer Distance", "buffer2", "GPLinearUnit", "Optional", "")
        buffer3 = setParam("Third Buffer Distance", "buffer3", "GPLinearUnit", "Optional", "")
        out_poly = setParam("Output File", "out_poly", "DEFeatureClass", "", "Output")

        #set the unique LandClass field based on feature dataset
        IDfield.parameterDependencies = [in_landuse.name]
        buffer1.parameterDependencies = [sitePnts.name]
        buffer2.parameterDependencies = [sitePnts.name]
        buffer3.parameterDependencies = [sitePnts.name]

        out_poly.parameterDependencies = [buffer1.name]
        
        #Set drop downs and additional buffers to be disabled initially
        IDfield.enabled = False
        buffer2.enabled = False
        buffer3.enabled = False
        params = [in_landuse, IDfield, sitePnts, buffer1, buffer2, buffer3, out_poly]
        return params

    def isLicensed(self):
        return True

    def updateParameters(self, params):
#Modify the values and properties of parameters before internal validation is performed.
#Called whenever a parameter is changed.
        if params[0].altered:
            params[1].enabled = True
        if params[3].altered:
            params[4].enabled = True
            if params[4].altered:
                params[5].enabled = True
        return

    def updateMessages(self, params):
        return

    def execute(self, params, messages):
#define variables from user inputs
        inPoly =params[0].valueAsText
        sitePnts =params[2].valueAsText
        buffer1 =params[3].valueAsText
        #create list for distances
        bufferLst = [buffer1]
        if params[4].altered:
            buffer2 =params[4].valueAsText
            bufferLst.append(buffer2)
        if params[5].altered:
            buffer3 =params[5].valueAsText
            bufferLst.append(buffer3)
        outPoly = params[6].valueAsText

        IDfield = params[1].valueAsText
        uniqueID = ["ORIG_FID", "LCLU"]

        outTup = os.path.split(inPoly)
        path = outTup[0] + "/"
        arcpy.AddMessage("Number of Buffers: " + str(len(bufferLst)))
        outFC = outPoly

#error handle:
        #check projections, make LULC = sitePnts
        #check that points are within the landuse area
        #check that buffers around points are within the landuse area
#create layer
        #arcpy.MakeFeatureLayer_management(inFC, outLayer)
#task
        #sort list to be sure the outermost buffer output is retained for join
    #if units for buffers aren't all the same this sort won't work and LULC types may be lost
        bufferLst.sort(reverse=True)
        i=0
    #buffer1
        for bufer in bufferLst:
            i+=1
            arcpy.AddMessage("Creating buffer of " + bufer)
        #divide out distance and units from bufer
            tranTbl = dict.fromkeys(map(ord, '0123456789'), None)
            bufferUnits = bufer.translate(tranTbl)
            tranTbl2 = dict.fromkeys(map(ord, bufferUnits), None)
            buffer1Distance = bufer.translate(tranTbl2)
            #arcpy.AddMessage('Distance: ' + buffer1Distance)
            #arcpy.AddMessage('Units: ' + bufferUnits[1:])
        #set variables    
            imtm_poly = outPoly[:-4] + "_" + buffer1Distance + ".shp"
    #buffer
            arcpy.Buffer_analysis(sitePnts, imtm_poly, bufer)

            actualBufer = unique_values(imtm_poly, "BUFF_DIST")
            if actualBufer == [bufer]:
                actualBufer  = bufer
            elif len(actualBufer) != 1:
                arcpy.AddMessage("Shit ERRROR, how did you even do that?!?!")
            else:
                actualBufer = actualBufer[0]
            #arcpy.AddMessage(str(actualBufer))
            
    #intersect
            in_features = [imtm_poly, inPoly]
            outFile = imtm_poly[:-4] + "_inter.shp"
            arcpy.Intersect_analysis(in_features, outFile)
            #calculate area of each landuse
            arcpy.AddField_management(outFile, "PercentBuf", "Double")            
            with arcpy.da.UpdateCursor(outFile, ["PercentBuf", "SHAPE@AREA"]) as cursor:
            #FC@AREA
                for row in cursor:
                    if (row[0] == 0 and row[1] != 0):
                        row[0] = (row[1]/((float(actualBufer))**2.0*math.pi))*100
                    cursor.updateRow(row)
        #Join intersect files together
        #add eliminate/dissolve to ensure it combines within each buffer
            outFile2 =outFile[:-4] + "_2.shp"
            outLyr = outFile[:-4]
            arcpy.MakeFeatureLayer_management(outFile, outLyr)
            arcpy.Dissolve_management(outLyr, outFile2, uniqueID, "PercentBuf SUM","","")
            #arcpy.Delete_management(imtm_poly)
            arcpy.Delete_management(outFile)
    #nest update cursor in search cursor
            bufField = "Pct_buf" + str(buffer1Distance)
            if i == 1:
                #arcpy.AlterField_management(outFile2, "SUM_Percen", "Pct_buf1", bufField)
                arcpy.AddField_management(outFile2, "Pct_buf1", "Double", "", "", "", bufField, "NULLABLE", "", "")
                with arcpy.da.UpdateCursor(outFile2, ["SUM_Percen", "Pct_buf1"]) as cursor:
                    for row in cursor:
                        row[1] = row[0]
                        cursor.updateRow(row)
                arcpy.DeleteField_management(outFile2, "SUM_Percen")
                arcpy.AddMessage("Created results output from largest buffer: " + bufer + ", as 'Pct_buf1' field")
            #join to site and landuse tables
            #save as results file
                arcpy.CopyFeatures_management(outFile2, outFC)
            elif i > 1:
#error handel for when bufField[:10] already exists? otherwise it is replaced
                fieldName = "Pct_buf" + str(i)
                arcpy.AddField_management(outFC, fieldName, "Double", "", "", "", bufField, "NULLABLE", "", "")
                with arcpy.da.SearchCursor(outFile2, ["ORIG_FID", "LCLU", "SUM_Percen"]) as cursor:
                    for row in cursor:
                        siteID = row[0]
                        landID = row[1]
                        bufferPercent = row[2]
                        with arcpy.da.UpdateCursor(outFC, ["ORIG_FID", "LCLU", fieldName]) as cursor:
                            for row in cursor:
                                if siteID == row[0] and landID == row[1]:
                                    row[2] = bufferPercent
                                cursor.updateRow(row)
                arcpy.AddMessage("Added results for buffer of " + bufer + ", to output file as '" + fieldName + "' field")
            arcpy.Delete_management(outFile2)
        #join outFC (sites) to new tables
        arcpy.JoinField_management(outFC, "ORIG_FID", sitePnts, "FID")
        arcpy.JoinField_management(outFC, "LCLU", inPoly, "LCLU")
        return
#####################################
###########Report Generator##########
class Report_Generator_Tool (object):
    def __init__(self):
        self.label = "Tier 1 Report Generator" 
        self.description = "Once the Tier 1 Indicators assessment is complete " + \
                           "this tool will compile results into a report"

    def getParameterInfo(self):
    #Define IN/OUT parameters
        outTbl = setParam("Results", "outTable", "DEFeatureClass", "","")
        #could code this as updated wetland shp instead
        watershed = setParam("Watershed", "watershed", "", "", "")
        ReportTable = setParam("Include Summary Table in Report", "Table", "GPBoolean", "Optional", "")
        #Pdf Save
        ReportPages = setParam("Include Site Pages in Report", "Pages", "GPBoolean", "Optional", "")
        #mxd template (with .rlf)
        reportTemplate = setParam("Report Template (downloaded with tool)", "template", "DEMapDocument","","")
        #outputs-pdf name
        pdfName = setParam("PDF filename and location", "outPDF", "GPDataFile", "", "")
        #could code this as a folder or updated wetland shp instead, info table?
        #could be made optional with an over write default
        params = [outTbl,watershed, ReportTable, ReportPages, reportTemplate, pdfName]
        return params

    def isLicensed(self):
        return True
    def updateParameters(self, params):
        return
    def updateMessages(self, params):
        return
    
    def execute(self, params, messages):
        start = time.clock() #start the clock
        #define variables from user inputs
