"""
# Name: Rapid Benefit Indicator Assessment - Presence/Absence to Yes/No
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

arcpy.env.parallelProcessingFactor = "100%" #use all available resources
arcpy.env.overwriteOutput = True #overwrite existing files

########USER PARAMETERS########
#existing results outTable
outTbl = ""
#field in outTable to overwrite
field = ""
#dataset to test presence/absence against
FC = ""
#distance within which feature matters
buff_dist = ""

##########FUNCTIONS##########
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


def simple_buffer(outTbl, tempName, bufferDist):
    """ Create buffer using tempName"""
    path = os.path.dirname(outTbl) + os.sep
    buf = path + tempName + get_ext(outTbl) # Set temp file name
    del_exists(buf)
    arcpy.Buffer_analysis(outTbl, buf, bufferDist)
    return buf


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


def quant_to_qual_lst(lst):
    """Quantitative List to Qualitative List
    Purpose: convert counts of >0 to YES"""
    qual_lst = []
    for i in lst:
        if (i == 0):
            qual_lst.append("NO")
        else:
            qual_lst.append("YES")
    return qual_lst
#############################
def absTest_MODULE(PARAMS):
    """Presence Absence Test"""

    outTbl, field = PARAMS[0], PARAMS[1]
    FC = PARAMS[2]
    buff_dist = PARAMS[3]

    # Check spatial ref
    FC = checkSpatialReference(outTbl, FC)

    # Create buffers for each site by buff_dist.
    buf = simple_buffer(outTbl, "feature_buffer", buff_dist)

    # If feature not present "NO", else "YES"
    booleanLst = quant_to_qual_lst(buffer_contains(buf, FC))

    # Move results to outTbl.field
    lst_to_AddField_lst(outTbl, [field], [booleanLst], ["Text"])
    arcpy.Delete_management(buf)
    
###########EXECUTE###########
try:
    start = time.clock() #start the clock
    absTest_MODULE([outTbl, field, FC, buff_dist])
    start = exec_time(start, "Presence/Absence assessment")
except Exception:
    message("Error occured during assessment.", 1)
    traceback.print_exc()
