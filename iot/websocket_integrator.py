#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebSocket消息集成器
将WebSocket接收到的消息集成到IoT系统中
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.logger import get_logger
from common.database_manager import get_database_manager

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False


class WebSocketIntegrator:
    """WebSocket消息集成器"""
    
    def __init__(self, 
                 ws_url: str = "ws://localhost:8888",
                 auto_reconnect: bool = True,
                 reconnect_interval: float = 5.0):
        """
        初始化集成器
        
        Args:
            ws_url: WebSocket服务器地址
            auto_reconnect: 是否自动重连
            reconnect_interval: 重连间隔(秒)
        """
        self.ws_url = ws_url
        self.auto_reconnect = auto_reconnect
        self.reconnect_interval = reconnect_interval
        
        self.logger = get_logger()
        self.db_manager = get_database_manager()
        
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_running: bool = False
        self._task: Optional[asyncio.Task] = None
        
        self.message_count: int = 0
        self.last_message_time: Optional[datetime] = None
        
        # 回调函数
        self._on_gift: Optional[callable] = None
        self._on_message: Optional[callable] = None
        self._on_any: Optional[callable] = None
    
    def set_callbacks(self, 
                     on_gift: Optional[callable] = None,
                     on_message: Optional[callable] = None,
                     on_any: Optional[callable] = None):
        """
        设置回调函数
        
        Args:
            on_gift: 礼物消息回调
            on_message: 聊天消息回调
            on_any: 任何消息回调
        """
        self._on_gift = on_gift
        self._on_message = on_message
        self._on_any = on_any
    
    async def connect(self):
        """连接到WebSocket服务器"""
        try:
            self.logger.info(f"正在连接到WebSocket服务器: {self.ws_url}")
            self.websocket = await websockets.connect(self.ws_url)
            self.logger.info("WebSocket连接成功")
            return True
        except Exception as e:
            self.logger.error(f"WebSocket连接失败: {e}")
            return False
    
    async def disconnect(self):
        """断开WebSocket连接"""
        if self.websocket:
            try:
                await self.websocket.close()
                self.logger.info("WebSocket连接已关闭")
            except Exception as e:
                self.logger.error(f"关闭WebSocket连接失败: {e}")
            finally:
                self.websocket = None
    
    async def _process_message(self, message: Dict[str, Any]):
        """
        处理接收到的消息
        
        Args:
            message: 消息字典
        """
        self.message_count += 1
        self.last_message_time = datetime.now()
        
        # 调用任意消息回调
        if self._on_any:
            try:
                if asyncio.iscoroutinefunction(self._on_any):
                    await self._on_any(message)
                else:
                    self._on_any(message)
            except Exception as e:
                self.logger.error(f"消息回调执行失败: {e}")
        
        # 获取消息类型
        message_type = message.get('type', 'unknown')
        
        if message_type == 'gif':
            # 礼物消息
            await self._process_gift(message)
        elif message_type == 'msg':
            # 聊天消息
            await self._process_chat(message)
        else:
            self.logger.debug(f"收到未处理的消息类型: {message_type}")
    
    async def _process_gift(self, message: Dict[str, Any]):
        """
        处理礼物消息
        
        Args:
            message: 礼物消息
        """
        try:
            room = message.get('room', '')
            name = message.get('name', '')
            giftname = message.get('giftname', '')
            giftcount = message.get('giftcount', 0)
            giftdiamond = message.get('giftdiamond', 0)
            
            self.logger.info(
                f"收到礼物 - 房间: {room}, 用户: {name}, "
                f"礼物: {giftname}, 数量: {giftcount}, 钻石: {giftdiamond}"
            )
            
            # 调用礼物回调
            if self._on_gift:
                try:
                    if asyncio.iscoroutinefunction(self._on_gift):
                        await self._on_gift(message)
                    else:
                        self._on_gift(message)
                except Exception as e:
                    self.logger.error(f"礼物回调执行失败: {e}")
            
        except Exception as e:
            self.logger.error(f"处理礼物消息失败: {e}")
    
    async def _process_chat(self, message: Dict[str, Any]):
        """
        处理聊天消息
        
        Args:
            message: 聊天消息
        """
        try:
            room = message.get('room', '')
            name = message.get('name', '')
            content = message.get('content', '')
            
            self.logger.info(
                f"收到聊天 - 房间: {room}, 用户: {name}, 内容: {content}"
            )
            
            # 调用聊天回调
            if self._on_message:
                try:
                    if asyncio.iscoroutinefunction(self._on_message):
                        await self._on_message(message)
                    else:
                        self._on_message(message)
                except Exception as e:
                    self.logger.error(f"聊天回调执行失败: {e}")
            
        except Exception as e:
            self.logger.error(f"处理聊天消息失败: {e}")
    
    async def _receive_loop(self):
        """接收消息的主循环"""
        while self.is_running:
            try:
                if not self.websocket:
                    # 尝试连接
                    connected = await self.connect()
                    if not connected:
                        await asyncio.sleep(self.reconnect_interval)
                        continue
                
                # 接收消息
                message_data = await self.websocket.recv()
                
                # 解析消息
                try:
                    message = json.loads(message_data)
                    await self._process_message(message)
                except json.JSONDecodeError:
                    self.logger.warning(f"收到无效的JSON数据: {message_data}")
                    continue
                
            except websockets.exceptions.ConnectionClosed:
                self.logger.warning("WebSocket连接已关闭")
                await self.disconnect()
                if not self.auto_reconnect:
                    break
                await asyncio.sleep(self.reconnect_interval)
            
            except Exception as e:
                self.logger.error(f"接收消息失败: {e}")
                await self.disconnect()
                if not self.