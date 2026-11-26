"""Printed pressure screw and matching side-printed tap, shared by the desk mounts.

Right hand; Z is the screw axis. `roof_side` is the sign of Y pointing UP on
that part's print bed, not the side of the desk on which the bore sits.
"""
import math

import build_desk_cable_holder as h

R = dict(r=7.5, depth=1.4, pitch=4., crest=0.65)
CLR, KH, KR, TIP, FACE = .4, 7., 11.8, 68., 5.75
TIP_RUNOUT = 3.7


def tap(body, x, y, bottom, top, roof_side):
    assert roof_side in (-1, 1)
    s = h.tapped(body, R, CLR, bottom, top, x, y, ends=(True, False))
    # 45-degree gable over the horizontal bore: no support trapped in the thread.
    q = (R['r'] + CLR + .15) / math.sqrt(2)
    roof = h.prism([(x-q, y+roof_side*q), (x, y+roof_side*2*q),
                    (x+q, y+roof_side*q)], bottom-1, top+1)
    return h.one(s.cut(roof), 'hand-threaded jaw')


def screw(height=TIP):
    """Default is the released cable-holder screw. Only length varies."""
    root = R['r'] - R['depth']
    rod = h.thread_rod(R, KH-.7, height-1.5)
    taper = h.rev([(0, KH-1), (R['r']+.5, KH-1), (R['r']+.5, height-TIP_RUNOUT),
                   (root-.12, height-1.5), (0, height-1.5)])
    tip = h.rev([(0, height-2.5), (root-.2, height-2.5), (root-.2, height-.35),
                 (FACE, height), (0, height)])
    return h.one(h.lobed(KR, KH, 6, 3.8, .75).fuse(rod.common(taper, h.FZ), h.FZ)
                 .fuse(tip, h.FZ), 'hand screw')
