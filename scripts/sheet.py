"""Contact sheet of local test frames: python3 scripts/sheet.py shots/test out.png"""
import sys, glob, os
from PIL import Image, ImageDraw
ds = sorted(glob.glob(sys.argv[1] + '/*/'))
ims = [(os.path.basename(d[:-1]), Image.open(sorted(glob.glob(d + 'f_*.jpg'))[-1]).convert('RGB').resize((180, 320))) for d in ds if glob.glob(d + 'f_*.jpg')]
cols = 6; rows = (len(ims) + cols - 1) // cols
sh = Image.new('RGB', (180 * cols, 320 * rows), 'white'); dr = ImageDraw.Draw(sh)
for i, (n, im) in enumerate(ims):
    sh.paste(im, ((i % cols) * 180, (i // cols) * 320)); dr.text(((i % cols) * 180 + 4, (i // cols) * 320 + 4), n, fill='red')
sh.save(sys.argv[2]); print(len(ims), 'shots')
