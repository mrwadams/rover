#!/usr/bin/env python3
"""
Interactive keyboard control for the rover over SSH.

Controls:
    W / Up Arrow    - Forward
    S / Down Arrow  - Backward
    A / Left Arrow  - Turn left
    D / Right Arrow - Turn right
    + / =           - Increase speed
    - / _           - Decrease speed
    Space           - Stop
    Q               - Quit
"""

import sys
import tty
import termios
from rover import Rover


def getch():
    """Read a single character from stdin without echo."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        # Handle arrow keys (escape sequences)
        if ch == '\x1b':
            ch += sys.stdin.read(2)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


def main():
    rover = Rover()
    speed = 50

    print(__doc__)
    print(f"Current speed: {speed}%")
    print("Ready for input...\n")

    try:
        while True:
            key = getch()

            if key in ('q', 'Q'):
                print("\nQuitting...")
                break
            elif key in ('w', 'W', '\x1b[A'):  # W or Up arrow
                print(f"Forward ({speed}%)")
                rover.forward(speed)
            elif key in ('s', 'S', '\x1b[B'):  # S or Down arrow
                print(f"Backward ({speed}%)")
                rover.backward(speed)
            elif key in ('a', 'A', '\x1b[D'):  # A or Left arrow
                print(f"Left ({speed}%)")
                rover.left(speed)
            elif key in ('d', 'D', '\x1b[C'):  # D or Right arrow
                print(f"Right ({speed}%)")
                rover.right(speed)
            elif key == ' ':
                print("Stop")
                rover.stop()
            elif key in ('+', '='):
                speed = min(100, speed + 10)
                print(f"Speed: {speed}%")
            elif key in ('-', '_'):
                speed = max(10, speed - 10)
                print(f"Speed: {speed}%")

    finally:
        rover.stop()
        print("Motors stopped.")


if __name__ == '__main__':
    main()
