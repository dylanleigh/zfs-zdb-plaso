#!/usr/bin/python
#
# Copyright 2014 Dylan Leigh
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Event Formatter for ZFSEvents, used by the ZFS ZDB Parsers
"""

from plaso.lib import eventdata

class ZFSUberBlockEventFormatter(eventdata.EventFormatter):
   """ZFS Uberblock Event Formatter. This event represents a write of an
   uberblock, which occurs once in each vdev affected by a transaction. It only
   contains the TXG and timestamp as recorded in the uberblock.
   Can be strict as this will always have a TXG and Timestamp.
   """

   DATA_TYPE = "fs:zfs:uberblock"
   FORMAT_STRING = u'Uberblock: Pool: {pool_guid} TXG: {txg}'
   FORMAT_STRING_SHORT = u'ZFS UB: {pool_guid} {txg} {timestamp}'
   SOURCE_LONG = "ZFS Uberblock"
   SOURCE_SHORT = 'ZFS'
   

class ZFSFileCreateEventFormatter(eventdata.EventFormatter):
   """Formatter for a ZFS File Create Event.
   Can be strict as this will always have a TXG and Timestamp.
   NOTE: File atributes in the object are the latest attributes, NOT those
   at the time of this event.
   """

   DATA_TYPE = "fs:zfs:file:create"

   FORMAT_STRING = u'Create: Pool: {pool_guid} TXG: {txg} Path: {fileobj}'

   SOURCE_LONG = "ZFS File Create"
   SOURCE_SHORT = 'ZFS'

class ZFSFileModifyEventFormatter(eventdata.EventFormatter):
   """Class for a ZFS File Modify Event.
   One of these is created for the top level BP of each file and all leaf
   / level 0 BPs of that file (if it uses Indirect Blocks).
   TXG is the BP TXG,
   timestamp is the file's MTime (the top level BP) or None (any later l0 BPs)

   As timestamp may be None this formatter needs to be conditional, so it is
   more complex than the others.
   """

   DATA_TYPE = "fs:zfs:file:modify"

   # TODO: Use ConditionalEventFormatter? This seems to be working correctly
   # if there are none with Timestamp=None, as the POSIXTimeEvent requires
   # timestamp anyway
   FORMAT_STRING = u'Modify: Pool: {pool_guid} TXG: {txg} Path: {fileobj}'
   SOURCE_LONG = "ZFS File Modify"
   SOURCE_SHORT = 'ZFS'
