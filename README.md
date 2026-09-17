# ibek-to-db

A new version of the diagnostics IOC builder, built on the assumption that IBEK will handle everything other than the IOC `.db` files and the autosave files.

## Overview

The `builder` directory contains code building on `epicsdbbuilder` to replicate some `iocbuilder` functionality, along with code specific to individual EPICS modules. This module code was previously in the builder directories/files in Diamond versions of EPICS modules. It is likely we will separate the `builder` directory into its own module in the future.

Python scripts have been defined to recreate both the linac and BR IOCs. These scripts create identical `.db` files to those previously created, with the exception of the vxWorks IOC stats template records — this likely needs replacing with an RTEMS version that does not currently exist. The scripts also run a parser to create autosave `.req` files from comments in the `.db` files.

The idea is that this script will be part of a generic IOC that takes a Python script (such as `linac.py`) and creates the required `.db` files at startup. There is also the option of running it to produce the `.db` files and then simply using them in the IOC. An example for the BR where we require adding in the `.db` files to load can be seen [here](https://gitlab.diamond.ac.uk/controls/containers/accelerator/di-services/-/tree/auto-convert-01/services/br02c-di-ioc-01).

The practicalities of how this would actually run are still a little up in the air.

## Known Issues

- **Hard-coded paths**: There is currently some code smell with paths hard-coded for the support modules. If this is being run within the IOC container that may be sensible, since the support modules would consistently be in the same place. However, if not, this should be made configurable.
- **Runtime environment**: A lot of clarification is needed on how/where this script would be run. The Python naturally won't be run within RTEMS, so it seems it's not an RTEMS container we need.
- The original idea of this was that we could parse the ibek yaml to produce the python script. There is by default information missing from the ibek yaml that would be needed so for now have left the configuration in two places.
