# Rover

Control scripts for a Raspberry Pi rover using the Waveshare Motor Driver HAT.

## Hardware

- Raspberry Pi
- Waveshare Motor Driver HAT (PCA9685-based)
- Two DC motors (differential drive)

## Usage

### Basic Control (Python)

```python
from rover import Rover
import time

rover = Rover()
rover.forward(50)    # 50% speed
time.sleep(1)
rover.stop()
```

### Interactive Keyboard Control

For real-time control over SSH:

```bash
python3 rover_keyboard.py
```

Controls:
- **W / ↑** - Forward
- **S / ↓** - Backward
- **A / ←** - Turn left
- **D / →** - Turn right
- **Space** - Stop
- **+/-** - Adjust speed
- **Q** - Quit

## API

### Rover class

| Method | Description |
|--------|-------------|
| `forward(speed)` | Drive forward |
| `backward(speed)` | Drive backward |
| `left(speed)` | Pivot turn left |
| `right(speed)` | Pivot turn right |
| `stop()` | Stop both motors |
| `set_speed(speed)` | Set default speed (0-100) |

All movement methods accept an optional `speed` parameter (0-100). If omitted, uses the default speed (50).
