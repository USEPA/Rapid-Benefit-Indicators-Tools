"""
# Name: Tier 1 Rapid Benefit Indicator Assessment- Flood Module
# Purpose: Calculate values for benefit indicators using wetland restoration site polygons
#          and a variety of other input data
# Author: Justin Bousquin
#
# Version Notes:
# Developed in ArcGIS 10.3
# v26 Tier 1 Rapid Benefit Indicator Assessment
# Date: 10/30/2016
"""
###########FUNCTIONS##########
"""Global Timer
Purpose: returns the message and calc time since the last time the function was used."""
#Function Notes: used during testing to compare efficiency of each step
def exec_time(start, message):
    end = time.clock()
    comp_time = end - start
    arcpy.AddMessage("Run time for " + message + ": " + str(comp_time))
    start = time.clock()
    return start

###########FLOODING##########

start = time.clock() #start the clock

#params = [restorationSites, addresses, popRast, floodZone, existingWetlands, dams, outTbl]
#define variables from user inputs
wetlands = params[0].valueAsText

addresses = params[1].valueAsText

popRast = params[2].valueAsText

flood_zone = params[3].valueAsText

ExistingWetlands = params[4].valueAtText

subs = params[5].valueAsText

outTbl = params[6].valueAsText
#
        
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
