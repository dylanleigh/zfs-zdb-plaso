
:::::::::::::::::::::
ZFS ZDB Plaso Parsers
:::::::::::::::::::::

Version 1.0.1

http://research.dylanleigh.net/zfs-time-forensics/plaso-zdb/

Introduction
============

These parsers process output from the ZFS Debugger (ZDB) to generate events for
Plaso (http://plaso.kiddaland.net/) based on internal ZFS objects and metadata.

Files
=====

The ZFS ZDB parser project consists of 4 files (apart from documentation):

zfs_event.py
   Encapsulates ZFS events, and any data which must be stored as part of an event.

zfs_event_formatter.py
   Output formatter for ZFS events.

zfs_zdb_dataset.py
   Parser for file events from ZDB dataset output.

zfs_zdb_label.py
   Parser for Uberblock events from ZDB label output.

Installation
============

These instructions are for FreeBSD 9; file locations for other 
operating systems may vary.

1. Install Plaso from ports (security/py-plaso) or by using pkg::

   # pkg install py-plaso

2. Install/copy zfs_event.py to the Plaso events directory::

   # install zfs_event.py /usr/local/lib/python2.7/site-packages/plaso/events/

3. Install/copy both parsers to the Plaso parsers directory::

   # install zfs_zdb_label.py zfs_zdb_dataset.py /usr/local/lib/python2.7/site-packages/plaso/parsers/

4. Add the new parsers to the parser initialization script::

   # echo from plaso.parsers import zfs_zdb_label >> /usr/local/lib/python2.7/site-packages/plaso/parsers/__init__.py
   # echo from plaso.parsers import zfs_zdb_dataset >> /usr/local/lib/python2.7/site-packages/plaso/parsers/__init__.py

5. Install/copy zfs_event_formatter.py to the Plaso formatters directory::

   # install zfs_event.py /usr/local/lib/python2.7/site-packages/plaso/formatters/

6. Add the new formatter to the formatter initialization script::

   # echo from plaso.formatters import zfs_event_formatter >> /usr/local/lib/python2.7/site-packages/plaso/formatters/__init__.py

7. Optional: Add the new parsers to the category lists in the presets file
             /usr/local/lib/python2.7/site-packages/plaso/frontend/presets.py


Usage
=====

Quick Start for Testing:
------------------------

As the new parsers read output from the ZFS debugger - not from 
files or the filesystem itself - it is necessary to run ZDB first 
manually. The following ZDB commands are used:

For vdev label (with uberblocks)::

   # zdb -P -uuu -l <device> > <uberblock-file>

For dataset::

   # zdb -P -bbbbbb -dddddd <poolname>/<dataset> > <dataset-file>

The output from ZDB can then be processed by Plaso using the log2timeline.py
command:

For vdev label (with uberblocks)::

   $ log2timeline.py --parsers zfs_zdb_label <output-file> <uberblock-file>

For dataset::

   $ log2timeline.py --zone <timezone> --parsers zfs_zdb_dataset <output-file> <dataset-file>

WARNING: The dataset parser needs the timezone specified to convert timestamps
         from the target system's local time to UTC time.

The output file can be an existing Plaso output file; new events 
will be added to it, including events from other parsers. The "mactime" parser
may be useful in conjunction with the "mac-robber" program to gather timestamps
from a mounted filesystem and import the events into plaso.

Events can be observed by using the Plaso psort.py command amongst others::

   $ psort.py <output-file>

Working with ZFS device images:
-------------------------------

- It is assumed here you have disk images of each device in the Zpool copied
  via dd or similar, and they are all in one directory somewhere.

- The vdev label parser can be used directly on each device image (not
  including special purpose devices such as log, cache, or hot spares).

    # zdb -P -uuu -l <device> > <uberblock-file>
    $ log2timeline.py --parsers zfs_zdb_label <output-file> <uberblock-file>

- To use the dataset parser - and access the filesystem itself for other
  Plaso parsers - you need to import the devices in the pool read only::

   zpool import -R <alternate-root-dir> -o readonly=on -d <dir-with-disk-images>

   WARNING: The altroot property will mount filesystems from the new pool
   under that root - if you do not specify this the imported pool could
   remount anywhere including /, /usr etc.

- Use zfs list to get all the filesystem datasets for the dataset parser::

    # zfs list -t filesystem

    Note: the -h option to zfs list can be useful if you want to automate this
    step and the next one.

- Then use the ZDB commands to get the object information for each dataset and
  add it to plaso::

   # zdb -P -bbbbbb -dddddd <poolname>/<dataset> > <dataset-file>
   $ log2timeline.py --zone <timezone> --parsers zfs_zdb_dataset <output-file> <dataset-file>

   WARNING: The dataset parser needs the timezone specified to convert timestamps
            from the target system's local time to UTC time.

- Finally run log2timeline.py on the ALTROOT to add all the non-ZFS events to
  the timeline::

   $ log2timeline.py <output-file> <altroot>

- All available events should now be in the output-file.

References/Background
=====================

This software is based on my studies into ZFS Timeline Analysis, see http://research.dylanleigh.net/zfs-time-forensics/

The discussion there will help you make the most use of the ZFS events for
timeline analysis.

My Presentation at BSDCan:
   D. Leigh, "Forensic Timestamp Analysis of ZFS", BSDCan 2014, May
   2014.
   http://www.bsdcan.org/2014/schedule/events/464.en.html

ZFS Timeline Forensics Quick Reference:
    http://research.dylanleigh.net/zfs-bsdcan-2014/zfs-timeline-quickref.pdf

FAQ/Misc
========

Will these parsers be added to the mainstream Plaso?
   Because they require manual preprocessing, not at this stage. If we can get
   them working automatically (which will probably mean adding ZFS support
   to TSK which is a BIG task!) then yes.

What are the advantages of the ZFS events over the POSIX filesystem
timestamp events (from mactime/mac-robber/etc)?

   1) The ZFS events can be used to detect when the mtime/crtime of the file has been forged.

   2) The ZFS events can be used to determine some of the times a file was
      modified before the most recent mtime. This generally only works for files
      >128KB and for files modified in parts; see the references for details.

