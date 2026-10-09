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

    def test_actual_encrypted_compressed_right_click(self):
        frame=bytes.fromhex('123456785c000504580001000000030000000400efff0000000000000100340003000000e04918b34f4918b3664918b349e9927cffb74080ff49dfb3a72ee82eedc15c80e06c8091be4b4efd4f4918b3e4e6fe9e50832b8812345678')
        result=parse405(frame)
        self.assertTrue(result['encrypted'] and result['compressed'])
        self.assertEqual((result['opcode'],result['request_id']),(0xed,44))
        self.assertEqual(result['payload'].hex(),'80ed0024002c000000000000240000000801120101000000010000000100000001000000')

if __name__=='__main__':unittest.main()
