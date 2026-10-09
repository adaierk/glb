"""Actual original-client control capture and fragmented aligned TCP frames."""
import struct,unittest
from native_data_packets import FrameStream,data405,parse405
from account_packets import message

class NativePaddingTests(unittest.TestCase):
    def test_actual_original_407_capture(self):
        raw=bytes.fromhex('12345678200007041b0001006060010000001900010000000100031234567800')
        s=FrameStream();self.assertEqual(s.feed(raw[:23]),[]);self.assertEqual(s.feed(raw[23:]),[raw])

    def test_application_payload_excludes_native_alignment(self):
        p=message(0x19,b'',1);f=bytearray(data405(p,0,2));f.extend(bytes(3))
        struct.pack_into('<H',f,4,len(f))
        self.assertEqual(parse405(bytes(f))['payload'],p)
        self.assertEqual(FrameStream().feed(bytes(f)*2),[bytes(f)]*2)

    def test_bad_tail_offset_and_excess_padding_rejected(self):
        for tail,pad in [(19,0),(25,8)]:
            f=bytearray(data405(message(0x19,b'',1),0,2));f.extend(bytes(pad))
            struct.pack_into('<H',f,4,len(f));struct.pack_into('<H',f,8,tail)
            with self.assertRaises(ValueError):FrameStream().feed(f)

if __name__=='__main__':unittest.main()
