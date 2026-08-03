#Protype/experminetal creator of 8001 db files. Ignores the paring side of things and just tests the creation of the db files.

# Try to create the db file corresponding to br with only card 4
import epicsdbbuilder

from builder.DLSRecordName import SetDLSRecordNames, SetDomain
from builder.modules.ipac import DIRECTION_INPUT
from builder.template import Substitution
import components.fanMonitor as fanMonitor
import components.timing as timing
import components.pin as pin
import components.stats as stats
import components.cmsIon as cmsIon

from builder.modules.ipac import Hy8001, Hy8002
from builder.modules.DLS8512 import DLS8512
from builder.modules.DLS8515 import DLS8516
from builder.modules.autosave import autosave_add_templates
from builder.modules.IOCinfo import IOCinfo

cell = 2  #Hard coded for now, can be 2 or 4
Location = 'BR%02dC' % cell

# ---------------------------------------------------------------------------
#     IOC hardware resources
# ---------------------------------------------------------------------------

# See drawings number 1007177 and 1007019, issue A for the underlying
# hardware associated with these definitions.

'''Booster Ring %(cell)d (%(Location)s) Hardware Layout

VME   IP
Slot  Slot  Description          Transition    Interface
  3         Event Receiver
  4         8001 Digital I/O & IP     8301
      A      8512 Scaler                       PIN crate
      C                                        8901-CC (PIM1)
  5         8002 IP carrier           8304
      A      8516  RS-485 controller           8904 (PIM2)

Hardware connections:
  4.A   <- PIN diode radiation detector
  4.C   <- Fan status control
  5.A   <- Radiation safety readback
'''


epicsdbbuilder.InitialiseDbd('/dls_sw/epics/R3.14.12.3/base/')
SetDLSRecordNames()

ioc_name = Location + '-DI-IOC-01'

autosave_add_templates(ioc_name)

IOCinfo(device = ioc_name)

stats.status(ioc_name)

# Card 4: PIN radiation detectors
# ======
card4 = Hy8001(4,DIRECTION_INPUT, invertin=1, ip_support=True)
pin_scaler = DLS8512(card4, 0)  #Note this is now explicit

pin_counters = [pin_scaler.channel(i) for i in range(16)]

fan_monitor = card4.register(32, 16)    # Port C


# Card 5: Crate fan temperature monitor.
# ======

card5 = Hy8002(5)    # Sheet 4
cmsIonSerialCard = DLS8516(card5, 0)  # CMS ION monitor channels in IP slot A

SetDomain(Location, 'DI')

fanMonitor.FanMonitor(1, fan_monitor.register(0,4))
er = timing.BoosterEvents(cell)
pins = pin.PINs(pin_counters)

# Each cell 2, 4 manages radiation monitors for the cell itself and the
# preceding cell.
cmsIon.createCmsIon(er, cmsIonSerialCard, Location, 1, 1)
cmsIon.createCmsIon(er, cmsIonSerialCard, Location, 2, 2)

epicsdbbuilder.WriteRecords(f'br{cell:02d}.db')
print(f"Wrote br{cell:02d}.db")

Substitution.write_all_substitutions(f'br{cell:02d}_expanded.substitutions')
print(f"Wrote br{cell:02d}_expanded.substitutions")
