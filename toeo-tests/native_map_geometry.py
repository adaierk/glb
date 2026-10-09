"""Staggered diamond grid used by original 413BD0 / 413D10 (64 x 32 map)."""
import math

def point_to_grid(position):
    x,y=position
    if not math.isfinite(x) or not math.isfinite(y):raise ValueError('Non-finite map position')
    bx,by=math.trunc(x/64),math.trunc(y/32)
    rx,ry=math.trunc(x)-bx*64,math.trunc(y)-by*32
    dx=dy=0
    if rx<32:
        if ry<16 and ry<16-rx*.5:dx=dy=-1
        elif ry>=16 and ry>=16+rx*.5:dx,dy=-1,1
    elif ry<16 and ry<(rx-32)*.5:dx,dy=1,-1
    elif ry>=16 and ry>=32-(rx-32)*.5:dx=dy=1
    return bx*2+dx,by*2+dy

def grid_to_point(grid):
    x,y=grid
    if y&1:return (math.trunc(x/2)+1)*64.,(math.trunc(y/2)+1)*32.
    return math.trunc(x/2)*64.+32.,math.trunc(y/2)*32.+16.
