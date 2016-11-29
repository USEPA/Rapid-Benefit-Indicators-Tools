"""Intersect Boolean
Purpose: returns T/F if two layers intersect at all
"""
def intersect_boolean(lyr1, lyr2):
    #with arcpy.da.SearchCursor(lyr1, ["SHAPE@"]) as cursor1:
    #    for row1 in cursor1:
    #        with arcpy.da.SearchCursor(lyr2, ["SHAPE@"]) as cursor2:
    #            for row2 in cursor2:
    #                intersectPoly = row2[0].intersect(row1[0], 4)
    arcpy.SelectLayerByLocation_management(lyr1, 'intersect', lyr2)
    cnt = int(arcpy.GetCount_management(lyr1)[0])
    if cnt == 0:
        return False
    else:
        return True