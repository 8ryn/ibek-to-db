#Code lifted directly from iocbuilder

## This class encapsulates the construction of records from hardware.
# Typically the hardware specific part consists simply of the DTYP
# specification and an address field, which may be computed using extra
# arguments and fields passed to the constructor.
class RecordFactory:

    ## Each record factory is passed a record constructor (factory), a link to
    # the associated Device instance (device), the name of the EPICS device
    # link (typically 'INP' or 'OUT'), an address string or address
    # constructor, and a option addressing fixup routine (post).
    #
    # \param factory
    #   Record constructor to be used.
    # \param device
    #   Associated DTYP setting
    # \param link
    #   Associated address link to go into INP or OUT field.
    # \param address
    #   Field name to receive address link
    # \param post
    #   Optional hook for post processing of fields.
    def __init__(self, factory, device, link, address, post=None):
        self.factory = factory
        self.device = device
        self.link = link
        self.address = address
        self.post = post

    # Calling a record factory instance builds a record with the given name
    # and fields bound to the originating hardware.
    def __call__(self, name, *address_extra, **fields):
        # If the address is callable then we compute the address using the
        # address hook, simultaneously fixing up any fields that only belong
        # to the address computation.  Otherwise we hope it's a static string
        # (or at least knows how to render itself) and use it as is.
        if callable(self.address):
            address = self.address(fields, *address_extra)
        else:
            assert address_extra == (), 'Unused address arguments'
            address = self.address
        # Build the appropriate type of record
        record = self.factory(name, **fields)

        # Bind the hardware to the device
        record.DTYP = self.device
        setattr(record, self.link, address)

        # Finally allow any special purpose fixup work to be done.
        if self.post:
            self.post(record)
        return record
