import socket
import json
import threading
import time
from typing import Dict, Optional, Callable
from common.logger import get_logger
from common.database_manager import get_database_manager


class NetworkServer:
    def __init__(self):
        self.logger = get_logger()
        self.config = get_database_manager()
        
        self.tcp_socket: Optional[socket.socket] = None
        self.udp_socket: Optional[socket.socket] = None
        
        self.is_running: bool = False
        self._tcp_thread: Optional[threading.Thread] = None
        self._udp_thread: Optional[threading.Thread] = None
        
        self._message_handlers: Dict[str, Callable] = {}
        
        self.simulation_mode = self.config.get('system.simulation_mode', False)
    
    @property
    def tcp_port(self):
        return self.config.get('network.tcp_port', 8080)
    
    @property
    def udp_port(self):
        return self.config.get('network.udp_port', 5000)

    def register_handler(self, message_type: str, handler: Callable):
        self._message_handlers[message_type] = handler
        self.logger.info(f"注册消息处理器: {message_type}")

    def start(self):
        if self.is_running:
            self.logger.warning("网络服务器已在运行")
            return False
            
        try:
            if not self.simulation_mode:
                self._setup_tcp_server()
                self._setup_udp_server()
            else:
                self.logger.info("模拟模式：TCP/UDP服务器已禁用")
            
            self.is_running = True
            
            if not self.simulation_mode:
                self._tcp_thread = threading.Thread(target=self._tcp_server_loop, daemon=True)
                self._tcp_thread.start()
                
                self._udp_thread = threading.Thread(target=self._udp_server_loop, daemon=True)
                self._udp_thread.start()
            
            self.logger.info(f"网络服务器已启动 - TCP:{self.tcp_port}, UDP:{self.udp_port}")
            return True
            
        except Exception as e:
            self.logger.error(f"网络服务器启动失败: {e}")
            self._cleanup()
            return False

    def stop(self):
        self.is_running = False
        
        if self._tcp_thread:
            self._tcp_thread.join(timeout=2)
        if self._udp_thread:
            self._udp_thread.join(timeout=2)
            
        self._cleanup()
        self.logger.info("网络服务器已停止")

    def _setup_tcp_server(self):
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_socket.bind(('0.0.0.0', self.tcp_port))
        self.tcp_socket.listen(10)
        self.tcp_socket.settimeout(1)
        self.logger.info(f"TCP服务器监听端口 {self.tcp_port}")

    def _setup_udp_server(self):
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind(('0.0.0.0', self.udp_port))
        self.udp_socket.settimeout(1)
        self.logger.info(f"UDP服务器监听端口 {self.udp_port}")

    def _tcp_server_loop(self):
        while self.is_running:
            try:
                client_socket, client_address = self.tcp_socket.accept()
                self.logger.info(f"TCP连接来自: {client_address}")
                
                client_thread = threading.Thread(
                    target=self._handle_tcp_client,
                    args=(client_socket, client_address),
                    daemon=True
                )
                client_thread.start()
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.is_running:
                    self.logger.error(f"TCP服务器错误: {e}")

    def _handle_tcp_client(self, client_socket: socket.socket, client_address: tuple):
        try:
            while self.is_running:
                data = client_socket.recv(4096)
                if not data:
                    break
                    
                try:
                    message = json.loads(data.decode())
                    self.logger.debug(f"收到TCP消息: {message}")
                    
                    response = self._process_message(message, client_address)
                    
                    if response:
                        client_socket.sendall(json.dumps(response).encode())
                        
                except json.JSONDecodeError:
                    self.logger.warning(f"收到无效的JSON数据: {data}")
                    
        except Exception as e:
            self.logger.error(f"处理TCP客户端错误: {e}")
        finally:
            client_socket.close()
            self.logger.info(f"TCP连接关闭: {client_address}")

    def _udp_server_loop(self):
        while self.is_running:
            try:
                data, client_address = self.udp_socket.recvfrom(4096)
                self.logger.debug(f"收到UDP数据: {len(data)} bytes from {client_address}")
                
                self._process_udp_data(data, client_address)
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.is_running:
                    self.logger.error(f"UDP服务器错误: {e}")

    def _process_udp_data(self, data: bytes, client_address: tuple):
        try:
            message_type = 'udp_audio'
            if message_type in self._message_handlers:
                self._message_handlers[message_type](data, client_address)
        except Exception as e:
            self.logger.error(f"处理UDP数据错误: {e}")

    def _process_message(self, message: Dict, client_address: tuple) -> Optional[Dict]:
        try:
            message_type = message.get('type')
            
            if message_type in self._message_handlers:
                return self._message_handlers[message_type](message, client_address)
            else:
                self.logger.warning(f"未知的消息类型: {message_type}")
                return {'status': 'error', 'message': 'Unknown message type'}
                
        except Exception as e:
            self.logger.error(f"处理消息错误: {e}")
            return {'status': 'error', 'message': str(e)}

    def send_tcp_message(self, host: str, port: int, message: Dict) -> Optional[Dict]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            
            sock.connect((host, port))
            sock.sendall(json.dumps(message).encode())
            
            response = sock.recv(4096).decode()
            sock.close()
            
            return json.loads(response)
            
        except Exception as e:
            self.logger.error(f"发送TCP消息失败: {e}")
            return None

    def send_udp_message(self, host: str, port: int, data: bytes) -> bool:
        try:
            self.udp_socket.sendto(data, (host, port))
            return True
        except Exception as e:
            self.logger.error(f"发送UDP消息失败: {e}")
            return False

    def broadcast_udp_message(self, port: int, data: bytes) -> bool:
        try:
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.udp_socket.sendto(data, ('<broadcast>', port))
            return True
        except Exception as e:
            self.logger.error(f"广播UDP消息失败: {e}")
            return False

    def _cleanup(self):
        if self.tcp_socket:
            try:
                self.tcp_socket.close()
            except:
                pass
                
        if self.udp_socket:
            try:
                self.udp_socket.close()
            except:
                pass