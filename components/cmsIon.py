# Simple CMS ION generator

from builder.modules.asyn import asyn
from builder.modules.cmsIon import cmsIon, cmsIon_CheckReset


def createCmsIon(er, serialCard, domain, id, socket, high=1.3, hihi=1.6):
    '''Helper routine for creating cmsIon instances.  The  arguments are:
        domain is the machine location (LI/BRnnC/SRnnC/etc),
        id is the sequence number (normally 1),
        socket is the connector number on the PIM used to connect to the
            serial device (with the first socket numbered 1).'''
    port = serialCard.channel(socket - 1, fullduplex=True)
    port = asyn.AsynSerial(port.DeviceName())
    radmon = '%s-RS-RDMON-%02d' % (domain, id)
    cmsIon_CheckReset(device = radmon, evr = er.GetDevice())
    return cmsIon(
        device = radmon, port = port, high = high, hihi = hihi)
