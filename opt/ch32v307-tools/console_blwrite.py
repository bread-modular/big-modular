#!/usr/bin/env python3
"""Send a bootloader image to a running firmware's CDC console (`blwrite`).

Usage: console_blwrite.py /dev/ttyACMn bootloader.bin

Protocol (firmware side: the module's console `blwrite`):
  host: "blwrite <bytes> <crc32 hex>\\r"   firmware: "blwrite: send <bytes>"
  host: <bytes> raw bytes                  firmware: "blwrite: OK ..." / "blwrite: FAIL ..."
The firmware writes the image only when the CRC-32 (zlib) matches, then reads
it back; after "OK" this sends `reboot`, so the new bootloader starts the
firmware again. Standard library only; the port is opened at 115200 baud (1200 baud
would restart the firmware into its DFU bootloader on close).
"""
import os
import select
import sys
import termios
import time
import zlib


def read_until(fd, tokens, timeout):
    buf = b""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        ready, _, _ = select.select([fd], [], [], 0.1)
        if ready:
            buf += os.read(fd, 4096)
            for token in tokens:
                if token in buf:
                    return buf, token
    return buf, None


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    tty, path = sys.argv[1], sys.argv[2]
    with open(path, "rb") as f:
        image = f.read()
    crc = zlib.crc32(image) & 0xFFFFFFFF

    fd = os.open(tty, os.O_RDWR | os.O_NOCTTY)
    try:
        attrs = termios.tcgetattr(fd)
        attrs[0] = 0                                   # iflag: raw
        attrs[1] = 0                                   # oflag
        attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        attrs[3] = 0                                   # lflag: no echo / canonical
        attrs[4] = attrs[5] = termios.B115200
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        time.sleep(0.2)
        os.write(fd, b"\r")
        read_until(fd, [], 0.5)                        # banner + prompt
        termios.tcflush(fd, termios.TCIFLUSH)

        os.write(fd, b"blwrite %d %08x\r" % (len(image), crc))
        out, tok = read_until(fd, [b"blwrite: send", b"blwrite: size"], 3)
        if tok != b"blwrite: send":
            sys.exit("no blwrite answer (old firmware?): " + out.decode(errors="replace").strip())
        time.sleep(0.05)
        for off in range(0, len(image), 512):
            os.write(fd, image[off:off + 512])
        out, tok = read_until(fd, [b"blwrite: OK", b"blwrite: FAIL"], 20)
        if tok:
            out += read_until(fd, [b"\n"], 0.5)[0]   # rest of the result line
        text = out[out.rfind(tok):].split(b"\r")[0].decode(errors="replace") if tok else "no answer after the image"
        if tok != b"blwrite: OK":
            sys.exit(text)
        print(text)
        # Reboot while the port is open (the console ignores input once DTR drops).
        os.write(fd, b"reboot\r")
        read_until(fd, [b"rebooting"], 1)
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
