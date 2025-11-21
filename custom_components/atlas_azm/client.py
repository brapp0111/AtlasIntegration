"""Atlas AZM4/AZM8 TCP/UDP Client."""
import asyncio
import json
import logging
from typing import Any, Callable, Optional

_LOGGER = logging.getLogger(__name__)


class AtlasAZMClient:
    """Client for Atlas AZM4/AZM8 JSON-RPC 2.0 protocol."""

    def __init__(
        self, 
        host: str, 
        tcp_port: int = 5321, 
        udp_port: int = 3131
    ):
        """Initialize the client."""
        self.host = host
        self.tcp_port = tcp_port
        self.udp_port = udp_port
        
        self._tcp_reader: Optional[asyncio.StreamReader] = None
        self._tcp_writer: Optional[asyncio.StreamWriter] = None
        self._udp_transport: Optional[asyncio.DatagramTransport] = None
        self._udp_protocol: Optional[asyncio.DatagramProtocol] = None
        
        self._subscriptions: dict[str, Callable] = {}
        self._connected = False
        self._keepalive_task: Optional[asyncio.Task] = None
        self._tcp_listen_task: Optional[asyncio.Task] = None
        
    async def connect(self) -> bool:
        """Establish TCP and UDP connections."""
        try:
            # Connect TCP
            self._tcp_reader, self._tcp_writer = await asyncio.open_connection(
                self.host, self.tcp_port
            )
            _LOGGER.info("TCP connection established to %s:%s", self.host, self.tcp_port)
            
            # Setup UDP
            loop = asyncio.get_event_loop()
            self._udp_transport, self._udp_protocol = await loop.create_datagram_endpoint(
                lambda: AtlasUDPProtocol(self._handle_udp_message),
                remote_addr=(self.host, self.udp_port)
            )
            _LOGGER.info("UDP connection established to %s:%s", self.host, self.udp_port)
            
            self._connected = True
            
            # Give device a moment to settle after connection
            await asyncio.sleep(0.5)
            
            # Start listening for TCP messages
            self._tcp_listen_task = asyncio.create_task(self._tcp_listen())
            
            # Start keepalive
            self._keepalive_task = asyncio.create_task(self._keepalive_loop())
            
            return True
            
        except Exception as err:
            _LOGGER.error("Failed to connect: %s", err)
            await self.disconnect()
            return False
    
    async def disconnect(self):
        """Close all connections."""
        self._connected = False
        
        # Cancel tasks
        if self._keepalive_task:
            self._keepalive_task.cancel()
        if self._tcp_listen_task:
            self._tcp_listen_task.cancel()
            
        # Close TCP
        if self._tcp_writer:
            self._tcp_writer.close()
            await self._tcp_writer.wait_closed()
            
        # Close UDP
        if self._udp_transport:
            self._udp_transport.close()
            
        _LOGGER.info("Disconnected from Atlas AZM")
    
    async def _tcp_listen(self):
        """Listen for TCP messages."""
        try:
            while self._connected and self._tcp_reader:
                data = await self._tcp_reader.readline()
                if not data:
                    break
                    
                try:
                    message = json.loads(data.decode().strip())
                    await self._handle_tcp_message(message)
                except json.JSONDecodeError as err:
                    _LOGGER.error("Failed to decode TCP message: %s", err)
                    
        except asyncio.CancelledError:
            pass
        except Exception as err:
            _LOGGER.error("TCP listen error: %s", err)
            self._connected = False
    
    async def _handle_tcp_message(self, message: dict):
        """Handle incoming TCP message."""
        method = message.get("method")
        
        if method in ("update", "getResp"):
            params = message.get("params", [])
            if isinstance(params, dict):
                params = [params]
                
            for param_data in params:
                param_name = param_data.get("param")
                _LOGGER.debug("Received message for param: %s, subscribed: %s, data: %s", 
                             param_name, param_name in self._subscriptions, param_data)
                if param_name and param_name in self._subscriptions:
                    callback = self._subscriptions[param_name]
                    callback(param_name, param_data)
                    
        elif method == "error":
            _LOGGER.error("Error from AZM: %s", message)
    
    def _handle_udp_message(self, data: bytes):
        """Handle incoming UDP message (meters)."""
        try:
            message = json.loads(data.decode().strip())
            method = message.get("method")
            
            if method in ("update", "getResp"):
                params = message.get("params", [])
                if isinstance(params, dict):
                    params = [params]
                    
                for param_data in params:
                    param_name = param_data.get("param")
                    if param_name and param_name in self._subscriptions:
                        callback = self._subscriptions[param_name]
                        callback(param_name, param_data)
                        
        except json.JSONDecodeError as err:
            _LOGGER.error("Failed to decode UDP message: %s", err)
    
    async def _keepalive_loop(self):
        """Send periodic keepalive messages."""
        try:
            while self._connected:
                await asyncio.sleep(240)  # 4 minutes
                await self.get("KeepAlive", "str")
        except asyncio.CancelledError:
            pass
        except Exception as err:
            _LOGGER.error("Keepalive error: %s", err)
    
    async def _send_tcp(self, message: dict):
        """Send a message over TCP."""
        if not self._tcp_writer:
            raise ConnectionError("Not connected")
        
        try:
            json_str = json.dumps(message) + "\n"
            self._tcp_writer.write(json_str.encode())
            await self._tcp_writer.drain()
        except (BrokenPipeError, ConnectionResetError, OSError) as err:
            _LOGGER.error("Connection lost while sending message: %s", err)
            self._connected = False
            raise ConnectionError("Connection lost") from err
    
    async def set(self, param: str, value: Any, fmt: str = "val"):
        """Set a parameter value."""
        message = {
            "jsonrpc": "2.0",
            "method": "set",
            "params": {"param": param, fmt: value}
        }
        await self._send_tcp(message)
    
    async def bump(self, param: str, value: Any, fmt: str = "val"):
        """Bump a parameter value (increment/decrement)."""
        message = {
            "jsonrpc": "2.0",
            "method": "bmp",
            "params": {"param": param, fmt: value}
        }
        await self._send_tcp(message)
    
    async def get(self, param: str, fmt: str = "val") -> None:
        """Get a parameter value (one-time, use subscribe for continuous updates)."""
        message = {
            "jsonrpc": "2.0",
            "method": "get",
            "params": {"param": param, "fmt": fmt}
        }
        await self._send_tcp(message)
    
    async def subscribe(self, param: str, fmt: str, callback: Callable):
        """Subscribe to parameter updates."""
        message = {
            "jsonrpc": "2.0",
            "method": "sub",
            "params": {"param": param, "fmt": fmt}
        }
        await self._send_tcp(message)
        self._subscriptions[param] = callback
        _LOGGER.debug("Subscribed to %s", param)
    
    async def subscribe_multiple(self, params: list[dict[str, str]], callback: Callable):
        """Subscribe to multiple parameters at once."""
        message = {
            "jsonrpc": "2.0",
            "method": "sub",
            "params": params
        }
        await self._send_tcp(message)
        
        param_names = []
        for param_data in params:
            param_name = param_data.get("param")
            if param_name:
                self._subscriptions[param_name] = callback
                param_names.append(param_name)
        
        _LOGGER.debug("Subscribed to %d parameters: %s", len(params), param_names)
    
    async def unsubscribe(self, param: str, fmt: str = "val"):
        """Unsubscribe from parameter updates."""
        # Always remove from subscriptions dict, even if send fails
        self._subscriptions.pop(param, None)
        
        try:
            message = {
                "jsonrpc": "2.0",
                "method": "unsub",
                "params": {"param": param, "fmt": fmt}
            }
            await self._send_tcp(message)
            _LOGGER.debug("Unsubscribed from %s", param)
        except ConnectionError:
            # Connection already lost, subscription removal from dict is sufficient
            _LOGGER.debug("Connection lost during unsubscribe from %s (already removed from subscriptions)", param)
    
    @property
    def is_connected(self) -> bool:
        """Return connection status."""
        return self._connected


class AtlasUDPProtocol(asyncio.DatagramProtocol):
    """UDP protocol handler for Atlas AZM."""
    
    def __init__(self, message_handler: Callable):
        """Initialize the protocol."""
        self.message_handler = message_handler
    
    def datagram_received(self, data: bytes, addr):
        """Handle received datagram."""
        self.message_handler(data)
    
    def error_received(self, exc):
        """Handle error."""
        _LOGGER.error("UDP error: %s", exc)
