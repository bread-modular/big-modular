#!/usr/bin/env python3
"""Send commands to the Bread Modular 6x8 console and print the replies.

  tools/console.py status                       # reply until 0.5 s quiet
  tools/console.py "cal out" -u "saved|nothing|FAIL" -w 15
  tools/console.py status cal -p /dev/ttyACM1
"""
import argparse
import glob
import re
import sys
import time

import serial


def find_port():
    ports = sorted(glob.glob("/dev/serial/by-id/*Bread_Modular_6x8*")) or sorted(glob.glob("/dev/ttyACM*"))
    if not ports:
        sys.exit("no console port")
    return ports[0]


def talk(s, cmd, wait=10.0, until=None, quiet=0.5):
    """One command on an open port; the reply ends at `until` (regex), else after
    `quiet` s without data, at most `wait` s."""
    s.write((cmd + "\r").encode())
    buf = b""
    t0 = last = time.time()
    while time.time() - t0 < wait:
        d = s.read(4096)
        now = time.time()
        if d:
            buf += d
            last = now
            if until and re.search(until, buf.decode(errors="replace")):
                time.sleep(0.2)
                buf += s.read(4096)
                break
        elif not until and buf and now - last > quiet:
            break
    return buf.decode(errors="replace").replace("\r", "")


def run(port, cmds, wait=10.0, until=None, quiet=0.5):
    """Opens the port, sends each command (talk()) and closes it again."""
    with serial.Serial(port, 115200, timeout=0.05) as s:
        time.sleep(0.2)
        s.reset_input_buffer()
        return [talk(s, cmd, wait, until, quiet) for cmd in cmds]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmds", nargs="+")
    ap.add_argument("-p", "--port")
    ap.add_argument("-w", "--wait", type=float, default=10.0, help="longest wait per reply, s")
    ap.add_argument("-u", "--until", help="regex that ends a reply")
    a = ap.parse_args()
    for r in run(a.port or find_port(), a.cmds, a.wait, a.until):
        sys.stdout.write(r)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
