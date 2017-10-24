"""
# Name: Rapid Benefit Indicator Assessment - Benefit Reliability
# Purpose: Calculate reliabilty of site benefit product into the future
# Author: Justin Bousquin
# bousquin.justin@epa.gov
#
# Version Notes:
# Developed in ArcGIS 10.3
#0.1.0 converted from .pyt
"""
###########IMPORTS###########
import os
import time
import arcpy
from decimal import Decimal

arcpy.env.parallelProcessingFactor = "100%" #use all available resources
arcpy.env.overwriteOutput = True #overwrite existing files

########USER PARAMETERS########
conserved = ""#conservation Feature dataset
rel_field = ""#field in feature dataset e.g. "Landuse"
cons_fieldLst = ""#list of values from field to consider conservation e.g. ["Conserved", "Protected"]
threat_fieldLst = ""#DETERMINE FROM cons_fieldLst?
rel_buff_dist = ""#Buffer Distance e.g. "1 Miles"
outTbl = ""#output file
###############################
###########FUNCTIONS###########
def message(string, severity = 0):
    """Generic message
    Purpose: prints string message in py or pyt.
    """
    print(string)
    if severity == 1:
        arcpy.AddWarning(string)
    else:
        arcpy.AddMessage(string)


def exec_time(start, task):
    """Global Timer
    Purpose: Returns the time since the last function assignment,
             and a task message.
    Notes: used during testing to compare efficiency of each step
    """
    end = time.clock()
    comp_time = time.strftime("%H:%M:%S", time.gmtime(end-start))
    message("Run time for " + task + ": " + str(comp_time))
    start = time.clock()
    return start


def dec(x):
    """decimal.Decimal"""
    return Decimal(x)


def get_ext(FC):
    """get extension"""
    ext = arcpy.Describe(FC).extension
    if len(ext) > 0:
        ext = "." + ext
    return ext


def del_exists(item):
    """ Delete if exists
    Purpose: if a file exists it is deleted and noted in a message.
    """
    if arcpy.Exists(item):
        try:
            arcpy.Delete_management(item)
            message("'{}' already exists and will be replaced.".format(item))
        except:
            message("'{}' exists but could not be deleted.".format(item))


def field_exists(table, field):
    """Check if field exists in table
    Notes: return true/false
    """
    fieldList = [f.name for f in arcpy.ListFields(table)]
    return True if field in fieldList else False


def find_ID(table):
    """return an ID field where orig_ID > ORIG_FID > OID@
    """
    if field_exists(table, "orig_ID"):
        return "orig_ID"
    elif field_exists(table, "ORIG_FID"):
        return "ORIG_FID"
    else:
        return arcpy.Describe(table).OIDFieldName 


def checkSpatialReference(match_dataset, in_dataset, output=None):
    """Check Spatial Reference
    Purpose: Checks that in_dataset spatial reference name matches
             match_dataset and re-projects if not.
    Inputs: \n match_dataset(Feature Class/Feature Layer/Feature Dataset):
            The dataset with the spatial reference that will be matched.
            in_dataset (Feature Class/Feature Layer/Feature Dataset):
            The dataset that will be projected if it does not match.
    output: \n Path, filename and extension for projected in_dataset
            Defaults to match_dataset location.
    Return: \n Either the original FC or the projected 'output' is returned.
    """
    matchSR = arcpy.Describe(match_dataset).spatialReference
    otherSR = arcpy.Describe(in_dataset).spatialReference
    if matchSR.name != otherSR.name:
        message("'{}' Spatial reference does not match.".format(in_dataset))
        try:
            if output is None:
                # Output defaults to match_dataset location
                path = os.path.dirname(match_dataset) + os.sep
                ext = get_ext(match_dataset)
                out_name = os.path.splitext(os.path.basename(in_dataset))[0]
                output = path + out_name + "_prj" + ext
            del_exists(output)  # delete if output exists
            # Project (doesn't work on Raster)
            arcpy.Project_management(in_dataset, output, matchSR)
            message("File was re-projected and saved as:\n" + output)
            return output
        except:
            message("Warning: spatial reference could not be updated.", 1)
            return in_dataset
    else:
        return in_dataset


def selectStr_by_list(field, lst):
    """Selection Query String from list
    Purpose: return a string for a where clause from a list of field values
    """
    exp = ''
    for item in lst:
        if type(item) in [str, unicode]:  # sequence
            exp += "{} = '{}' OR ".format(field, item)
        elif type(item) == float:
            decP = len(repr(item).split(".")[1])  # decimal places
            if decP >= 15:
                exp += 'ROUND({},{}) = {} OR '.format(field, decP, repr(item))
            else:
                exp += '{} = {} OR '.format(field, repr(item))
        elif type(item) in [int, long]:  # numeric
            exp += '"{}" = {} OR '.format(field, item)
        else:
            message("'{}' in list, unknown type '{}'".format(item, type(item)))
    return (exp[:-4])


def simple_buffer(outTbl, tempName, bufferDist):
    """ Create buffer using tempName"""
    path = os.path.dirname(outTbl) + os.sep
    buf = path + tempName + get_ext(outTbl) # Set temp file name
    del_exists(buf)
    arcpy.Buffer_analysis(outTbl, buf, bufferDist)
    return buf


