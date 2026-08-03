#This is vastly simplified in comparison to the original autosave.py.
# The only purpose of this version is to produce the appropriate substitution files.

from builder.template import Substitution


class _AutosaveFile(Substitution):
    Macros = ('device', 'file',)
    TemplateDir = 'autosave/5-9dls3'
    TemplateFile = 'dlssrfile.template'

class _AutosaveStatus(Substitution):
    Macros = ('device', 'name')
    TemplateDir = 'autosave/5-9dls3'
    TemplateFile = 'dlssrstatus.template'

def autosave_add_templates(iocName: str, db_suffix: str = '', name: str|None = None):
    _AutosaveFile(device = iocName + db_suffix, file = '0')
    _AutosaveFile(device = iocName + db_suffix, file = '1')
    _AutosaveFile(device = iocName + db_suffix, file = '2')

    _AutosaveStatus(device = iocName + db_suffix, name = name)
