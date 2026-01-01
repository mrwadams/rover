#!/usr/bin/env python3
"""
Web-based rover control server.

Launches a web server that provides a browser-based interface to control the rover.
Access the control page at http://<raspberry-pi-ip>:8080
"""

import sys
sys.path.insert(0, '/home/edith/bcm2835-1.70/Motor_Driver_HAT_Code/Motor_Driver_HAT_Code/Raspberry Pi/python')

from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from threading import Condition
import json
import signal
import io
import os
from rover import Rover

from google import genai
from google.genai import types
from dotenv import load_dotenv


from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput
import libcamera

import pygame
import numpy as np


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTP server that handles each request in a separate thread."""
    daemon_threads = True


class StreamingOutput(io.BufferedIOBase):
    """Thread-safe output buffer for MJPEG streaming."""

    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()
        return len(buf)


class ReversingSound:
    """Manages the vehicle reversing beep sound."""

    def __init__(self):
        # Initialize pygame mixer for audio output
        # Using hw:2,0 (the 3.5mm jack) - set via environment before init
        os.environ['SDL_AUDIODRIVER'] = 'alsa'
        os.environ['AUDIODEV'] = 'hw:2,0'
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

        # Generate the reversing beep sound
        self.beep_sound = self._generate_beep()
        self.is_playing = False

    def _generate_beep(self):
        """Generate a classic reversing beep pattern (beep-silence-beep-silence...)"""
        sample_rate = 44100
        beep_freq = 1000  # 1kHz tone
        beep_duration = 0.3  # 300ms beep
        silence_duration = 0.3  # 300ms silence

        # Generate one beep cycle (beep + silence)
        beep_samples = int(sample_rate * beep_duration)
        silence_samples = int(sample_rate * silence_duration)
        total_samples = beep_samples + silence_samples

        # Create time array for the beep portion
        t = np.linspace(0, beep_duration, beep_samples, dtype=np.float32)

        # Generate sine wave for beep
        beep = np.sin(2 * np.pi * beep_freq * t)

        # Apply fade in/out to avoid clicks (20ms fade)
        fade_samples = int(sample_rate * 0.02)
        fade_in = np.linspace(0, 1, fade_samples, dtype=np.float32)
        fade_out = np.linspace(1, 0, fade_samples, dtype=np.float32)
        beep[:fade_samples] *= fade_in
        beep[-fade_samples:] *= fade_out

        # Create silence
        silence = np.zeros(silence_samples, dtype=np.float32)

        # Combine beep and silence
        mono = np.concatenate([beep, silence])

        # Create stereo array: silent left channel, beep on right channel
        stereo = np.zeros((total_samples, 2), dtype=np.float32)
        stereo[:, 1] = mono  # Right channel only

        # Convert to 16-bit integers and scale
        stereo_int = (stereo * 32767).astype(np.int16)

        # Create pygame sound from the array
        sound = pygame.sndarray.make_sound(stereo_int)
        return sound

    def start(self):
        """Start playing the reversing beep in a loop."""
        if not self.is_playing:
            self.beep_sound.play(loops=-1)  # -1 = infinite loop
            self.is_playing = True

    def stop(self):
        """Stop the reversing beep."""
        if self.is_playing:
            self.beep_sound.stop()
            self.is_playing = False

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

        .video-container {
            background: #2d1f3d;
            border-radius: 12px;
            padding: 8px;
            margin-bottom: 20px;
            max-width: 400px;
            width: 100%;
        }
        .video-container img {
            width: 100%;
            border-radius: 8px;
            display: block;
        }

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

        .vision-btn {
            background: #1e3a5f;
            border: 2px solid #3b82f6;
            color: #3b82f6;
            padding: 12px 24px;
            font-size: 14px;
            margin-bottom: 20px;
            width: 100%;
            max-width: 400px;
        }
        .vision-btn:hover { background: #234b7a; }
        .vision-btn:active, .vision-btn.active {
            background: #3b82f6;
            color: #1a1025;
        }
        .vision-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .vision-result {
            background: #2d1f3d;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
            max-width: 400px;
            width: 100%;
            min-height: 60px;
            font-size: 14px;
            line-height: 1.5;
            display: none;
        }
        .vision-result.visible { display: block; }

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
                align-items: center;
                gap: 20px;
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
            .video-container {
                margin: 0;
                max-width: none;
                width: auto;
                height: calc(100vh - 40px);
                padding: 6px;
            }
            .video-container img {
                height: 100%;
                width: auto;
            }
            .controls {
                margin: 0;
                grid-template-columns: repeat(3, 60px);
                grid-template-rows: repeat(3, 60px);
                gap: 6px;
            }
            .btn {
                font-size: 22px;
            }
            .speed-control {
                display: flex;
                flex-direction: column;
                justify-content: center;
                padding: 12px;
                width: 100px;
                height: auto;
            }
            .speed-control label {
                margin-bottom: 8px;
                font-size: 12px;
            }
            input[type="range"] {
                height: 40px;
            }
            input[type="range"]::-webkit-slider-thumb {
                width: 32px;
                height: 32px;
                margin-top: -12px;
            }
            input[type="range"]::-moz-range-thumb {
                width: 32px;
                height: 32px;
            }
            .keyboard-hint {
                display: none;
            }
        }

        /* Even smaller landscape screens */
        @media screen and (max-height: 400px) and (orientation: landscape) {
            body {
                gap: 15px;
            }
            .video-container {
                height: calc(100vh - 30px);
                padding: 4px;
            }
            .controls {
                grid-template-columns: repeat(3, 50px);
                grid-template-rows: repeat(3, 50px);
                gap: 4px;
            }
            .btn {
                font-size: 18px;
                border-radius: 8px;
            }
            .btn.stop {
                font-size: 10px;
            }
            .speed-control {
                width: 80px;
                padding: 8px;
            }
        }
    </style>
</head>
<body>
    <h1>Rover Control</h1>

    <div class="status connected" id="status">Connected</div>

    <div class="video-container">
        <img src="/video_feed" alt="Camera feed">
    </div>

    <button class="btn vision-btn" id="btn-vision">Describe Scene</button>
    <div class="vision-result" id="vision-result"></div>

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

        // Vision analysis
        const visionBtn = document.getElementById('btn-vision');
        const visionResult = document.getElementById('vision-result');

        visionBtn.addEventListener('click', async () => {
            visionBtn.disabled = true;
            visionBtn.textContent = 'Analyzing...';
            visionResult.classList.add('visible');
            visionResult.textContent = 'Processing...';

            try {
                const response = await fetch('/api/vision', { method: 'POST' });
                const data = await response.json();
                if (data.status === 'ok') {
                    visionResult.textContent = data.description;
                } else {
                    visionResult.textContent = 'Error: ' + data.error;
                }
            } catch (e) {
                visionResult.textContent = 'Connection error';
            }

            visionBtn.disabled = false;
            visionBtn.textContent = 'Describe Scene';
        });
    </script>
</body>
</html>
"""


