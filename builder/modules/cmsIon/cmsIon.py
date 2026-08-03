from builder.device import Device, autodepends
from builder.template import Substitution


class _cmsIon_Device(Device):
    DbdDir = "cmsIon/4-11"
    DbdFileList = ['cmsIonSupport']

class _cmsIon_Substitution(Substitution):
    TemplateDir = "cmsIon/4-11"

class cmsIon(_cmsIon_Substitution):
    TemplateDir = "cmsIon/4-11"
    TemplateFile  = 'cmsIon.template'

    # TODO: This previously had a dependence on streamDevice and handled copying the relevant protocol file
    # Ensure that is handled correctly by ibek etc. Once certain remove the warning below
    @autodepends(_cmsIon_Device)
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        print("WARNING: cmsIon instantiated. Previous version handled copying of protocol file. Has this been handled elsewhere?")

class cmsIon_CheckReset(_cmsIon_Substitution):
    TemplateFile = 'cmsIon_CheckReset.template'

class RS4hour(_cmsIon_Substitution):
    TemplateFile = 'RS4hour.template'

class RS4hour_IFB300(_cmsIon_Substitution):
    TemplateFile = 'RS4hour-IFB300.template'

# The simulation has a slightly different db file
class cmsIon_sim(cmsIon):
    TemplateFile = 'simulation_cmsIon.template'
