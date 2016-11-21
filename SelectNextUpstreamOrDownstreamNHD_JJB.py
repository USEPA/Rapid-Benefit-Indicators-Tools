"""
# Tool Name:  Find Next Upstream or Downstream NHD
# Author: Marc Weber and Tad Larsen
# Date: October 3, 2014
# Select upstream or downstream feature from a
# selected NHDPlus feature (stream line or catchment)
"""
# Import system modules
import os, arcpy, sys
import struct, decimal, itertools
from collections import deque, defaultdict

def dbfreader(f):
    """Returns an iterator over records in a Xbase DBF file.

    The first row returned contains the field names.
    The second row contains field specs: (type, size, decimal places).
    Subsequent rows contain the data records.
    If a record is marked as deleted, it is skipped.

    File should be opened for binary reads.

    """
    # See DBF format spec at:
    #     http://www.pgts.com.au/download/public/xbase.htm#DBF_STRUCT

    numrec, lenheader = struct.unpack('<xxxxLH22x', f.read(32))    
    numfields = (lenheader - 33) // 32

    fields = []
    for fieldno in xrange(numfields):
        name, typ, size, deci = struct.unpack('<11sc4xBB14x', f.read(32))
        name = name.replace('\0', '')       # eliminate NULLs from string   
        fields.append((name, typ, size, deci))
    yield [field[0] for field in fields]
    yield [tuple(field[1:]) for field in fields]

    terminator = f.read(1)
    assert terminator == '\r'

    fields.insert(0, ('DeletionFlag', 'C', 1, 0))
    fmt = ''.join(['%ds' % fieldinfo[2] for fieldinfo in fields])
    fmtsiz = struct.calcsize(fmt)
    for i in xrange(numrec):
        record = struct.unpack(fmt, f.read(fmtsiz))
        if record[0] != ' ':
            continue                        # deleted record
        result = []
        for (name, typ, size, deci), value in itertools.izip(fields, record):
            if name == 'DeletionFlag':
                continue
            if typ == "N":
                value = value.replace('\0', '').lstrip()
                if value == '':
                    value = 0
                elif deci:
                    value = decimal.Decimal(value)
                else:
                    value = int(value)
            elif typ == 'D':
                y, m, d = int(value[:4]), int(value[4:6]), int(value[6:8])
                value = datetime.date(y, m, d)
            elif typ == 'L':
                value = (value in 'YyTt' and 'T') or (value in 'NnFf' and 'F') or '?'
            result.append(value)
        yield result
        
# Main Function
if __name__ == "__main__":
    InputFC = sys.argv[1] # NHDPlus feature
    InputField = sys.argv[2] # Field with COMID or FEATUREID
    Path = arcpy.Describe(InputFC).Path
    UpDown = sys.argv[3]
    if (InputFC == "Catchment"):
        Flow = Path.replace('NHDPlusCatchment','NHDPlusAttributes')+'\PlusFlow.dbf' #replace(*old*, *new*) 
    else:
        Flow = Path.replace('NHDSnapshot\\Hydrography','NHDPlusAttributes')+'\PlusFlow.dbf'
    arcpy.env.workspace = Path
    try:
        UpCOMs = defaultdict(list)
        DownCOMs = defaultdict(list)
        FeatureclassName = arcpy.Describe(InputFC).Name
        arcpy.AddMessage("Gathering info on upstream / downstream relationships")
        infile = open(Flow, 'rb')
        arcpy.AddMessage("Making list from dbf file.")
        data = list(dbfreader(infile))
        infile.close()
        for line in data[2:]:
            FROMCOMID=line[0]
            TOCOMID=line[3]
            UpCOMs[TOCOMID].append(FROMCOMID)
            DownCOMs[FROMCOMID].append(TOCOMID)
        for k in UpCOMs.iterkeys():
            for items in UpCOMs[k]:
                if items == 0:
                    UpCOMs[k] = []
        for k in DownCOMs.iterkeys():
            for items in DownCOMs[k]:
                if items == 0:
                    DownCOMs[k] = []

        rows = arcpy.SearchCursor(InputFC)
        for row in rows:
            COMID = (row.getValue("%s"%(InputField)))
            
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
                
        arcpy.AddMessage(" ")
    except:
      arcpy.GetMessages()



