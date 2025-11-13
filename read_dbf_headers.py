import os
import json
from dbfread import DBF, FieldParser
from collections import OrderedDict

class MyFieldParser(FieldParser):
    def parse(self, field, data):
        try:
            return super().parse(field, data)
        except ValueError:
            return None

def get_dbf_structure(dbf_path):
    try:
        # Use a custom field parser to handle potential parsing errors
        table = DBF(dbf_path, parserclass=MyFieldParser, encoding='iso-8859-1')
        
        # Get the field names and types from the header
        fields = OrderedDict()
        for field in table.fields:
            fields[field.name] = field.type
            
        # Get the first record to see sample data
        first_record = None
        try:
            first_record = next(iter(table))
        except StopIteration:
            # The table is empty
            pass

        return {"fields": fields, "first_record": first_record}
    except Exception as e:
        return {"error": str(e)}

def main():
    dbf_files = [
        "C:\\acocta5\\acocarpo.dbf",
        "C:\\acocta5\\liqven.dbf",
        "C:\\acocta5\\acogran.dbf",
        "C:\\acocta5\\acograst.dbf",
        "C:\\acocta5\\contrat.dbf",
        "C:\\acocta5\\acohis.dbf",
        "C:\\acocta5\\sysmae.dbf",
        "C:\\acocta5\\choferes.dbf",
        "C:\\acocta5\\ccbcta.dbf"
    ]
    
    all_structures = OrderedDict()
    for dbf_path in dbf_files:
        file_name = os.path.basename(dbf_path)
        all_structures[file_name] = get_dbf_structure(dbf_path)
        
    # Print as JSON
    print(json.dumps(all_structures, indent=4, default=str))

if __name__ == "__main__":
    main()