class RoverHandler(BaseHTTPRequestHandler):
    """HTTP request handler for rover control."""

    rover = None  # Class-level rover instance
    stream_output = None  # Class-level streaming output
    gemini_client = None  # Class-level Gemini client
    reversing_sound = None  # Class-level reversing sound

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
        elif self.path == '/video_feed':
            self.send_response(200)
            self.send_header('Age', '0')
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with self.stream_output.condition:
                        self.stream_output.condition.wait()
                        frame = self.stream_output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception:
                pass
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
                    if self.reversing_sound:
                        self.reversing_sound.stop()
                elif command == 'forward':
                    self.rover.forward(speed)
                    if self.reversing_sound:
                        self.reversing_sound.stop()
                elif command == 'backward':
                    self.rover.backward(speed)
                    if self.reversing_sound:
                        self.reversing_sound.start()
                elif command == 'left':
                    self.rover.left(speed)
                    if self.reversing_sound:
                        self.reversing_sound.stop()
                elif command == 'right':
                    self.rover.right(speed)
                    if self.reversing_sound:
                        self.reversing_sound.stop()

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

        elif self.path == '/api/vision':
            if not self.gemini_client:
                self.send_json({'status': 'error', 'error': 'Gemini not configured'}, 503)
                return

            # Capture current frame
            with self.stream_output.condition:
                frame = self.stream_output.frame

            if not frame:
                self.send_json({'status': 'error', 'error': 'No frame available'}, 503)
                return

            try:
                # Send to Gemini
                response = self.gemini_client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=[
                        "Describe what you see in this image from a rover's camera. Be concise.",
                        types.Part.from_bytes(data=frame, mime_type='image/jpeg'),
                    ],
                )
                self.send_json({'status': 'ok', 'description': response.text})
            except Exception as e:
                self.send_json({'status': 'error', 'error': str(e)}, 500)

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

    # Initialize reversing sound
    print("Initializing audio...")
    try:
        reversing_sound = ReversingSound()
        RoverHandler.reversing_sound = reversing_sound
        print("Reversing sound enabled")
    except Exception as e:
        print(f"Warning: Audio initialization failed ({e}), reversing sound disabled")
        RoverHandler.reversing_sound = None

    # Initialize camera
    print("Initializing camera...")
    picam2 = Picamera2()
    video_config = picam2.create_video_configuration(main={"size": (640, 480)}, transform=libcamera.Transform(hflip=True, vflip=True))
    picam2.configure(video_config)
    stream_output = StreamingOutput()
    picam2.start_recording(MJPEGEncoder(), FileOutput(stream_output))
    RoverHandler.stream_output = stream_output
    print("Camera streaming started")

    # Load .env file and initialize Gemini
    load_dotenv()
    api_key = os.environ.get('GEMINI_API_KEY')
    if api_key:
        RoverHandler.gemini_client = genai.Client(api_key=api_key)
        print("Gemini vision enabled")
    else:
        RoverHandler.gemini_client = None
        print("Warning: GEMINI_API_KEY not set, vision disabled")

    # Setup signal handlers for clean shutdown
    def shutdown(signum, frame):
        print("\nShutting down...")
        picam2.stop_recording()
        rover.stop()
        if RoverHandler.reversing_sound:
            RoverHandler.reversing_sound.stop()
        pygame.mixer.quit()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Start server
    server = ThreadingHTTPServer(('0.0.0.0', port), RoverHandler)
    print(f"Rover web control running at http://0.0.0.0:{port}")
    print("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    finally:
        picam2.stop_recording()
        rover.stop()
        if RoverHandler.reversing_sound:
            RoverHandler.reversing_sound.stop()
        pygame.mixer.quit()


if __name__ == '__main__':
    main()
