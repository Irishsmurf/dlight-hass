"""Fake dLight TCP Server with Chaos Injection.

This script simulates a dLight lamp and allows for manual injection of network
faults to test the robustness of the Home Assistant integration.
"""
import asyncio
import json
import logging
import random
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
_LOGGER = logging.getLogger(__name__)

class FakeLamp:
    def __init__(self):
        self.on = False
        self.brightness = 100
        self.temperature = 3000
        self.device_id = "dlight_fake_1"
        
        # Chaos Flags
        self.chaos_delay = 0  # Seconds to sleep before responding
        self.chaos_reset = False  # Reset connection mid-flight
        self.chaos_hang = False  # Accept connection but never respond
        self.chaos_error_rate = 0.0  # Probability of sending invalid JSON

    def get_state(self):
        return {
            "status": "SUCCESS",
            "on": self.on,
            "brightness": self.brightness,
            "color": {"temperature": self.temperature}
        }

    def get_info(self):
        return {
            "status": "SUCCESS",
            "deviceModel": "Fake-Lamp-Pro",
            "swVersion": "2.0.1-chaos",
            "hwVersion": "1.0.0"
        }

    async def handle_client(self, reader, writer):
        addr = writer.get_extra_info('peername')
        _LOGGER.info("Connection from %s", addr)

        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                
                if self.chaos_hang:
                    _LOGGER.warning("Chaos: Hanging connection from %s", addr)
                    return # Just leave it open or let it timeout

                if self.chaos_delay > 0:
                    _LOGGER.info("Chaos: Delaying response by %ds", self.chaos_delay)
                    await asyncio.sleep(self.chaos_delay)

                if self.chaos_reset:
                    _LOGGER.warning("Chaos: Resetting connection to %s", addr)
                    writer.close()
                    await writer.wait_closed()
                    return

                try:
                    request = json.loads(data.decode())
                    _LOGGER.info("Received: %s", request)
                    
                    method = request.get("method")
                    params = request.get("params", {})
                    
                    response = {"status": "ERROR", "message": "Unknown method"}
                    
                    if method == "get_state":
                        response = self.get_state()
                    elif method == "get_info":
                        response = self.get_info()
                    elif method == "turn_on":
                        self.on = True
                        response = {"status": "SUCCESS"}
                    elif method == "turn_off":
                        self.on = False
                        response = {"status": "SUCCESS"}
                    elif method == "set_brightness":
                        self.brightness = params.get("brightness", self.brightness)
                        response = {"status": "SUCCESS"}
                    elif method == "set_color_temperature":
                        self.temperature = params.get("temperature", self.temperature)
                        response = {"status": "SUCCESS"}

                    if random.random() < self.chaos_error_rate:
                        _LOGGER.warning("Chaos: Injecting invalid JSON error")
                        payload = b"NOT_JSON_DATA"
                    else:
                        payload = json.dumps(response).encode()

                    writer.write(payload)
                    await writer.drain()
                    
                except json.JSONDecodeError:
                    _LOGGER.error("Invalid JSON received")
                    writer.write(b'{"status": "ERROR", "message": "Invalid JSON"}')
                    await writer.drain()

        except asyncio.CancelledError:
            pass
        except Exception as err:
            _LOGGER.error("Error handling client %s: %s", addr, err)
        finally:
            _LOGGER.info("Closing connection from %s", addr)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

async def main():
    lamp = FakeLamp()
    server = await asyncio.start_server(lamp.handle_client, '127.0.0.1', 8888)

    addr = server.sockets[0].getsockname()
    _LOGGER.info("Serving dLight on %s", addr)
    _LOGGER.info("Controls: set lamp.chaos_delay, lamp.chaos_reset, etc. via debugger or signal handlers.")

    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
