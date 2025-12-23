#!/usr/bin/env python3
"""
Web-based rover control server.

Launches a web server that provides a browser-based interface to control the rover.
Access the control page at http://<raspberry-pi-ip>:8080
"""

import sys
sys.path.insert(0, '/home/edith/bcm2835-1.70/Motor_Driver_HAT_Code/Motor_Driver_HAT_Code/Raspberry Pi/python')

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import signal
from rover import Rover

# HTML page with embedded CSS and JavaScript
HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Rover Control</title>
    <style>
        * {
            box-sizing: border-box;
            touch-action: manipulation;
            -webkit-touch-callout: none;
            -webkit-user-select: none;
            user-select: none;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1025;
            color: #eee;
            margin: 0;
            padding: 20px;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        h1 {
            margin: 0 0 20px 0;
            font-size: 24px;
            color: #a855f7;
        }
        .status {
            background: #2d1f3d;
            padding: 10px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
        }
        .status.connected { border-left: 4px solid #00ff88; }
        .status.error { border-left: 4px solid #ff4757; }

        .controls {
            display: grid;
            grid-template-columns: repeat(3, 80px);
            grid-template-rows: repeat(3, 80px);
            gap: 10px;
            margin-bottom: 30px;
        }
        .btn {
            background: #3b1f5c;
            border: 2px solid #a855f7;
            border-radius: 12px;
            color: #a855f7;
            font-size: 28px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.1s;
        }
        .btn:hover {
            background: #4c2875;
        }
        .btn:active, .btn.active {
            background: #a855f7;
            color: #1a1025;
            transform: scale(0.95);
        }
        .btn.stop {
            background: #4a1a1a;
            border-color: #ff4757;
            color: #ff4757;
            font-size: 14px;
            font-weight: bold;
        }
        .btn.stop:active, .btn.stop.active {
            background: #ff4757;
            color: #1a1a2e;
        }

        .speed-control {
            background: #2d1f3d;
            padding: 20px;
            border-radius: 12px;
            width: 100%;
            max-width: 280px;
        }
        .speed-control label {
            display: block;
            margin-bottom: 10px;
            font-size: 14px;
        }
        .speed-value {
            color: #a855f7;
            font-weight: bold;
            font-size: 18px;
        }
        input[type="range"] {
            width: 100%;
            height: 30px;
            -webkit-appearance: none;
            background: transparent;
        }
        input[type="range"]::-webkit-slider-runnable-track {
            height: 8px;
            background: #3b1f5c;
            border-radius: 4px;
        }
        input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 28px;
            height: 28px;
            background: #a855f7;
            border-radius: 50%;
            margin-top: -10px;
            cursor: pointer;
        }
        input[type="range"]::-moz-range-track {
            height: 8px;
            background: #3b1f5c;
            border-radius: 4px;
        }
        input[type="range"]::-moz-range-thumb {
            width: 28px;
            height: 28px;
            background: #a855f7;
            border-radius: 50%;
            border: none;
            cursor: pointer;
        }

        .keyboard-hint {
            margin-top: 20px;
            font-size: 12px;
            color: #666;
            text-align: center;
        }

        /* Landscape layout for mobile */
        @media screen and (max-height: 500px) and (orientation: landscape) {
            body {
                padding: 10px 20px;
                flex-direction: row;
                justify-content: center;
                gap: 40px;
                min-height: 100vh;
            }
            h1 {
                display: none;
            }
            .status {
                position: absolute;
                top: 10px;
                left: 50%;
                transform: translateX(-50%);
                margin: 0;
                padding: 5px 15px;
                font-size: 12px;
            }
            .controls {
                margin: 0;
                grid-template-columns: repeat(3, 70px);
                grid-template-rows: repeat(3, 70px);
                gap: 8px;
            }
            .btn {
                font-size: 24px;
            }
            .speed-control {
                display: flex;
                flex-direction: column;
                justify-content: center;
                padding: 15px;
                width: 180px;
                height: auto;
            }
            .speed-control label {
                margin-bottom: 8px;
            }
            input[type="range"] {
                height: 40px;
            }
            input[type="range"]::-webkit-slider-thumb {
                width: 36px;
                height: 36px;
                margin-top: -14px;
            }
            input[type="range"]::-moz-range-thumb {
                width: 36px;
                height: 36px;
            }
            .keyboard-hint {
                display: none;
            }
        }

        /* Even smaller landscape screens */
        @media screen and (max-height: 400px) and (orientation: landscape) {
            body {
                gap: 30px;
            }
            .controls {
                grid-template-columns: repeat(3, 60px);
                grid-template-rows: repeat(3, 60px);
                gap: 6px;
            }
            .btn {
                font-size: 20px;
                border-radius: 10px;
            }
            .btn.stop {
                font-size: 11px;
            }
            .speed-control {
                width: 150px;
                padding: 10px;
            }
        }
    </style>
</head>
<body>
    <h1>Rover Control</h1>

    <div class="status connected" id="status">Connected</div>

    <div class="controls">
        <div></div>
        <button class="btn" id="btn-forward">&#9650;</button>
        <div></div>

        <button class="btn" id="btn-left">&#9664;</button>
        <button class="btn stop" id="btn-stop">STOP</button>
        <button class="btn" id="btn-right">&#9654;</button>

        <div></div>
        <button class="btn" id="btn-backward">&#9660;</button>
        <div></div>
    </div>

    <div class="speed-control">
        <label>Speed: <span class="speed-value" id="speed-value">50</span>%</label>
        <input type="range" id="speed" min="0" max="100" value="50">
    </div>

    <div class="keyboard-hint">
        Keyboard: Arrow keys or WASD to move, Space to stop
    </div>

    <script>
        const status = document.getElementById('status');
        const speedSlider = document.getElementById('speed');
        const speedValue = document.getElementById('speed-value');

        let currentCommand = null;

        async function sendCommand(command) {
            try {
                const speed = speedSlider.value;
                const response = await fetch('/api/control', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command, speed: parseInt(speed) })
                });
                const data = await response.json();
                if (data.status === 'ok') {
                    status.textContent = command === 'stop' ? 'Stopped' : `Moving: ${command}`;
                    status.className = 'status connected';
                } else {
                    status.textContent = 'Error: ' + data.error;
                    status.className = 'status error';
                }
            } catch (e) {
                status.textContent = 'Connection error';
                status.className = 'status error';
            }
        }

        function startCommand(command) {
            if (currentCommand !== command) {
                currentCommand = command;
                sendCommand(command);
            }
        }

        function stopCommand() {
            if (currentCommand !== null && currentCommand !== 'stop') {
                currentCommand = 'stop';
                sendCommand('stop');
            }
        }

        // Button event handlers (mouse and touch)
        const buttons = {
            'btn-forward': 'forward',
            'btn-backward': 'backward',
            'btn-left': 'left',
            'btn-right': 'right',
            'btn-stop': 'stop'
        };

        Object.entries(buttons).forEach(([id, command]) => {
            const btn = document.getElementById(id);

            // Mouse events
            btn.addEventListener('mousedown', (e) => {
                e.preventDefault();
                btn.classList.add('active');
                if (command === 'stop') {
                    sendCommand('stop');
                    currentCommand = 'stop';
                } else {
                    startCommand(command);
                }
            });

            btn.addEventListener('mouseup', (e) => {
                e.preventDefault();
                btn.classList.remove('active');
                if (command !== 'stop') {
                    stopCommand();
                }
            });

            btn.addEventListener('mouseleave', (e) => {
                btn.classList.remove('active');
                if (command !== 'stop' && currentCommand === command) {
                    stopCommand();
                }
            });

            // Touch events
            btn.addEventListener('touchstart', (e) => {
                e.preventDefault();
                btn.classList.add('active');
                if (command === 'stop') {
                    sendCommand('stop');
                    currentCommand = 'stop';
                } else {
                    startCommand(command);
                }
            });

            btn.addEventListener('touchend', (e) => {
                e.preventDefault();
                btn.classList.remove('active');
                if (command !== 'stop') {
                    stopCommand();
                }
            });
        });

        // Keyboard controls
        const keyMap = {
            'ArrowUp': 'forward',
            'ArrowDown': 'backward',
            'ArrowLeft': 'left',
            'ArrowRight': 'right',
            'w': 'forward',
            'W': 'forward',
            's': 'backward',
            'S': 'backward',
            'a': 'left',
            'A': 'left',
            'd': 'right',
            'D': 'right',
            ' ': 'stop'
        };

        const activeKeys = new Set();

        document.addEventListener('keydown', (e) => {
            if (keyMap[e.key] && !activeKeys.has(e.key)) {
                e.preventDefault();
                activeKeys.add(e.key);
                const command = keyMap[e.key];
                const btnId = 'btn-' + command;
                const btn = document.getElementById(btnId);
                if (btn) btn.classList.add('active');

                if (command === 'stop') {
                    sendCommand('stop');
                    currentCommand = 'stop';
                } else {
                    startCommand(command);
                }
            }
        });

        document.addEventListener('keyup', (e) => {
            if (keyMap[e.key]) {
                activeKeys.delete(e.key);
                const command = keyMap[e.key];
                const btnId = 'btn-' + command;
                const btn = document.getElementById(btnId);
                if (btn) btn.classList.remove('active');

                if (command !== 'stop') {
                    stopCommand();
                }
            }
        });

        // Speed slider
        speedSlider.addEventListener('input', () => {
            speedValue.textContent = speedSlider.value;
        });

        speedSlider.addEventListener('change', () => {
            fetch('/api/speed', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ speed: parseInt(speedSlider.value) })
            });
        });
    </script>