How should I make use of these parsers with other Plaso parsers?
   See "Working with ZFS device images" in the Usage section above - summary
   is: Import the pool read-only with an ALTROOT and run Plaso on the altroot
   directory to get non-ZDB evens.

Changelog
=========

1.0.1 - 2014-07-24
        Initial Public release, improved readme and minor fixes

1.0.0 - Initial version for my Honours coursework project.

Licence
=======

Copyright (c) 2014 Dylan Leigh. All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software without
   specific prior written permission.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.

IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE, EVEN IF ADVISED
OF THE POSSIBILITY OF SUCH DAMAGE.

TODO
====

Critical
--------

   - Proper unit tests for both parsers
      - We have heaps of test files, just need to add the test_lib stuff
   - Need a way to pass GUID into Dataset parser
        - Using the poolname temporarily as a workaround
   - Fix event generation with unknown time

Urgent
------

   - Conform to Plaso style guidelines (http://plaso.kiddaland.net/developer/style-guide)
   - Wrapper script to automatically do everything, given a directory of disk
     images and an ALTROOT dir to use temporarily.
   - Find a way for the parsers to call ZDB directly instead of requiring manual intervention
      - Need a way to enumerate all the dataset names from a given device, or set of devices.
   - Support for snapshots and/or clones

Not Urgent
----------

   - Retain more data from file objects (partially implemented)
   - Analysis plugins to:
      - Remove duplicate events from redundant uberblocks
      - Automatic reconstruction of timestamp for modification events
        generated from L0 BPs with known TXG but unknown time

Wishlist
--------

   - Improve performance of Dataset parser
   - Analysis plugins to:
      - Automatic detection of timestamp inconsistencies
         - Automartic detection of false positive inconsistencies
           caused by clock corrections, daylight savings, etc
   - Support for ZVOLs

