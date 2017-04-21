import arcpy
import urllib
import os


def get_ext(FC):
    """get extension"""
    ext = arcpy.Describe(FC).extension
    if len(ext)>0:
        ext = "." + ext
    return ext


def checkSpatialReference(alphaFC, otherFC):
    """Check Spatial Reference
    Purpose: Checks that a second spatial reference matches the first and
             re-projects if not.
    Function Notes: Either the original FC or the re-projected one is returned
    """
    alphaSR = arcpy.Describe(alphaFC).spatialReference
    otherSR = arcpy.Describe(otherFC).spatialReference
    if alphaSR.name != otherSR.name:
        #e.g. .name = u'WGS_1984_UTM_Zone_19N' for WGS_1984_UTM_Zone_19N
        message("Spatial reference for " + otherFC + " does not match.")
        try:
            path = os.path.dirname(alphaFC)
            ext = get_ext(alphaFC)
            newName = os.path.basename(otherFC)
            output = path + os.sep + os.path.splitext(newName)[0] + "_prj" + ext
            arcpy.Project_management(otherFC, output, alphaSR)
            fc = output
            message("File was re-projected and saved as " + fc)
        except:
            message("Warning: spatial reference could not be updated.")
            fc = otherFC
    else:
        fc = otherFC
    return fc


def field_to_lst(table, field):
    """Read Field to List
    Purpose:
    Notes: if field is: string, 1 field at a time;
                        list, 1 field at a time or 1st field is used to sort
    Example: lst = field_to_lst("table.shp", "fieldName")
    """
    lst = []
    #check that field exists in table
    if field_exists(table, field) == True:
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
            message("Something went wrong with the field to list function")
    else:
        message(str(field) + " could not be found in " + str(table))
        message("Empty values will be returned.")
    return lst


sites = r"\\AA.AD.EPA.GOV\ORD\NAR\USERS\EC1\jbousqui\Net MyDocuments\ArcGIS\Default.gdb\test_Sites_Buffer"
NHD_VUB = r"L:\Public\jbousqui\GED\GIS\NHD_Plus\NHDPlusV21_NHDPlusGlobalData_02\BoundaryUnit.shp"
local = r"C:\Users\jbousqui\Desktop"

NHD_ftp = "ftp://www.horizon-systems.com/{0}/{0}V21/Data/{0}".format("NHDPlus")
distance = "5 Miles"

# Check projection.
sites = checkSpatialReference(NHD_VUB, sites)

# Make layer.
arcpy.MakeFeatureLayer_management(NHD_VUB, "VUB")

# Select NHDPlus vector unit boundaries
overlap = "WITHIN_A_DISTANCE"
arcpy.SelectLayerByLocation_management("VUB", overlap, sites, distance, "", "")

# Gather info from fields to construct request
ID_list = field_to_lst("VUB", "UnitID")
drain_list = field_to_list("VUB", "DrainageID")

for i, ID in enumerate(drain_list):
    f = "NHDPlusV21_" + ID + "_" + ID_list[i] + "_NHDPlusCatchment_01.7z"
    request = NHD_ftp + ID + "/" + f
    local_f = local + os.sep + f
    urllib.urlretrieve(request, local_f)





#########NOTES########
import ftplib

host = 'ftp.horizon-systems.com'
ftp = ftplib.FTP('ftp.horizon-systems.com')

sub_dir = "/NHDPlus/NHDPlusV21/Data/NationalData/"

#files
PR = "NHDPlusV21_NationalData_National_HI_PR_VI_PI_Seamless_Geodatabase_03.7z"
CONUS = "NHDPlusV21_NationalData_CONUS_Seamless_Geodatabase_04.7z"
Cat = "NHDPlusV21_NationalData_NationalCat_02.7z"

>>> import arcpy
>>> import urllib
>>> f = r"C:\Users\jbousqui\Desktop\NHD"
>>> link = "ftp://www.horizon-systems.com/NHDPlus/NHDPlusV21/Data/NationalData/NHDPlusV21_NationalData_CONUS_Seamless_Geodatabase_04.7z"
>>> urllib.urlretrieve(link, f)


###WATERS SERVER###
service_url = 'https://ofmpub.epa.gov/waters10/'
