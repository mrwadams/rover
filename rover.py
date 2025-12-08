#!/usr/bin/env python3
"""
Rover control script for Raspberry Pi with Motor Driver HAT
"""

import sys
sys.path.insert(0, '/home/edith/bcm2835-1.70/Motor_Driver_HAT_Code/Motor_Driver_HAT_Code/Raspberry Pi/python')

from PCA9685 import PCA9685
import time

class Rover:
    """
    A class to control a two-wheeled rover using the Waveshare Motor Driver HAT.

    The rover uses a PCA9685 PWM controller to drive two DC motors (left and right).
    Movement is achieved through differential drive - varying the speed and direction
    of each motor independently.

    Attributes:
        speed (int): Default speed for movements (0-100). Defaults to 50.

    Hardware Setup:
        - Motor A (left):  PWM on channel 0, direction on channels 1 & 2
        - Motor B (right): PWM on channel 5, direction on channels 3 & 4
        - I2C address: 0x40

    Example:
        >>> from rover import Rover
        >>> import time
        >>>
        >>> rover = Rover()
        >>> rover.forward(75)      # Drive forward at 75% speed
        >>> time.sleep(2)
        >>> rover.left(50)         # Pivot turn left
        >>> time.sleep(0.5)
        >>> rover.stop()           # Always stop when done
    """

    def __init__(self):
        self.pwm = PCA9685(0x40, debug=False)
        self.pwm.setPWMFreq(50)

        # Motor A (left) channels
        self.PWMA = 0
        self.AIN1 = 1
        self.AIN2 = 2

        # Motor B (right) channels
        self.PWMB = 5
        self.BIN1 = 3
        self.BIN2 = 4

        self.speed = 50  # Default speed (0-100)

    def _motor(self, motor, direction, speed):
        """Control individual motor. motor: 'left' or 'right', direction: 'forward' or 'backward'"""
        speed = max(0, min(100, speed))

        if motor == 'left':
            self.pwm.setDutycycle(self.PWMA, speed)
            if direction == 'forward':
                self.pwm.setLevel(self.AIN1, 0)
                self.pwm.setLevel(self.AIN2, 1)
            else:
                self.pwm.setLevel(self.AIN1, 1)
                self.pwm.setLevel(self.AIN2, 0)
        else:  # right (reversed - motor is mirrored on chassis)
            self.pwm.setDutycycle(self.PWMB, speed)
            if direction == 'forward':
                self.pwm.setLevel(self.BIN1, 1)
                self.pwm.setLevel(self.BIN2, 0)
            else:
                self.pwm.setLevel(self.BIN1, 0)
                self.pwm.setLevel(self.BIN2, 1)

    def forward(self, speed=None):
        """
        Drive the rover forward.

        Args:
            speed (int, optional): Motor speed from 0-100. Uses default speed if not specified.
        """
        speed = speed or self.speed
        self._motor('left', 'forward', speed)
        self._motor('right', 'forward', speed)

    def backward(self, speed=None):
        """
        Drive the rover backward.

        Args:
            speed (int, optional): Motor speed from 0-100. Uses default speed if not specified.
        """
        speed = speed or self.speed
        self._motor('left', 'backward', speed)
        self._motor('right', 'backward', speed)

    def left(self, speed=None):
        """
        Pivot turn left (rotate in place).

        Turns by running the right motor forward and left motor backward,
        causing the rover to rotate counter-clockwise.

        Args:
            speed (int, optional): Motor speed from 0-100. Uses default speed if not specified.
        """
        speed = speed or self.speed
        self._motor('left', 'backward', speed)
        self._motor('right', 'forward', speed)

    def right(self, speed=None):
        """
        Pivot turn right (rotate in place).

        Turns by running the left motor forward and right motor backward,
        causing the rover to rotate clockwise.

        Args:
            speed (int, optional): Motor speed from 0-100. Uses default speed if not specified.
        """
        speed = speed or self.speed
        self._motor('left', 'forward', speed)
        self._motor('right', 'backward', speed)

    def stop(self):
        """
        Stop both motors immediately.

        Sets PWM duty cycle to 0 for both motors. Should always be called
        when done controlling the rover to prevent runaway movement.
        """
        self.pwm.setDutycycle(self.PWMA, 0)
        self.pwm.setDutycycle(self.PWMB, 0)

    def set_speed(self, speed):
        """
        Set the default speed for all movements.

        Args:
            speed (int): Speed value from 0-100. Values outside this range
                will be clamped.
        """
        self.speed = max(0, min(100, speed))


if __name__ == '__main__':
    rover = Rover()

    try:
        print("Forward...")
        rover.forward(50)
        time.sleep(1)

        print("Backward...")
        rover.backward(50)
        time.sleep(1)

        print("Left...")
        rover.left(50)
        time.sleep(0.5)

        print("Right...")
        rover.right(50)
        time.sleep(0.5)

    finally:
        print("Stopping")
        rover.stop()
