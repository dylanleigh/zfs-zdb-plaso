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
"""Parser for ZFS Vdev Labels / Uberblocks from ZDB

   i.e. output of "zdb -P -uuu -l <device>"

   Parts of this parser are based on the mactime and xchat parsers.
"""

__author__ = 'Dylan Leigh (research.dylanleigh.net)'

import logging
import pyparsing

from plaso.events import zfs_event

from plaso.lib import text_parser

class ZFSZDBVdevLabelParser(text_parser.PyparsingSingleLineTextParser):
   """Parses ZDB -uuu -l <dev> output - vdev label - for Uberblock events

   Using a line by line parser:

   1) If "pool_guid:<guid>" extract to add to events later
   2) If "Uberblock[<slot>]" prepare to extract:
      2.1) get txg "txg = <txg>"
      2.2) get timestamp "timestamp = <time>"
      2.3) Once we have both of these, create a new ZFS event
   """

   NAME = "zfs_zdb_label"
   #ENCODING = 'utf-8' # TODO: raw?

   #  PYPARSING VARS
   # LITERALS
   #EQ   = pyparsing.Literal("=").suppress()
   #COLON   = pyparsing.Literal(":").suppress()
   #LSQB    = pyparsing.Literal("[").suppress()
   RSQB  = pyparsing.Literal("]").suppress()

   # CHAR CLASSES
   DIGITS   = pyparsing.Word(pyparsing.nums) # Multiple numbers
   PRINT    = pyparsing.printables           # A printable character
   WORDS    = pyparsing.Word(PRINT)          # Multiple characters

   # LINES
   POOL_GUID = pyparsing.Literal("pool_guid: ").suppress() + DIGITS
   UB_SLOT = pyparsing.Literal("Uberblock[").suppress() + DIGITS + RSQB
   UB_TXG = pyparsing.Literal("txg = ").suppress() + DIGITS

   UB_TIME = pyparsing.Literal("timestamp = ").suppress() + DIGITS + \
      pyparsing.SkipTo(pyparsing.lineEnd).suppress()
   # Note timestamp lines like:
   # timestamp = 1384818880 UTC = Tue Nov 19 10:54:40 2013
   # pyparsing.Literal(" UTC = ").suppress() + 

   LINE_STRUCTURES = [
      ('pool_guid', POOL_GUID),
      ('ub_slot', UB_SLOT),
      ('ub_txg', UB_TXG),
      ('ub_time', UB_TIME),
      ('ignore', WORDS),      # Last = Lowest priority
   ]

   HEADER_SIGNATURE = pyparsing.Keyword("--------------------------------------------")
   HEADER = (HEADER_SIGNATURE.suppress()) # TODO: add Label: X 

   def __init__(self, pre_obj, config=None):
       """ZFS ZDB Vdev Label parser object constructor."""
       super(ZFSZDBVdevLabelParser, self).__init__(pre_obj, config)
       self.offset = 0
       #self.local_zone = getattr(pre_obj, 'zone', pytz.utc)
       
       self.curr_pool_guid = None
       self.curr_ub_slot = None
       self.curr_ub_txg = None
       self.curr_ub_time = None

   def VerifyStructure(self, line):
      """Verify that this parser was given data from zdb -uuu."""
      # Line 1: "--------------------------------------------"
      try:
         parse_result = self.HEADER.parseString(line)
      except pyparsing.ParseException:
         logging.debug(u'Unable to parse, Vdev Label Header not found')
         return False
      return True

   def SpawnEvent(self):
      """IF both txg and time are filled in, create a new event and reset"""
      if ((self.curr_ub_txg is not None) and (self.curr_ub_time is not None)):
         txg = self.curr_ub_txg
         time = self.curr_ub_time
         self.curr_ub_txg = None
         self.curr_ub_time = None
         logging.debug(u'Create event with txg and time: %s %s'%(txg,time))
         return zfs_event.ZFSUberBlockEvent(self.curr_pool_guid, txg, time)

   def ParseRecord(self, key, structure):
      """Parse each record structure and return an EventObject if applicable."""

      if key == 'ub_slot':
         logging.debug(u'Matched ub_slot: %s'%(structure,))
         self.curr_ub_slot = int(structure[0])
         # Reset these for new slot = new event
         self.curr_ub_txg = None
         self.curr_ub_time = None
         return

      elif key == 'ub_txg':
         logging.debug(u'Matched ub_txg: %s'%(structure,))
         self.curr_ub_txg = long(structure[0])
         return self.SpawnEvent()
      elif key == 'ub_time':
         logging.debug(u'Matched ub_time: %s'%(structure,))
         self.curr_ub_time = long(structure[0])
         return self.SpawnEvent()

      elif key == 'pool_guid':
         logging.debug(u'Matched pool_guid: %s'%(structure,))
         self.curr_pool_guid = str(structure[0]) # Treat GUID as a str
         return
      else:
         logging.debug(u'Unknown line ignored: %s'%(structure,))
         return

      # TODO: Parse vdev GUID, guid_sum, UB slot as well?