def percent_cover(poly, bufPoly, units="SQUAREMETERS"):
    """Percent Cover
    Purpose:"""
    arcpy.MakeFeatureLayer_management(poly, "polyLyr")
    lst = []
    orderLst = []
    # ADD handle for when no overlap?
    # Check for "orig_ID" then "ORIG_FID" then use OID@
    field = find_ID(bufPoly)
    with arcpy.da.SearchCursor(bufPoly, ["SHAPE@", field]) as cursor:
        for row in cursor:
            totalArea = dec(row[0].getArea("PLANAR", units))
            match = "INTERSECT"  # default
            arcpy.SelectLayerByLocation_management("polyLyr", match, row[0])
            lyrLst = []
            with arcpy.da.SearchCursor("polyLyr", ["SHAPE@"]) as cursor2:
                for row2 in cursor2:
                    p = 4  # dimension = polygon
                    interPoly = row2[0].intersect(row[0], p)
                    interArea = dec(interPoly.getArea("PLANAR", units))
                    lyrLst.append((interArea/totalArea)*100)
            lst.append(sum(lyrLst))
            orderLst.append(row[1])
    arcpy.Delete_management("polyLyr")
    # Sort by ID field
    orderLst, lst = (list(x) for x in zip(*sorted(zip(orderLst, lst))))
    return lst


def lst_to_AddField_lst(table, field_lst, list_lst, type_lst):
    """Lists to ADD Field
    Purpose:
    Notes: Table, list of new fields, list of listes of field values,
           list of field datatypes.
    """
    if len(field_lst) != len(list_lst) or len(field_lst) != len(type_lst):
        message("ERROR: lists aren't the same length!")
    #  "" defaults to "DOUBLE"
    type_lst = ["Double" if x == "" else x for x in type_lst]

    for i, field in enumerate(field_lst):
        # Add fields
        arcpy.AddField_management(table, field, type_lst[i])
        # Add values
        lst_to_field(table, field, list_lst[i])


def lst_to_field(table, field, lst):
    """Add List to Field
    Purpose:
    Notes: 1 field at a time
    Example: lst_to_field(featureClass, "fieldName", lst)
    """
    if len(lst) == 0:
        message("No values to add to '{}'.".format(field))
    elif field_exists(table, field):   
        with arcpy.da.UpdateCursor(table, [field]) as cursor:
            # For row in cursor:
            for i, row in enumerate(cursor):
                    row[0] = lst[i]
                    cursor.updateRow(row)
    else:
        message("{} field not found in {}".format(field, table))
                
#########RELIABILITY##########
def reliability_MODULE(PARAMS):
    """Reliability of Benefits"""
    # start = time.clock() #start the clock
    mod_str = "Reliability of Benefits analysis"
    message(mod_str + "...")

    cons_poly = PARAMS[0]
    field = PARAMS[1]
    consLst, threatLst = PARAMS[2], PARAMS[3]
    bufferDist = PARAMS[4]
    outTbl = PARAMS[5]

    message("Checking input variables...")
    # Remove None/0 from lists
    if consLst is not None:
        consLst = [x for x in consLst if x is not None]
        threatLst = [x for x in threatLst if x is not None]
        cons_poly = checkSpatialReference(outTbl, cons_poly)
        message("Input variables OK")
    else:
        message("Reliability inputs failed: no Conservation Field Values selected")

    # Buffer site by user specified distance
    buf = simple_buffer(outTbl, "conservation", bufferDist)

    # Make selection from FC based on fields to include
    sel = "NEW_SELECTION"
    arcpy.MakeFeatureLayer_management(cons_poly, "lyr")
    whereClause = selectStr_by_list(field, consLst)
    arcpy.SelectLayerByAttribute_management("lyr", sel, whereClause)
    # Determine percent of buffer which is each conservation type
    pct_consLst = percent_cover("lyr", buf)
    try:
        # Make list based on threat use types
        whereThreat = selectStr_by_list(field, threatLst)
        arcpy.SelectLayerByAttribute_management("lyr", sel, whereThreat)
        pct_threatLst = percent_cover("lyr", buf)
    except Exception:
        message("Error occured determining percent non-conserved areas.", 1)
        traceback.print_exc()
        pass

    # Final Step - move results to results file
    message("Saving {} results to 'Conserved' in Output...".format(mod_str))
    fields_lst = ["Conserved", "Threatene"]
    list_lst = [pct_consLst, pct_threatLst]

    lst_to_AddField_lst(outTbl, fields_lst, list_lst, ["", ""])

    arcpy.Delete_management(buf)
    arcpy.Delete_management("lyr")
    message(mod_str + " complete")

##############################
###########EXECUTE############
try:
    start = time.clock()
    reliability_MODULE([conserved, rel_field, cons_fieldLst,
                        threat_fieldLst, rel_buff_dist, outTbl])
    start = exec_time(start, "Reliability assessment")
except Exception:
    message("Error occured during Reliability assessment.", 1)
    traceback.print_exc()
