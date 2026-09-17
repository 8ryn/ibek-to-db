# Helper functions for adding autosave comments and parser to create .req files

from contextlib import ExitStack

from epicsdbbuilder.recordbase import Record


def add_autosave(record: Record, field = 'VAL', pass_num = 0):
    """Add autosave metadata to a record."""
    record.add_metadata(f'autosave {pass_num} {field}')

def db_to_req(db_file_names: str | list[str], passes = [0,1,2], ioc_name: str|None = None):
    if isinstance(db_file_names, str):
        db_file_names = [db_file_names]
    if ioc_name is None:
        ioc_name = db_file_names[0].split('.')[0].split('_')[0]
    req_file_names = {pass_num:f"{ioc_name}_{pass_num}.req" for pass_num in passes}
    with ExitStack() as stack: #Allows automatic closing of files when done
        req_files = {pass_num: stack.enter_context(open(name, 'w')) for pass_num, name in req_file_names.items()}
        for fname in db_file_names:
            db_file = stack.enter_context(open(fname, 'r'))
            for line in db_file:
                if line.startswith('#% autosave'):
                    autosave_list = []
                    while line.startswith('#'):
                        # Allows for multiple comments before record definition without code duplication.
                        if line.startswith('#% autosave'):
                            split_line = line.split()
                            pass_num = int(split_line[2])
                            field = split_line[3]
                            if pass_num in passes:
                                autosave_list.append((pass_num, field))
                            else:
                                print(f"Warning: Found autosave for pass {pass_num} which is not in passes {passes}. Ignoring.")
                        line = next(db_file)
                    if line.startswith('record'):
                        record_name = line.split(",")[1].strip(" \")\n{")
                        for pass_num, field in autosave_list:
                            req_files[pass_num].write(f"{record_name}.{field}\n")
                    else:
                        print("Warning: Expected record definition after autosave comments, but found: ", line)


if __name__ == "__main__":
    # To test
    db_to_req(['linac.db', 'linac_expanded.db'])
