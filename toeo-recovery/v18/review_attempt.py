"""Preserve actual failed-run map pixels for reverse-engineering review."""
import json,os
from pathlib import Path
from PIL import Image
root=Path(os.environ['RUNNER_TEMP'])/'TOEO_V18_ATTEMPT1'
out=Path('toeo-recovery/v18/attempt1');out.mkdir(parents=True,exist_ok=True)
for seconds in (140,170,210,230,260):
 p=root/'first'/f'original_desktop_{seconds:03d}s.png'
 Image.open(p).crop((8,32,808,632)).save(out/f'map_{seconds:03d}.png')
result=json.loads((root/'first/runtime_result.json').read_text())
(out/'runtime_result.json').write_text(json.dumps(result,indent=2))
print('FAILED_ATTEMPT_PIXELS_PRESERVED_FOR_REVIEW')
