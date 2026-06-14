"""Fake dLight TCP Server with Chaos Injection.

Simulates a dLight lamp and allows injection of network faults for manual
end-to-end testing of the coordinator's resilience without real hardware.

Usage:
  python3 tests/fake_lamp.py [--port PORT] [--drop-rate 0.3] [--error-rate 0.2]
                             [--latency 500] [--latency-spike 5000 0.1]
                             [--disconnect-after N] [--offline-for N]

Runtime commands (typed at the prompt):
  on / off          Toggle lamp state
  bright N          Set brightness (0-100)
  temp N            Set color temperature (Kelvin)
  chaos on/off      Toggle all chaos modes simultaneously
  drop N            Set drop rate (0.0-1.0)
  error N           Set error rate (0.0-1.0)
  latency N         Set base latency in ms (0 to disable)
  spike             Inject a one-shot 10 s latency spike on the next command
  offline N         Go silent for N seconds then come back
  disconnect N      Close connection every N commands (0 to disable)
  status            Show current lamp and chaos state
  quit / exit       Shut down
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
_LOGGER = logging.getLogger(__name__)


class FakeLamp:
    def __init__(
        self,
        *,
        drop_rate: float = 0.0,
        error_rate: float = 0.0,
        latency_ms: int = 0,
        latency_spike_ms: int = 0,
        latency_spike_prob: float = 0.0,
        disconnect_after: int = 0,
        offline_for: int = 0,
    ) -> None:
        # Lamp state
        self.on = False
        self.brightness = 100
        self.temperature = 3000
        self.device_id = "dlight_fake_1"

        # Chaos parameters
        self.drop_rate = drop_rate          # probability of silently dropping a connection
        self.error_rate = error_rate        # probability of sending a protocol error response
        self.latency_ms = latency_ms        # base added latency per response in ms
        self.latency_spike_ms = latency_spike_ms      # spike latency in ms
        self.latency_spike_prob = latency_spike_prob  # probability of a spike

        self.disconnect_after = disconnect_after  # close TCP after every N commands (0=never)
        self.offline_for = offline_for      # go silent for N seconds on startup

        # Runtime chaos state
        self._offline_until: float = 0.0
        self._spike_next: bool = False      # one-shot spike on next command
        self._command_count: int = 0        # per-connection counter

        # Legacy flags kept for backwards compatibility
        self.chaos_delay = 0
        self.chaos_reset = False
        self.chaos_hang = False
        self.chaos_error_rate = 0.0

    # --- State helpers ---

    def get_state(self) -> dict:
        return {
            "status": "SUCCESS",
            "on": self.on,
            "brightness": self.brightness,
            "color": {"temperature": self.temperature},
        }

    def get_info(self) -> dict:
        return {
            "status": "SUCCESS",
            "deviceModel": "Fake-Lamp-Pro",
            "swVersion": "2.0.1-chaos",
            "hwVersion": "1.0.0",
        }

    def print_status(self) -> None:
        print(
            f"\n[lamp] on={self.on} brightness={self.brightness} temp={self.temperature}K\n"
            f"[chaos] drop={self.drop_rate:.0%} error={self.error_rate:.0%} "
            f"latency={self.latency_ms}ms spike={self.latency_spike_ms}ms@{self.latency_spike_prob:.0%} "
            f"disconnect_after={self.disconnect_after} offline_for={self.offline_for}s\n"
        )

    # --- Connection handler ---

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        addr = writer.get_extra_info("peername")

        # Drop connection silently
        if self.drop_rate > 0 and random.random() < self.drop_rate:
            _LOGGER.warning("Chaos: dropping connection from %s (drop_rate=%.0f%%)", addr, self.drop_rate * 100)
            writer.close()
            return

        # Offline window check
        loop = asyncio.get_event_loop()
        now = loop.time()
        if now < self._offline_until:
            remaining = self._offline_until - now
            _LOGGER.warning("Chaos: offline for %.1f more seconds — closing %s", remaining, addr)
            writer.close()
            return

        _LOGGER.info("Connection from %s", addr)
        self._command_count = 0

        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break

                # Legacy hang mode
                if self.chaos_hang:
                    _LOGGER.warning("Chaos: hanging connection from %s", addr)
                    return

                # Legacy reset mode
                if self.chaos_reset:
                    _LOGGER.warning("Chaos: resetting connection to %s", addr)
                    writer.close()
                    await writer.wait_closed()
                    return

                self._command_count += 1

                # Determine latency
                delay_s = self._pick_latency()
                if delay_s > 0:
                    _LOGGER.info("Chaos: adding %.3fs latency for command #%d", delay_s, self._command_count)
                    await asyncio.sleep(delay_s)

                try:
                    request = json.loads(data.decode())
                    _LOGGER.info("Received: %s", request)

                    method = request.get("method")
                    params = request.get("params", {})

                    response = self._dispatch(method, params)

                    # Error injection (overrides real response)
                    effective_error_rate = max(self.error_rate, self.chaos_error_rate)
                    if effective_error_rate > 0 and random.random() < effective_error_rate:
                        _LOGGER.warning("Chaos: injecting error response for method=%s", method)
                        payload = b"NOT_JSON_DATA"
                    else:
                        payload = json.dumps(response).encode()

                    writer.write(payload)
                    await writer.drain()

                except json.JSONDecodeError:
                    _LOGGER.error("Invalid JSON received")
                    writer.write(b'{"status": "ERROR", "message": "Invalid JSON"}')
                    await writer.drain()

                # Disconnect after N commands
                if self.disconnect_after > 0 and self._command_count >= self.disconnect_after:
                    _LOGGER.warning(
                        "Chaos: disconnecting after %d command(s) to force reconnect", self._command_count
                    )
                    break

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

    def _dispatch(self, method: str | None, params: dict) -> dict:
        if method == "get_state":
            return self.get_state()
        if method == "get_info":
            return self.get_info()
        if method == "turn_on":
            self.on = True
            return {"status": "SUCCESS"}
        if method == "turn_off":
            self.on = False
            return {"status": "SUCCESS"}
        if method == "toggle":
            self.on = not self.on
            return {"status": "SUCCESS"}
        if method == "set_brightness":
            self.brightness = params.get("brightness", self.brightness)
            return {"status": "SUCCESS"}
        if method == "set_color_temperature":
            self.temperature = params.get("temperature", self.temperature)
            return {"status": "SUCCESS"}
        if method == "apply_scene":
            if "brightness" in params:
                self.brightness = params["brightness"]
            if "temperature" in params:
                self.temperature = params["temperature"]
            self.on = True
            return {"status": "SUCCESS"}
        if method == "ping":
            return {"status": "SUCCESS"}
        if method == "flash":
            return {"status": "SUCCESS"}
        return {"status": "ERROR", "message": f"Unknown method: {method}"}

    def _pick_latency(self) -> float:
        """Return how long (seconds) to sleep before responding."""
        # One-shot spike requested at the prompt
        if self._spike_next:
            self._spike_next = False
            _LOGGER.info("Chaos: one-shot spike of 10s triggered")
            return 10.0

        # Probabilistic spike
        if self.latency_spike_ms > 0 and random.random() < self.latency_spike_prob:
            return self.latency_spike_ms / 1000.0

        # Legacy delay
        if self.chaos_delay > 0:
            return float(self.chaos_delay)

        return self.latency_ms / 1000.0


# --- Interactive command prompt ---

async def _run_prompt(lamp: FakeLamp) -> None:
    loop = asyncio.get_event_loop()
    while True:
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            break
        cmd = line.strip()
        if not cmd:
            continue

        parts = cmd.split()
        verb = parts[0].lower()

        if verb in ("quit", "exit"):
            print("Shutting down.")
            loop.stop()
            break
        elif verb == "on":
            lamp.on = True
            print(f"[lamp] on=True")
        elif verb == "off":
            lamp.on = False
            print(f"[lamp] on=False")
        elif verb == "bright" and len(parts) == 2:
            lamp.brightness = int(parts[1])
            print(f"[lamp] brightness={lamp.brightness}")
        elif verb == "temp" and len(parts) == 2:
            lamp.temperature = int(parts[1])
            print(f"[lamp] temperature={lamp.temperature}K")
        elif verb == "chaos":
            if len(parts) < 2:
                print("Usage: chaos on|off")
            elif parts[1].lower() == "on":
                lamp.drop_rate = 0.3
                lamp.error_rate = 0.2
                lamp.latency_ms = 200
                lamp.latency_spike_ms = 3000
                lamp.latency_spike_prob = 0.1
                lamp.disconnect_after = 5
                print("[chaos] all chaos modes ON")
            else:
                lamp.drop_rate = 0.0
                lamp.error_rate = 0.0
                lamp.latency_ms = 0
                lamp.latency_spike_ms = 0
                lamp.latency_spike_prob = 0.0
                lamp.disconnect_after = 0
                print("[chaos] all chaos modes OFF")
        elif verb == "drop" and len(parts) == 2:
            lamp.drop_rate = float(parts[1])
            print(f"[chaos] drop_rate={lamp.drop_rate:.0%}")
        elif verb == "error" and len(parts) == 2:
            lamp.error_rate = float(parts[1])
            print(f"[chaos] error_rate={lamp.error_rate:.0%}")
        elif verb == "latency" and len(parts) == 2:
            lamp.latency_ms = int(parts[1])
            print(f"[chaos] latency={lamp.latency_ms}ms")
        elif verb == "spike":
            lamp._spike_next = True
            print("[chaos] one-shot spike armed — next command will be delayed 10s")
        elif verb == "offline" and len(parts) == 2:
            seconds = int(parts[1])
            lamp._offline_until = asyncio.get_event_loop().time() + seconds
            print(f"[chaos] offline for {seconds}s")
        elif verb == "disconnect" and len(parts) == 2:
            lamp.disconnect_after = int(parts[1])
            print(f"[chaos] disconnect_after={lamp.disconnect_after}")
        elif verb == "status":
            lamp.print_status()
        else:
            print(
                "Commands: on | off | bright N | temp N | chaos on/off | drop N | error N\n"
                "          latency N | spike | offline N | disconnect N | status | quit"
            )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Fake dLight lamp for chaos testing")
    parser.add_argument("--port", type=int, default=8888)
    parser.add_argument("--drop-rate", type=float, default=0.0, metavar="PROB",
                        help="Probability [0-1] of silently dropping a connection")
    parser.add_argument("--error-rate", type=float, default=0.0, metavar="PROB",
                        help="Probability [0-1] of returning a protocol error response")
    parser.add_argument("--latency", type=int, default=0, metavar="MS",
                        help="Base latency added to every response (ms)")
    parser.add_argument("--latency-spike", nargs=2, metavar=("MS", "PROB"), default=None,
                        help="Occasional spike: MS duration at PROB probability")
    parser.add_argument("--disconnect-after", type=int, default=0, metavar="N",
                        help="Force TCP disconnect after every N commands")
    parser.add_argument("--offline-for", type=int, default=0, metavar="N",
                        help="Start in offline mode for N seconds")
    args = parser.parse_args()

    spike_ms, spike_prob = 0, 0.0
    if args.latency_spike:
        spike_ms = int(args.latency_spike[0])
        spike_prob = float(args.latency_spike[1])

    lamp = FakeLamp(
        drop_rate=args.drop_rate,
        error_rate=args.error_rate,
        latency_ms=args.latency,
        latency_spike_ms=spike_ms,
        latency_spike_prob=spike_prob,
        disconnect_after=args.disconnect_after,
        offline_for=args.offline_for,
    )

    if args.offline_for:
        lamp._offline_until = asyncio.get_event_loop().time() + args.offline_for
        _LOGGER.info("Starting offline for %ds", args.offline_for)

    server = await asyncio.start_server(lamp.handle_client, "127.0.0.1", args.port)
    addr = server.sockets[0].getsockname()
    _LOGGER.info("Fake dLight listening on %s:%s", *addr)
    lamp.print_status()
    print("Type 'status' for current state, 'quit' to exit.\n")

    async with server:
        await asyncio.gather(
            server.serve_forever(),
            _run_prompt(lamp),
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
