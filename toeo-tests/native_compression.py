"""Bounded CNLzComp1 translation of original 5F8F60 / 5F8A20.

16-byte transport wrapper: type, plain length, coded length, original raw CRC32.
Code dictionary and LRU order follow the original x86, independently checked
against original 622AC0 and captured native requests.
"""
import struct,zlib


def raw_crc32(payload):
    return zlib.crc32(payload,0xffffffff)^0xffffffff


def decompress(wrapper):
    if len(wrapper)<16:raise ValueError('Short native compression header')
    kind,length,coded,crc=struct.unpack_from('<IIII',wrapper)
    if kind!=1 or not 9<=length<=60000 or coded!=len(wrapper)-16:
        raise ValueError('Invalid native compression bounds')
    source=wrapper[16:];bitpos=0
    def bits(n):
        nonlocal bitpos
        if bitpos+n>len(source)*8:raise ValueError('Truncated native compressed data')
        value=0
        for _ in range(n):
            value=(value<<1)|((source[bitpos//8]>>(7-bitpos%8))&1);bitpos+=1
        return value
    end=4096;count=256;width=1;threshold=2;head=tail=end
    chars=list(range(256))+[0]*(end-256)
    parents=[end]*end;children=[end]*end;siblings=[end]*end;previous_sibling=[end]*end
    newer=[end]*(end+1);older=[end]*(end+1)
    def detach(node):
        nonlocal tail,head
        if node==tail:
            tail=newer[node];older[tail]=end
        else:
            newer[older[node]]=newer[node];older[newer[node]]=older[node]
        if node==head:head=older[node]
    def insert(node,after):
        nonlocal head,tail
        if head==end:
            head=tail=node;newer[node]=older[node]=end
        elif after==end:
            older[node]=end;newer[node]=tail;older[tail]=node;tail=node
        elif after==head:
            older[node]=head;newer[node]=end;newer[head]=node;head=node
        else:
            older[node]=after;newer[node]=newer[after]
            older[newer[after]]=node;newer[after]=node
    def find(parent,char):
        node=children[parent]
        while node!=end:
            if chars[node]==char:return node
            node=siblings[node]
        return end
    def extend(sequence,parent,depth):
        nonlocal count
        if parent==end:return
        for char in sequence:
            depth+=1
            if depth>256:return
            node=find(parent,char)
            if node==end:
                if count<end:node=count;count+=1
                else:
                    node=tail
                    if node==parent:return
                    detach(node)
                    prev=previous_sibling[node];nxt=siblings[node]
                    if prev!=end:siblings[prev]=nxt
                    else:children[parents[node]]=nxt
                    if nxt!=end:previous_sibling[nxt]=prev
                chars[node]=char;parents[node]=parent;children[node]=end
                previous_sibling[node]=end;siblings[node]=children[parent]
                if children[parent]!=end:previous_sibling[children[parent]]=node
                children[parent]=node
                insert(node,head if parent<256 else older[parent])
            parent=node
    output=bytearray();last=end;last_length=0
    while bitpos<len(source)*8:
        if count-256>=threshold:width+=1;threshold*=2
        code=bits(width)+256 if bits(1) else bits(8)
        if code>=count:raise ValueError('Invalid native compression dictionary code')
        current=code;chain=[]
        while current!=end:
            if len(chain)>=4096:raise ValueError('Cyclic native compression dictionary')
            if current>=256 and current!=head:
                detach(current);insert(current,head)
            chain.append(chars[current]);current=parents[current]
        sequence=bytes(reversed(chain))
        if len(output)+len(sequence)>length:raise ValueError('Native decompression exceeds declared size')
        output.extend(sequence);extend(sequence,last,last_length)
        last=code;last_length=len(sequence)
        if len(output)==length:break
    if len(output)!=length or raw_crc32(output)!=crc:raise ValueError('Native compression length or CRC mismatch')
    return bytes(output)
