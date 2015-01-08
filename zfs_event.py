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
"""Events for ZFS, used by the ZFS ZDB Parsers

"""

from plaso.lib import event
from plaso.lib import eventdata

# XXX: Unused for now
#class ZFSBlockPointer():
#   """Class for a single direct ZFS BP - for use in later work?"""
#   
#   def __init__(self, txg, dva, level):
#      self.txg = txg
#      self.dva = dva
#      self.level = level

class ZFSObject():
   """Class for ZFS Object
   TODO: This could be expanded in future work to contain more data.
   Currently it only stores object number, dataset name and type."""

   def __init__(self, pool_guid, dataset_name, obj_num, obj_type):
      """Init for a ZFS Object of any type within a dataset."""
      self.pool_guid = pool_guid
      self.dataset_name = dataset_name
      self.obj_num = obj_num
      self.obj_type = obj_type
   
   def __str__(self):
      """Return a string representation of the ZFSObject."""
      return unicode(self).encode('utf-8')

   def __unicode__(self):
      """Print a human readable string from the Object."""
      return unicode(self).encode('utf-8')

   # TODO: Later analysis work may need equivalence classes

class ZFSFileObject(ZFSObject):
   """Class for ZFS File / Dir (ZPL) Objects
   TODO: This could be expanded in future work to contain more data.
   """

#  TODO: Future attributes:
#  def __init__(self, path, size, atime, mtime, ctime, crtime, gentxg):

   def __init__(self, path):
      """Init for a ZFS Plain File object."""
      # TODO: later matching stuff will need superclass attributes
      self.path = path
      #self.topbp = ZFSBlockPointer(topbp) TODO: later
   
   def __str__(self):
      """Return a string representation of the File Object."""
      # TODO: Curently this just stores/returns the file path.
      return unicode(self.path).encode('utf-8')

   def __unicode__(self):
      """Print a human readable string from the Object."""
      # TODO: Curently this just stores/returns the file path.
      return unicode(self.path).encode('utf-8')

   # TODO: Later analysis work may need equivalence classes

class ZFSEvent(event.PosixTimeEvent):
#class ZFSEvent(event.PosixTimeEvent):
   """SuperClass for all ZFS Events.
   All events are linked to a Transaction Group (TXG) from a specific ZFS
   pool, and may contain a Timestamp.
   """

   def __init__(self, pool_guid, txg, usage, data_type, timestamp=None):
      """Initializes a ZFS Event.

      Arguments / Attributes:
      data_type: (inherited): Should be overridden by subclass, in the format
         "fs:zfs:<unique keywords>"
      usage: (inherited) should be "mtime", "crtime" etc applicable
         to the timestamp.
      posix_time: (inherited) is the timestamp; it may be None if
         the exact time is unkown but can be determined later
         from the TXG.
      txg: is the zpool Transaction Group in which this event
         occurred and is REQUIRED.
      pool_guid: is the GUID of the zpool and is REQUIRED to avoid
         clashes and make use of the TXG values if events from
         multiple pools are combined into the same timeline.
      """
      super(ZFSEvent, self).__init__(int(timestamp),\
                                     usage, data_type) # PosixTimeEvent
      #self.timestamp = timestamp # for UML purposes only XXX
      #self.timestamptype = usage # for UML purposes only XXX
      self.pool_guid = pool_guid
      self.txg = txg

class ZFSUberBlockEvent(ZFSEvent):
   """Class for a ZFS Uberblock Event. This event represents a write of an
   uberblock, which occurs once in each vdev affected by a transaction. It only
   contains the TXG and timestamp as recorded in the uberblock.
   """

   DATA_TYPE = "fs:zfs:uberblock"

   def __init__(self, pool_guid, txg, timestamp):
      """Initializes a ZFS Uberblock Event.
      Arguments / Attributes:

      txg: The Transaction Group ID (TXG)
      timestamp: The timestamp as recorded in the uberblock
      pool_guid: is the GUID of the zpool (at the top of zdb -uuu output)
      """
      super(ZFSUberBlockEvent, self).__init__(pool_guid, txg, \
         "ZFS-uberblock", self.DATA_TYPE, timestamp)
      

class ZFSFileCreateEvent(ZFSEvent):
   """Class for a ZFS File Create Event.
   TXG is the Gen TXG, and timestamp is the file's CRTime.
   
   TODO: File atributes in the object are the latest attributes, NOT those
   at the time of this event.
   """

   DATA_TYPE = "fs:zfs:file:create"

   def __init__(self, pool_guid, gentxg, fileobj, crtime):
      """Initializes a ZFS File Creation Event.

      Arguments / Attributes:
      pool_guid: is the GUID of the zpool
      gentxg: The file's Gen TXG (transaction when it was created)
      crtime: The file creation timestamp (crtime)
      fileobj: A ZFSFileObject with the object number, dataset name,
         file path etc.
      """
      super(ZFSFileCreateEvent, self).__init__(pool_guid, gentxg, \
         "crtime", self.DATA_TYPE, crtime)
      self.fileobj = fileobj

class ZFSFileModifyEvent(ZFSEvent):
   """Class for a ZFS File Modify Event.
   One of these is created for the top level BP of each file and all leaf
   / level 0 BPs of that file (if it uses Indirect Blocks).
   TXG is the BP TXG,
   timestamp is the file's MTime (the top level BP) or None (any later l0 BPs)
   """

   DATA_TYPE = "fs:zfs:file:modify"

   def __init__(self, pool_guid, bptxg, fileobj, mtime=None) :
      """Initializes a ZFS File Modification Event.

      Arguments / Attributes:
      pool_guid: is the GUID of the zpool
      bptxg: Birth TXG from the Block Pointer of this event
      mtime: The modification time of the file - XXX WARNING: this
         should ONLY be recorded for the FIRST, TOP LEVEL BP of
         the file. For any later indirect blocks, we only create
         events for the level 0 and do NOT add the modification
         time to them. We need to cross-reference to determine
         the modification time later.
      fileobj: A ZFSFileObject with the object number, dataset name,
         file path etc.
      """
      super(ZFSFileModifyEvent, self).__init__(pool_guid, bptxg, \
         "mtime", self.DATA_TYPE, mtime)
      self.fileobj = fileobj
