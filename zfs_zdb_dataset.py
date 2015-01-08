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
"""Parser for ZFS Dataset dump from ZDB
   i.e. output of "zdb -P -bbbbbb -dddddd <dataset>"

   Parts of this parser are based on the mactime and xchat parsers.
"""

__author__ = 'Dylan Leigh (research.dylanleigh.net)'

import logging
import pyparsing

import pytz

from plaso.events import zfs_event

from plaso.lib import timelib
from plaso.lib import text_parser

class ZFSZDBDatasetParser(text_parser.PyparsingSingleLineTextParser):
   """Parses "zdb -P -bbbbbb -dddddd <dataset>" for file create/modify events

   Using a line by line parser:

   1) If dataset header extract dataset name to add to events later
		e.g. "Dataset poolv7r0/filesim [ZPL],...."
   2) If Start of object header detected, clear any per-obj vars
      2.1) Save object number and type from line after header
		2.2) Check type - if object is not a file, ignore it
      2.3) parse to get gen txg, crtime and mtime
      2.4) Once we have both gen and CRtime, spawn CreateEvent
      2.5) Once we reach the top level block, parse it to get its TXG
			2.5.1) Spawn a ModifyEvent with the top level block TXG and file mtime
                THEN RESET file mtime for below!
			2.5.2) Parse for any LATER level 0 BPs, spawn a new ModifyEvent with a
					 None timestamp. This needs to be joined on TXG later to get the
					 time (within 5 seconds)

	Start of object / object HEADER:
  		Object  lvl   iblk   dblk  dsize  lsize   %full  type
        12    1  16384  12288  12288  12288  100.00  ZFS plain file (K=inherit) (Z=inherit)
	...
	Gen / Crtime / Mtime: 
		  mtime   Wed Nov 20 23:40:03 2013
        ctime   Wed Nov 20 23:40:03 2013
        crtime  Tue Nov 19 12:23:57 2013
        gen     25
	...
	BP list with HEADER:
		Indirect blocks:
               0 L0 DVA[0]=<3:229eea00:3000> [L0 ZFS plain file] fletcher4 uncompressed LE contiguous unique single size=3000L/3000P birth=25406L/25406P fill=1 cksum=537fffffb40:21b297ffdebaa0:879a15d77897d4c0:5e783f30b0cddd10
	...
	BP list with multiple blocks looks like:
	Indirect blocks:
               0 L1  DVA[0]=<6:3c10e00:400> DVA[1]=<0:3940000:400> [L1 ZFS plain file] fletcher4 lzjb LE contiguous unique double size=4000L/400P birth=3110L/3110P fill=2 cksum=5ba0b9feab:3ca8122fed40:156c3a8e829722:554cbf984e38a0b
               0  L0 DVA[0]=<6:3cafe00:20000> [L0 ZFS plain file] fletcher4 uncompressed LE contiguous unique single size=20000L/20000P birth=3110L/3110P fill=1 cksum=3c3c3c3c0000:f0f2d2d1e1e0000:9191a32314140000:21919cdccf0f0000
           20000  L0 DVA[0]=<6:3db3000:20000> [L0 ZFS plain file] fletcher4 uncompressed LE contiguous unique single size=20000L/20000P birth=3110L/3110P fill=1 cksum=2ebe969667d8:e4dc5e86a2ab290:58e7896f0172ce70:59f652413c502408
	...
   """

   NAME = "zfs_zdb_dataset"
   #ENCODING = 'utf-8' # TODO: raw?

   #  PYPARSING VARS
   # LITERALS
   #EQ   = pyparsing.Literal("=").suppress()
   #COLON   = pyparsing.Literal(":").suppress()
   LSQB    = pyparsing.Literal("[").suppress()
   #RSQB  = pyparsing.Literal("]").suppress()
   PERIOD = pyparsing.Literal(".").suppress()
   LITERAL_L = pyparsing.Literal("L").suppress()

   # CHAR CLASSES
   DIGITS   = pyparsing.Word(pyparsing.nums) # Multiple numbers
   HEXDIGITS= pyparsing.Word(pyparsing.hexnums) # Hexadecimal nums
   PRINT    = pyparsing.printables           # A printable character
   WORD     = pyparsing.Word(PRINT)          # Multiple characters
   WORDS    = pyparsing.OneOrMore(WORD)      # Multiple characters and spaces

   # LINES
   # Match Header "Dataset poolv7r0/filesim [ZPL],...."
   DATASET_HEADER = pyparsing.Literal("Dataset ").suppress() \
                  + WORD \
                  + pyparsing.Literal("[ZPL]").suppress() \
                  + pyparsing.SkipTo(pyparsing.lineEnd).suppress()

   # Marks start of new object XXX: No longer used
   #OBJECT_HEADER_TEXT = pyparsing.Literal("Object") + ...

   # Starts with obj number, ends with type / inherit info. We discard the rest
   OBJECT_HEADER_DATA = DIGITS \
                        + DIGITS.suppress() \
                        + DIGITS.suppress() + DIGITS.suppress() \
                        + DIGITS.suppress() + DIGITS.suppress() \
                        + DIGITS.suppress() + PERIOD + DIGITS.suppress() \
                        + pyparsing.SkipTo(pyparsing.lineEnd)

   # path, gen, crtime, mtime are just <key><whitespace><value>
   OBJECT_PATH = pyparsing.Literal("path").suppress() + WORDS
   OBJECT_GEN = pyparsing.Literal("gen").suppress() + DIGITS
   # mtime and ctime need to parse the timestamp components in detail.
   # We are using plaso's timelib later to convert the string
   # timestamp with timezone into a POSIX timestamp.
   # e.g. "Tue Jun 24 20:57:21 2014"
   TIMESTRING = WORD.suppress() + WORD + DIGITS + WORD + DIGITS
   OBJECT_MTIME = pyparsing.Literal("mtime").suppress() + TIMESTRING
   OBJECT_CRTIME = pyparsing.Literal("crtime").suppress() + TIMESTRING

   BLOCK_HEADER = pyparsing.Literal("Indirect blocks:")

   # We want the level and the birth txg.
   # Complex because there may be 1-3 DVAs, and multiple extra flags, possibly
   # missing fields.
   # Note level is prefixed by "L" with no space, we don't want the L.
   BLOCK_POINTER = HEXDIGITS.suppress() \
                   + LITERAL_L.suppress() + DIGITS \
                   + pyparsing.SkipTo(pyparsing.Literal("birth")).suppress() \
                   + WORD \
                   + pyparsing.SkipTo(pyparsing.lineEnd).suppress()

                   # XXX: Unknown why this doesn't work!:
                   # + pyparsing.Literal("birth=").suppress() + DIGITS \

                   #+ pyparsing.Literal("DVA[").suppress() # TODO: finer match
                   # + WORDS.suppress() \
                   #+ pyparsing.Literal("L/").suppress() \ # TODO: finer match
                   #+ DIGITS.suppress() + pyparsing.Literal("P").suppress() \

   # Example BP:
   # 4000       L0 DVA[0]=<3:780ed000:1000> DVA[1]=<4:7dd13200:1000>
   #  [L0 DMU dnode] fletcher4 lzjb LE contiguous unique double
   #  size=4000L/1000P birth=68732L/68732P fill=26
   #  cksum=1065276ec13:23f2bf4d79fdc:309a2331fbdd487:11fd63480494c 4bc

   # Segment listing - ignored
   SEGMENT = pyparsing.Literal("segment") + LSQB.suppress() \
             + pyparsing.SkipTo(pyparsing.lineEnd).suppress()

   # These are ordered for performance
   # Some of these are not parsed, but are used for lines we want to ignore, so
   # we don't bother doing further matching attempts on that line (for
   # performance)
   LINE_STRUCTURES = [
      ('segment', SEGMENT),
      ('block_pointer', BLOCK_POINTER),
      #('block_header', BLOCK_HEADER),
      #('obj_header_text', OBJECT_HEADER_TEXT), rm in favour of header_data
      ('obj_path', OBJECT_PATH),
      ('obj_gen', OBJECT_GEN),
      ('obj_mtime', OBJECT_MTIME),
      ('obj_crtime', OBJECT_CRTIME),
      ('obj_header_data', OBJECT_HEADER_DATA),
      ('dataset_header', DATASET_HEADER),
      ('ignore', WORDS),      # Last = Lowest priority
   ]
   # TODO: May need to add a line to match directory entries, to prevent a
   # filename clashing with mtime/gen/ctime matches.

   def __init__(self, pre_obj, config=None):
       """ZFS ZDB Dataset parser object constructor."""
       super(ZFSZDBDatasetParser, self).__init__(pre_obj, config)
       self.offset = 0

       self.local_zone = getattr(pre_obj, 'zone', pytz.utc) # Timezone XXX
       
       self.curr_pool_guid = None
       self.dataset_name = None

       self.curr_obj_number = None
       self.curr_obj_type = None
       self.curr_obj_gen = None
       self.curr_obj_crtime = None
       self.curr_obj_mtime = None
       self.curr_obj_path = None

   def VerifyStructure(self, line):
      """Verify that this parser was given data from zdb -dddddd"""
      try:
         parse_result = self.DATASET_HEADER.parseString(line)
      except pyparsing.ParseException:
         logging.debug(u'Unable to parse, Dataset Header not found')
         return False
      return True

   def SpawnCreateEvent(self):
      """IF both gen and crtime are filled in, create a new createevent"""
      if (      (self.curr_obj_gen is not None) \
            and (self.curr_obj_crtime is not None) \
            and ("ZFS plain file" in self.curr_obj_type) ):
         
         txg = self.curr_obj_gen
         time = self.curr_obj_crtime
         self.curr_obj_gen = None
         self.curr_obj_crtime = None
         logging.debug(u'ZFSFileCreateEvent with txg/time/path: %s %s %s'%\
               (txg,time, self.curr_obj_path))

         # TODO: Create a new ZFS file object to go with the returned event.
         # The fileobject currently only stores the path to the file.
         return zfs_event.ZFSFileCreateEvent(self.curr_pool_guid, txg, \
            self.curr_obj_path, time)

   def ParseRecord(self, key, structure):
      """Parse each record structure and return an EventObject if applicable."""

      # Matches for block pointers
      # This goes first because there are many of them
      if key == 'block_pointer':
         logging.debug(u'Matched block pointer: %s'%(structure,))
         # If we are not parsing a file object ignore the BP
         if ("ZFS plain file" not in self.curr_obj_type):
            return

         # If mtime exists and/or it is level 0, parse it,
         # set mtime to None and do an mtimeevent
         if ((self.curr_obj_mtime is not None) or (structure[0] == 'L0')):

            # extract birth TXG
            # TODO: This is kludgy, should be replaced. For some reason
            # pyparsing will not parse the birth TXG parts as individual
            # components so we have to split it up here.
            txg = int((str(structure[1]).lstrip('birth=').\
                  split('/'))[0].rstrip('L'))

            time = self.curr_obj_mtime
            self.curr_obj_mtime = None

            logging.debug(u'ZFSFileModify with txg/time/path: %s %s %s'%\
                  (txg, time, self.curr_obj_path))
            # TODO: Create a new ZFS file object to go with the returned event.
            # The fileobject currently only stores the path to the file.
            return zfs_event.ZFSFileModifyEvent(self.curr_pool_guid, txg, \
               self.curr_obj_path, time)

         # If there is no mtime read (this is not the first BP) and it is NOT
         # level 0 ignore
         return

      # Matches for obj attributes
      elif key == 'obj_path':
         logging.debug(u'Matched obj_path: %s'%(structure,))
         self.curr_obj_path=str(structure[0])
      elif key == 'obj_gen':
         logging.debug(u'Matched obj_gen: %s'%(structure,))
         self.curr_obj_gen= long(structure[0])
         return self.SpawnCreateEvent()
      elif key == 'obj_crtime':
         logging.debug(u'Matched crtime: %s'%(structure,))

         # Structure is [Month (string), day, time, year].
         # We want Something like "2013-07-01 12:53:12" 
         # Timelib converts to microsecond timestamps, reconvert to POSIX
         self.curr_obj_crtime = timelib.Timestamp.CopyToPosix( \
            timelib.Timestamp.FromTimeString( \
            str(structure[3]) + " " + str(structure[0]) + " " \
            + str(structure[1]) + " " + str(structure[2]), self.local_zone))
         return self.SpawnCreateEvent()

      elif key == 'obj_mtime':
         logging.debug(u'Matched mtime: %s'%(structure,))

         # Timelib converts to microsecond timestamps, reconvert to POSIX
         self.curr_obj_mtime = timelib.Timestamp.CopyToPosix( \
            timelib.Timestamp.FromTimeString( \
            str(structure[3]) + " " + str(structure[0]) + " " \
            + str(structure[1]) + " " + str(structure[2]), self.local_zone))
         # Don't spawn event now - wait for first BP

      # Match for object headers
      #elif key == 'obj_header_text':
      #   logging.debug(u'Matched new object header')
      # Reset all object vars
      #     self.curr_obj_number = None
      #     self.curr_obj_type = None
      #     return
      elif key == 'obj_header_data':
         logging.debug(u'Matched object header data: %s'%(structure,))
         # Reset all object vars
         self.curr_obj_gen = None
         self.curr_obj_crtime = None
         self.curr_obj_mtime = None
         self.curr_obj_path = None
         self.curr_obj_number = long(structure[0])
         self.curr_obj_type = str(structure[1]) # Object type + inherit info

      # Misc matches
      elif key == 'dataset_header':
         logging.debug(u'Matched dataset header: %s'%(structure,))
         self.dataset_name = str(structure[0])
         self.curr_pool_guid = self.dataset_name # TODO kludge to prevent clash!
         return

      # Ignored lines
      elif key == 'segment':
         #logging.debug(u'Ignoring Segment: %s'%(structure,))
         return
      else:
         logging.debug(u'Unknown line ignored: %s'%(structure,))
         return

      # TODO: Parse vdev GUID, guid_sum, UB slot as well?
