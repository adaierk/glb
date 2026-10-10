import hashlib,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from legacy_graphics_assets import expand_palette_tga,prepare_render_client

def fixture():
 palette=bytes([7,8,9,0,17,18,19,127,27,28,29,255]);indices=bytes([4,3,5,4])
 return struct.pack('<BBBHHBHHHHBB',2,1,1,3,3,32,7,8,2,2,8,0x30)+b'ID'+palette+indices

class GraphicsAssetTests(unittest.TestCase):
 def test_preserves_every_color_alpha_id_and_origin(self):
  converted,meta=expand_palette_tga(fixture());h=struct.unpack('<BBBHHBHHHHBB',converted[:18])
  self.assertEqual(h,(2,0,2,0,0,0,7,8,2,2,32,0x38));self.assertEqual(converted[18:20],b'ID')
  self.assertEqual(converted[20:],bytes([17,18,19,127,7,8,9,0,27,28,29,255,17,18,19,127]))
  self.assertEqual(meta['bgra_pixels_sha256'],hashlib.sha256(converted[20:]).hexdigest())
 def test_rejects_truncated_or_incompatible_data(self):
  source=fixture()
  for bad in (b'',source[:17],source[:-1],source+b'x',source[:-1]+b'\xff',source[:2]+b'\x09'+source[3:]):
   with self.assertRaises(ValueError):expand_palette_tga(bad)
 def test_isolated_copy_is_idempotent_and_original_untouched(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);original=root/'original';asset=original/'data/ui/image/statusbar.tga';asset.parent.mkdir(parents=True)
   source=fixture();asset.write_bytes(source);(original/'ToEO_CL.dat').write_bytes(b'original-exe')
   with patch('legacy_graphics_assets.KNOWN_PALETTES',{'ui/image/statusbar.tga':hashlib.sha256(source).hexdigest()}):
    runtime=prepare_render_client(original,root/'runtime',root/'proof.json');before=(runtime/'data/ui/image/statusbar.tga').read_bytes()
    prepare_render_client(original,runtime,root/'proof.json');self.assertEqual(before,(runtime/'data/ui/image/statusbar.tga').read_bytes())
   self.assertEqual(asset.read_bytes(),source);self.assertEqual((runtime/'ToEO_CL.dat').read_bytes(),b'original-exe')
   self.assertFalse(asset.samefile(runtime/'data/ui/image/statusbar.tga'))
 def test_hash_guard_and_copy_fallback_preserve_original(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);original=root/'original';asset=original/'data/test.tga';asset.parent.mkdir(parents=True);asset.write_bytes(fixture())
   with patch('legacy_graphics_assets.KNOWN_PALETTES',{'test.tga':'0'*64}):
    with self.assertRaises(ValueError):prepare_render_client(original,root/'runtime',root/'proof.json')
    self.assertFalse((root/'runtime').exists())
   with patch('legacy_graphics_assets.KNOWN_PALETTES',{'test.tga':hashlib.sha256(fixture()).hexdigest()}),patch('legacy_graphics_assets.os.link',side_effect=OSError):
    runtime=prepare_render_client(original,root/'runtime',root/'proof.json')
   self.assertEqual(asset.read_bytes(),fixture());self.assertNotEqual((runtime/'data/test.tga').read_bytes(),fixture())

if __name__=='__main__':unittest.main()
