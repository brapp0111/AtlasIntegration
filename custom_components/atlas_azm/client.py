"""Atlas AZM4/AZM8 TCP/UDP Client."""
import asyncio
import json
import logging
from typing import Any, Callable, Optional

_LOGGER = logging.getLogger(__name__)

CONNECT_TIMEOUT = 10
# AZM drops idle connections after ~5 minutes; ping well inside that
KEEPALIVE_INTERVAL = 60
# Declare the link dead if nothing (not even a KeepAlive reply) arrives in this window
KEEPALIVE_TIMEOUT = 150
RECONNECT_MIN_DELAY = 5
RECONNECT_MAX_DELAY = 60
RESUBSCRIBE_BATCH = 50
# Batched subscription responses can exceed asyncio's 64 KiB default line limit
STREAM_LIMIT = 1024 * 1024


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
        
        self._subscriptions: dict[str, list[Callable]] = {}
        # Format of each subscribed parameter, needed to resubscribe after a reconnect
        self._subscription_formats: dict[str, str] = {}
        self._connected = False
        self._closing = False
        self._last_rx = 0.0
        self._keepalive_task: Optional[asyncio.Task] = None
        self._tcp_listen_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        # Requests sent with an "id", waiting for their result/error reply
        self._pending: dict[int, asyncio.Future] = {}
        self._next_id = 1
        
    async def connect(self) -> bool:
        """Establish TCP and UDP connections."""
        self._closing = False
        try:
            await self._open()
            return True
        except Exception as err:
            _LOGGER.error("Failed to connect: %s", err)
            await self._close_transports()
            return False
    
    async def _open(self):
        """Open TCP and UDP and start the listener and keepalive tasks."""
        # Connect TCP
        self._tcp_reader, self._tcp_writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.tcp_port, limit=STREAM_LIMIT),
            timeout=CONNECT_TIMEOUT,
        )
        _LOGGER.info("TCP connection established to %s:%s", self.host, self.tcp_port)
        
        # Setup UDP
        loop = asyncio.get_running_loop()
        self._udp_transport, self._udp_protocol = await loop.create_datagram_endpoint(
            lambda: AtlasUDPProtocol(self._handle_udp_message),
            remote_addr=(self.host, self.udp_port)
        )
        _LOGGER.info("UDP connection established to %s:%s", self.host, self.udp_port)
        
        self._connected = True
        self._last_rx = loop.time()
        
        # Give device a moment to settle after connection
        await asyncio.sleep(0.5)
        
        # Start listening for TCP messages
        self._tcp_listen_task = asyncio.create_task(self._tcp_listen())
        
        # Start keepalive
        self._keepalive_task = asyncio.create_task(self._keepalive_loop())
    
    async def disconnect(self):
        """Close all connections and stop reconnecting."""
        self._closing = True
        if self._reconnect_task:
            self._reconnect_task.cancel()
            self._reconnect_task = None
        await self._close_transports()
        _LOGGER.info("Disconnected from Atlas AZM")
    
    async def _close_transports(self):
        """Cancel tasks and close sockets without touching subscriptions."""
        self._connected = False
        current = asyncio.current_task()
        
        # Cancel tasks (but not the one calling us)
        for task in (self._keepalive_task, self._tcp_listen_task):
            if task and task is not current:
                task.cancel()
        self._keepalive_task = None
        self._tcp_listen_task = None
        
        # Fail any requests still waiting on a reply
        for future in self._pending.values():
            if not future.done():
                future.set_exception(ConnectionError("Connection closed"))
        self._pending.clear()
            
        # Close TCP
        if self._tcp_writer:
            writer = self._tcp_writer
            self._tcp_writer = None
            self._tcp_reader = None
            try:
                writer.close()
                await asyncio.wait_for(writer.wait_closed(), timeout=5)
            except Exception as err:
                _LOGGER.debug("Error closing TCP connection: %s", err)
            
        # Close UDP
        if self._udp_transport:
            self._udp_transport.close()
            self._udp_transport = None
            self._udp_protocol = None
    
    def _connection_lost(self, reason: str):
        """Mark the connection dead and start reconnecting."""
        if self._closing:
            return
        if self._connected:
            _LOGGER.warning("Connection to Atlas AZM at %s lost: %s", self.host, reason)
        self._connected = False
        if not self._reconnect_task or self._reconnect_task.done():
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())
    
    async def _reconnect_loop(self):
        """Reconnect with backoff, then restore all subscriptions."""
        delay = RECONNECT_MIN_DELAY
        try:
            while not self._closing:
                await self._close_transports()
                await asyncio.sleep(delay)
                try:
                    await self._open()
                    await self._resubscribe()
                    _LOGGER.info("Reconnected to Atlas AZM at %s", self.host)
                    return
                except asyncio.CancelledError:
                    raise
                except Exception as err:
                    _LOGGER.warning(
                        "Reconnect to Atlas AZM at %s failed: %s (retrying in %ss)",
                        self.host, err, min(delay * 2, RECONNECT_MAX_DELAY),
                    )
                    delay = min(delay * 2, RECONNECT_MAX_DELAY)
        except asyncio.CancelledError:
            pass
    
    async def _resubscribe(self):
        """Re-send subscriptions; the AZM drops them when TCP closes."""
        params = [
            {"param": param, "fmt": self._subscription_formats.get(param, "val")}
            for param in self._subscriptions
        ]
        for i in range(0, len(params), RESUBSCRIBE_BATCH):
            await self._send_tcp({
                "jsonrpc": "2.0",
                "method": "sub",
                "params": params[i:i + RESUBSCRIBE_BATCH],
            })
        _LOGGER.debug("Resubscribed to %d parameters", len(params))
    
    async def _tcp_listen(self):
        """Listen for TCP messages."""
        reason = "connection closed by device"
        try:
            while self._connected and self._tcp_reader:
                data = await self._tcp_reader.readline()
                if not data:
                    break
                self._last_rx = asyncio.get_running_loop().time()
                    
                try:
                    message = json.loads(data.decode().strip())
                    await self._handle_tcp_message(message)
                except json.JSONDecodeError as err:
                    _LOGGER.error("Failed to decode TCP message: %s", err)
                    
        except asyncio.CancelledError:
            return
        except Exception as err:
            _LOGGER.error("TCP listen error: %s", err)
            reason = str(err)
        self._connection_lost(reason)
    
    async def _handle_tcp_message(self, message: dict):
        """Handle incoming TCP message."""
        # Reply to a request sent with an "id"
        if "id" in message and ("result" in message or "error" in message):
            future = self._pending.pop(message["id"], None)
            if future and not future.done():
                future.set_result(message)
            return
        
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
                    # Call all callbacks registered for this parameter
                    for callback in list(self._subscriptions[param_name]):
                        self._run_callback(callback, param_name, param_data)
                    
        elif method == "error":
            _LOGGER.error("Error from AZM: %s", message)
    
    @staticmethod
    def _run_callback(callback: Callable, param_name: str, param_data: dict):
        """Run an entity callback; a bad callback must not kill the listener."""
        try:
            callback(param_name, param_data)
        except Exception:
            _LOGGER.exception("Error in update callback for %s", param_name)
    
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
                        # Mirror TCP behavior: each parameter may have multiple listeners.
                        for callback in list(self._subscriptions[param_name]):
                            self._run_callback(callback, param_name, param_data)
                        
        except json.JSONDecodeError as err:
            _LOGGER.error("Failed to decode UDP message: %s", err)
    
    async def _keepalive_loop(self):
        """Send periodic keepalives and drop the connection if the device goes quiet."""
        loop = asyncio.get_running_loop()
        try:
            while self._connected:
                await asyncio.sleep(KEEPALIVE_INTERVAL)
                if loop.time() - self._last_rx > KEEPALIVE_TIMEOUT:
                    self._connection_lost(
                        f"no data received for {int(loop.time() - self._last_rx)}s"
                    )
                    return
                await self.get("KeepAlive", "str")
        except asyncio.CancelledError:
            pass
        except Exception as err:
            _LOGGER.error("Keepalive error: %s", err)
            self._connection_lost(f"keepalive failed: {err}")
    
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
            self._connection_lost(str(err))
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
    
    async def request(self, method: str, params: Any, timeout: float = 5) -> dict:
        """Send a message with an "id" and return the device's result/error reply."""
        request_id = self._next_id
        self._next_id += 1
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        try:
            await self._send_tcp({
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "id": request_id,
            })
            return await asyncio.wait_for(future, timeout)
        finally:
            self._pending.pop(request_id, None)
    
    async def get_name(self, param: str) -> Optional[str]:
        """Return a name parameter's value, or None if the device has no such parameter."""
        reply = await self.request("get", {"param": param, "fmt": "str"})
        result = reply.get("result")
        if not isinstance(result, list) or not result:
            return None
        return result[0].get("str", "")
    
    async def subscribe(self, param: str, fmt: str, callback: Callable):
        """Subscribe to parameter updates."""
        message = {
            "jsonrpc": "2.0",
            "method": "sub",
            "params": {"param": param, "fmt": fmt}
        }
        
        # Add callback to the list for this parameter
        if param not in self._subscriptions:
            self._subscriptions[param] = []
        self._subscriptions[param].append(callback)
        self._subscription_formats[param] = fmt
        
        # While reconnecting, the resubscribe after reconnect covers this
        if self._connected:
            await self._send_tcp(message)
        
        _LOGGER.debug("Subscribed to %s (total callbacks: %d)", param, len(self._subscriptions[param]))
    
    async def subscribe_multiple(self, params: list[dict[str, str]], callback: Callable):
        """Subscribe to multiple parameters at once."""
        message = {
            "jsonrpc": "2.0",
            "method": "sub",
            "params": params
        }
        
        param_names = []
        for param_data in params:
            param_name = param_data.get("param")
            if param_name:
                # Add callback to the list for this parameter
                if param_name not in self._subscriptions:
                    self._subscriptions[param_name] = []
                self._subscriptions[param_name].append(callback)
                self._subscription_formats[param_name] = param_data.get("fmt", "val")
                param_names.append(param_name)
        
        # While reconnecting, the resubscribe after reconnect covers this
        if self._connected:
            await self._send_tcp(message)
        
        _LOGGER.debug("Subscribed to %d parameters: %s", len(params), param_names)
    
    async def unsubscribe(self, param: str, fmt: str = "val", callback: Optional[Callable] = None):
        """Unsubscribe from parameter updates.
        
        If callback is provided, only that callback is removed.
        If callback is None, all callbacks for the parameter are removed.
        Only sends unsub message to device when last callback is removed.
        """
        if param not in self._subscriptions:
            return
            
        if callback:
            # Remove specific callback
            try:
                self._subscriptions[param].remove(callback)
                _LOGGER.debug("Removed callback from %s (remaining: %d)", param, len(self._subscriptions[param]))
            except (ValueError, KeyError):
                pass
            
            # If no more callbacks, clean up
            if not self._subscriptions[param]:
                del self._subscriptions[param]
        else:
            # Remove all callbacks
            del self._subscriptions[param]
        
        # Only send unsub to device if no more callbacks for this parameter
        if param not in self._subscriptions:
            self._subscription_formats.pop(param, None)
            if not self._connected:
                return
            try:
                message = {
                    "jsonrpc": "2.0",
                    "method": "unsub",
                    "params": {"param": param, "fmt": fmt}
                }
                await self._send_tcp(message)
                _LOGGER.debug("Unsubscribed from %s (sent to device)", param)
            except ConnectionError:
                # Connection already lost, subscription removal from dict is sufficient
                _LOGGER.debug("Connection lost during unsubscribe from %s", param)
    
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
