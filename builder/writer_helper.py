import subprocess

import epicsdbbuilder

from builder.template import Substitution

"""
Write the database and substitution files for a given IOC name. Creates the following files:
- {name}.db: The EPICS database file.
- {name}_expanded.substitutions: The expanded substitutions file.
It will also run the 'msi' command to generate the expanded database file:
- {name}_expanded.db: The expanded EPICS database file.
"""
def write_db(name: str):
    epicsdbbuilder.WriteRecords(f"{name}.db")
    print(f"Wrote {name}.db")

    Substitution.write_all_substitutions(f"{name}_expanded.substitutions")
    print(f"Wrote {name}_expanded.substitutions")

    subst_result = subprocess.run(
        ['msi', '-S', f"{name}_expanded.substitutions"],
        stdout=open(f"{name}_expanded.db", 'w'),
        stderr=subprocess.PIPE,
        text=True
    )
    if subst_result.returncode != 0:
        print(f"msi failed: {subst_result.stderr}")
    else:
        print(f"Wrote {name}_expanded.db")