</body>
</html>
"""


class RoverHandler(BaseHTTPRequestHandler):
    """HTTP request handler for rover control."""

    rover = None  # Class-level rover instance

    def log_message(self, format, *args):
        """Custom log format."""
        print(f"[{self.log_date_time_string()}] {args[0]}")

    def send_json(self, data, status=200):
        """Send a JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        """Handle POST requests."""
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self.send_json({'status': 'error', 'error': 'Invalid JSON'}, 400)
            return

        if self.path == '/api/control':
            command = data.get('command')
            speed = data.get('speed')

            if command not in ('forward', 'backward', 'left', 'right', 'stop'):
                self.send_json({'status': 'error', 'error': 'Invalid command'}, 400)
                return

            try:
                if command == 'stop':
                    self.rover.stop()
                elif command == 'forward':
                    self.rover.forward(speed)
                elif command == 'backward':
                    self.rover.backward(speed)
                elif command == 'left':
                    self.rover.left(speed)
                elif command == 'right':
                    self.rover.right(speed)

                self.send_json({'status': 'ok', 'command': command})
            except Exception as e:
                self.send_json({'status': 'error', 'error': str(e)}, 500)

        elif self.path == '/api/speed':
            speed = data.get('speed')
            if speed is not None:
                self.rover.set_speed(speed)
                self.send_json({'status': 'ok', 'speed': speed})
            else:
                self.send_json({'status': 'error', 'error': 'Missing speed'}, 400)

        else:
            self.send_json({'status': 'error', 'error': 'Not found'}, 404)

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


def main():
    """Start the web server."""
    port = 8080

    # Initialize rover
    print("Initializing rover...")
    rover = Rover()
    RoverHandler.rover = rover

    # Setup signal handlers for clean shutdown
    def shutdown(signum, frame):
        print("\nShutting down...")
        rover.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Start server
    server = HTTPServer(('0.0.0.0', port), RoverHandler)
    print(f"Rover web control running at http://0.0.0.0:{port}")
    print("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    finally:
        rover.stop()


if __name__ == '__main__':
    main()
