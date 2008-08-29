#!/usr/bin/python
'''Copyright 2008 The Apache Software Foundation
 
  Licensed to the Apache Software Foundation (ASF) under one
  or more contributor license agreements.  See the NOTICE file
  distributed with this work for additional information
  regarding copyright ownership.  The ASF licenses this file
  to you under the Apache License, Version 2.0 (the
  "License"); you may not use this file except in compliance
  with the License.  You may obtain a copy of the License at
 
     http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.
''' 
# Instructions:
# 1. Run Thrift to generate python module HBase
#    thrift --gen py ../../../src/java/org/apache/hadoop/hbase/thrift/Hbase.thrift 
# 2. Copy gen-py/HBase module into your project tree and change import string
# Contributed by: Ivan Begtin (ibegtin@gmail.com, ibegtin@enotpoiskun.ru)

import sys
import time

from thrift import Thrift
from thrift.transport import TSocket, TTransport
from thrift.protocol import TBinaryProtocol
from Hbase import ttypes
from Hbase.Hbase import Client, ColumnDescriptor, Mutation

def printVersions(row, versions):
    print "row: " + row + ", values: ",
    for cell in versions:
        print cell.value + "; ",
    print

def printRow(entry):
    print "row: " + entry.row + ", cols",
    for k in sorted(entry.columns):
        print k + " => " + entry.columns[k].value,
    print


# Make socket
transport = TSocket.TSocket('localhost', 9090)

# Buffering is critical. Raw sockets are very slow
transport = TTransport.TBufferedTransport(transport)

# Wrap in a protocol
protocol = TBinaryProtocol.TBinaryProtocol(transport)

# Create a client to use the protocol encoder
client = Client(protocol)

# Connect!
transport.open()

t = "demo_table"

#
# Scan all tables, look for the demo table and delete it.
#
print "scanning tables..."
for table in client.getTableNames():
    print "  found: %s" %(table)
    if table == t:
        print "    disabling table: %s" %(t)
        if client.isTableEnabled(table):
            client.disableTable(table)
	print "    deleting table: %s"  %(t)	
	client.deleteTable(table)

columns = []
col = ColumnDescriptor()
col.name = 'entry:'
col.maxVersions = 10
columns.append(col)
col = ColumnDescriptor()
col.name = 'unused:'
columns.append(col)

try:
    client.createTable(t, columns)
except AlreadyExists, ae:
    print "WARN: " + ae.message

cols = client.getColumnDescriptors(t)
for col_name in cols.keys():
    col = cols[col_name]
    print "  column: %s, maxVer: %d" % (col.name, col.maxVersions)
#
# Test UTF-8 handling
#
invalid = "foo-\xfc\xa1\xa1\xa1\xa1\xa1"
valid = "foo-\xE7\x94\x9F\xE3\x83\x93\xE3\x83\xBC\xE3\x83\xAB";

# non-utf8 is fine for data
mutations = [Mutation({"column":"entry:foo", "value":invalid})]
client.mutateRow(t, "foo", mutations)

# try empty strings
mutations = [Mutation({"column":"entry:", "value":""})]
client.mutateRow(t, "foo", mutations)

# this row name is valid utf8
mutations = [Mutation({"column":"entry:foo", "value":valid})]
client.mutateRow(t, "foo", mutations)

# non-utf8 is not allowed in row names
try:
    mutations = [Mutation({"column":"entry:foo", "value":invalid})]
    client.mutateRow(t, invalid, mutations)
except ttypes.IOError, e:
    print 'expected exception: %s' %(e.message)

# Run a scanner on the rows we just created
print "Starting scanner..."
scanner = client.scannerOpen(t, "", ["entry::"])
try:
    while 1:
	printRow(client.scannerGet(scanner))
except ttypes.NotFound, e:
    print "Scanner finished"

#
# Run some operations on a bunch of rows.
#
for e in range(100, 0, -1):
    # format row keys as "00000" to "00100"
    row = "%0.5d" % (e)

    mutations = [Mutation({"column":"unused:", "value":"DELETE_ME"})]
    client.mutateRow(t, row, mutations)
    printRow(client.getRow(t, row))
    client.deleteAllRow(t, row)
    
    mutations = [Mutation({"column":"entry:num", "value":"0"}),
                 Mutation({"column":"entry:foo", "value":"FOO"})]
    client.mutateRow(t, row, mutations)
    printRow(client.getRow(t, row));

    mutations = []
    m = Mutation()
    m.column = "entry:foo"
    m.isDelete = 1
    mutations.append(m)
    m = Mutation()
    m.column = "entry:num"
    m.value = "-1"
    mutations.append(m)
    client.mutateRow(t, row, mutations)
    printRow(client.getRow(t, row));

    mutations = [Mutation({"column":"entry:num", "value":str(e)}),
                 Mutation({"column":"entry:sqr", "value":str(e*e)})]
    client.mutateRow(t, row, mutations)
    printRow(client.getRow(t, row));

    time.sleep(0.05)
  
    mutations = []
    m = Mutation()
    m.column = "entry:num"
    m.value = "-999"
    mutations.append(m)
    m = Mutation()
    m.column = "entry:sqr"
    m.isDelete = 1
    mutations.append(m)
    client.mutateRowTs(t, row, mutations, 1) # shouldn't override latest
    printRow(client.getRow(t, row))

    versions = client.getVer(t, row, "entry:num", 10)
    printVersions(row, versions)
    if len(versions) != 4:
        print("FATAL: wrong # of versions")
        sys.exit(-1)
  
    try:
	client.get(t, row, "entry:foo")
        print("FATAL: shouldn't get here")
        sys.exit(-1)
    except ttypes.NotFound:
	pass

    print

columnNames = []
for col2 in client.getColumnDescriptors(t):
    print "column name is "+col2.name
    print col2
    columnNames.append(col2.name+":")

print "Starting scanner..."
scanner = client.scannerOpenWithStop(t, "00020", "00040", columnNames)
try:
  while 1:
    printRow(client.scannerGet(scanner))
except ttypes.NotFound:
    client.scannerClose(scanner)
    print "Scanner finished"
  
transport.close()
