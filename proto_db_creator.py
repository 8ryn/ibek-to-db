#Protype/experminetal creator of 8001 db files. Ignores the paring side of things and just tests the creation of the db files.

# Try to create the db file corresponding to br with only card 4
import epicsdbbuilder

from DLSRecordName import SetDLSRecordNames, SetDomain
import components.fanMonitor as fanMonitor
import components.timing as timing
import components.pin as pin

from builder.ipac import Hy8001, Hy8002, DIRECTION_INPUT
from builder.DLS8512 import DLS8512
from builder.DLS8515 import DLS8516

cell = 2
Location = 'BR%02dC' % cell


epicsdbbuilder.InitialiseDbd('/dls_sw/epics/R3.14.12.3/base/')
SetDLSRecordNames()

# Card 4: PIN radiation detectors
# ======
card4 = Hy8001(4,DIRECTION_INPUT, invertin=1, ip_support=True)
pin_scaler = DLS8512(card4, 0)  #Note this is now explicit

pin_counters = [pin_scaler.channel(i) for i in range(16)]

fan_monitor = card4.register(32, 16)    # Port C


# Card 5: Crate fan temperature monitor.
# ======
#card5 = Hy8002(5)    # Sheet 4
#cmsIonSerialCard = DLS8516(card5, 0)  # CMS ION monitor channels in IP slot A

SetDomain(Location, 'DI')

fanMonitor.FanMonitor(1, fan_monitor.register(0,4))
er = timing.BoosterEvents(cell)
pins = pin.PINs(pin_counters)

# Each cell 2, 4 manages radiation monitors for the cell itself and the
# preceding cell.
#cmsIon.createCmsIon(er, cmsIonSerialCard, Location, 1, 1)
#cmsIon.createCmsIon(er, cmsIonSerialCard, Location, 2, 2)

epicsdbbuilder.WriteRecords('test.db')
