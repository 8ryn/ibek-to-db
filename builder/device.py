import epicsdbbuilder

class Device():

    DbdFileList = []
    _loaded_dbds = set()

    @classmethod
    def load_dbd_list(cls):
        for cls in reversed(cls.__mro__):
            for dbd in cls.__dict__.get('DbdFileList', []):
                cls.load_dbd(dbd)

    @classmethod
    def load_dbd(cls, dbd):
        if dbd not in cls._loaded_dbds:
            print("Loading dbd file: %s" % dbd)
            epicsdbbuilder.LoadDbdFile(dbd)
            cls._loaded_dbds.add(dbd)

    def __init__(self):
        self.load_dbd_list()


def autodepends(*devices):
    def device_wrapper(f):
        def wrapped_function(*args, **kargs):
            for device in devices:
                device.load_dbd_list()
            return f(*args, **kargs)
        wrapped_function.__name__ = f.__name__
        wrapped_function.__doc__  = f.__doc__
        return wrapped_function
    return device_wrapper
