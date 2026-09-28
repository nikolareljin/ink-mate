from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import socket
import time
import logging


DISCOVERY_PORT = 37653
DISCOVERY_PREFIX = "INKMATE/1 DISCOVER"
logger = logging.getLogger(__name__)


def gateway_address(client_ip: str, gateway_port: int, bind_address: str = "") -> str:
    """Use the selected LAN address, or derive a route when none was selected."""
    if bind_address and bind_address != "0.0.0.0":
        return f"http://{bind_address}:{gateway_port}"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect((client_ip, 9))
        host = probe.getsockname()[0]
    return f"http://{host}:{gateway_port}"


def discovery_reply(
    message: bytes,
    client_ip: str,
    devices: dict[str, str],
    gateway_port: int,
    bind_address: str = "",
    gateway_network: str = "",
    now: int | None = None,
) -> bytes | None:
    try:
        prefix, device_id, nonce = message.decode("ascii").strip().rsplit(" ", 2)
    except UnicodeDecodeError:
        return None
    except ValueError:
        return None
    if prefix != DISCOVERY_PREFIX or len(nonce) != 32 or any(char not in "0123456789abcdef" for char in nonce):
        return None
    secret = devices.get(device_id)
    if not secret:
        return None
    if gateway_network:
        try:
            network = ipaddress.ip_network(gateway_network, strict=False)
            if ipaddress.ip_address(client_ip) not in network:
                return None
        except ValueError:
            return None
    url = gateway_address(client_ip, gateway_port, bind_address)
    timestamp = int(time.time()) if now is None else now
    canonical = f"DISCOVER\n{nonce}\n{url}\n{timestamp}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()
    return f"INKMATE/1 GATEWAY {nonce} {url} {timestamp} {signature}".encode("ascii")


class GatewayDiscovery(asyncio.DatagramProtocol):
    def __init__(
        self, devices: dict[str, str], gateway_port: int, bind_address: str = "", gateway_network: str = ""
    ):
        self.devices = devices
        self.gateway_port = gateway_port
        self.bind_address = bind_address
        self.gateway_network = gateway_network
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, address: tuple[str, int]) -> None:
        logger.warning("received gateway discovery datagram")
        reply = discovery_reply(
            data, address[0], self.devices, self.gateway_port, self.bind_address, self.gateway_network
        )
        if reply is None:
            logger.warning("ignored gateway discovery datagram")
        elif self.transport is not None:
            self.transport.sendto(reply, address)
            logger.warning("replied to authenticated gateway discovery")


async def start_discovery(
    devices: dict[str, str],
    port: int,
    gateway_port: int,
    bind_address: str = "",
    gateway_network: str = "",
) -> asyncio.DatagramTransport:
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: GatewayDiscovery(devices, gateway_port, bind_address, gateway_network),
        local_addr=("0.0.0.0", port),
        allow_broadcast=True,
    )
    return transport
