from builder.device import Device

# These devices are used directly, while the others are loaded as part of
# other devices
__all__ = ['Asyn', 'AsynSerial', 'AsynIP']


class Asyn(Device):
    DbdDir = 'asyn/4-31/'
    DbdFileList = ['asyn']


class AsynPort(Asyn):

    # Set of allocated ports to avoid accidential duplication.
    __Ports = set()

    # Flag used to identify this as an asyn device.
    IsAsyn = True

    def __init__(self, name):
        self.asyn_name = name
        assert name not in self.__Ports, \
            'AsynPort %s already defined' % name
        self.__Ports.add(name)
        super().__init__()

    def DeviceName(self):
        return self.asyn_name

    def __str__(self):
        return self.DeviceName()


class _AsynOctetInterface(AsynPort):

    ValidSetOptionKeys = set([
        'baud', 'bits', 'parity', 'stop', 'crtscts'])

    def __init__(self, port,
            name=None, input_eos=None, output_eos=None,
            priority=100, noAutoConnect=False, noProcessEos=False,
            simulation=None, **options):
        self.port_name = port
        assert set(options.keys()) <= self.ValidSetOptionKeys, \
            'Invalid argument to asynSetOption'
        self.options = options
        self.input_eos = input_eos
        self.output_eos = output_eos
        self.priority = priority
        self.noAutoConnect = int(noAutoConnect)
        self.noProcessEos = int(noProcessEos)
        super().__init__(name)


class AsynSerial(_AsynOctetInterface):
    '''Asyn Serial Port'''

    DbdFileList = ['drvAsynSerialPort']

    # just pass the port name to AsynOctet interface
    def __init__(self, port, name = None, **kwargs):
        if name is None:
            name = port[1:].replace('/', '_')
        super().__init__(port, name, **kwargs)

class AsynIP(_AsynOctetInterface):
    '''Asyn IP Port'''

    DbdFileList = ['drvAsynIPPort']

    # validate the port then pass it up
    def __init__(self, port, name = None, **kwargs):
        IsIpAddr(port)
        if name is None:
            name = port.replace(".", "_").replace(":","_")
        super().__init__(port, name, **kwargs)

class Vxi11(_AsynOctetInterface):
    '''Asyn vxi11 Port'''

    DbdFileList = ['drvVxi11']

    def __init__(self, port,
            name=None, flags=0, timeout="0.0", vxiName="gpib0", **kwargs):
        IsIpAddr(port)
        if name is None:
            name = port.replace(".", "_").replace(":","_")
        self.flags = flags
        self.timeout = timeout
        self.vxiName = vxiName
        super().__init__(port, name, **kwargs)


def IsIpAddr(val):
    # validator for an ip address
    errStr = "'%s' should be of format x[xx].x[xx].x[xx].x[xx][:x[x..]] [protocol]" % val
    # split into ip and port
    split = val.strip().split(" ")[0].split(":")
    # check we have either just an ip, or an ip and a port
    assert len(split)in [1,2], errStr
    # check the port is in an int if it exists
    if len(split) == 2:
        assert split[1].isdigit(), errStr

def AsynSerial_sim(port, simulation=None, AsynIP=AsynIP, **args):
    if simulation:
        return AsynIP(simulation, **args)

def AsynIP_sim(port, simulation=None, AsynIP=AsynIP, **args):
    if simulation:
        return AsynIP(simulation, **args)


def Vxi11_sim(port, simulation=None, Vxi11=Vxi11, **args):
    if simulation:
        return Vxi11(simulation, **args)
