# Helper functions for adding autosave comments and parder to create .req files

from epicsdbbuilder.recordbase import Record
from contextlib import ExitStack

def add_autosave(record: Record, field = 'VAL', pass_num = 0):
    """Add autosave metadata to a record."""
    record.add_metadata(f'autosave {pass_num} {field}')

def db_to_req(db_file_name: str, passes = [0,1,2], ioc_name: str|None = None):
    if ioc_name is None:
        ioc_name = db_file_name.split('.')[0]
    req_file_names = {pass_num:f"{ioc_name}_{pass_num}.req" for pass_num in passes}
    with ExitStack() as stack: #Allows automatic closing of files when done
        req_files = {pass_num: stack.enter_context(open(name, 'w')) for pass_num, name in req_file_names.items()}
        db_file = stack.enter_context(open(db_file_name, 'r'))
        for line in db_file:
            if line.startswith('#% autosave'):
                split_line = line.split()
                pass_num = int(split_line[2])
                field = split_line[3]
                if pass_num in passes:
                    record_line = next(db_file) #Get the next line which should be the record definition
                    record_name = record_line.split(",")[1].strip(" \")\n")
                    print("Record name: ", record_name)
                    req_files[pass_num].write(f"{record_name}.{field}\n")
                else:
                    print(f"Warning: Found autosave for pass {pass_num} which is not in passes {passes}. Ignoring.")


# To test
db_to_req('linac.db')
