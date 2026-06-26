#!/usr/bin/env python3
"""
礼物配置管理模块
Gift Configuration Management Module
"""

import os
import logging
from typing import List, Dict, Optional
from common.database_manager import get_database_manager

# 价值等级定义
VALUE_LEVELS = {
    '巨': '巨大',
    '大': '大',
    '中': '中',
    '小': '小',
    '微': '微',
    '无': '无'
}

# 价值等级排序（从高到低）
VALUE_LEVEL_ORDER = ['巨', '大', '中', '小', '微', '无']

class GiftConfigManager:
    """礼物配置管理器"""
    
    def __init__(self):
        """
        初始化礼物配置管理器
        """
        self.logger = logging.getLogger('gift_config')
        self.db = get_database_manager()
        self._gifts = []
        
        # 加载配置
        self.load()
    
    def load(self) -> bool:
        """
        加载礼物配置
        
        Returns:
            bool: 加载是否成功
        """
        try:
            gifts = self.db.get_all_gifts()
            self._gifts = []
            
            for gift in gifts:
                self._gifts.append({
                    'id': gift['id'],
                    'name': gift['name'],
                    'value': gift['value'],
                    'level': gift['level']
                })
            
            # self.logger.info(f"成功加载 {len(self._gifts)} 个礼物配置")
            return True
                
        except Exception as e:
            self.logger.error(f"加载配置失败: {e}")
            self._gifts = []
            return False
    
    def save(self) -> bool:
        """
        保存礼物配置
        
        Returns:
            bool: 保存是否成功
        """
        try:
            import sqlite3
            
            conn = sqlite3.connect(self.db._db_path)
            conn.execute("DELETE FROM gifts")
            
            for i, gift in enumerate(self._gifts, 1):
                conn.execute("""
                    INSERT INTO gifts (id, name, value, level, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (i, gift['name'], gift['value'], gift['level']))
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"成功保存 {len(self._gifts)} 个礼物配置")
            
            # 保存后立即重新加载数据，确保内存中的数据与数据库一致
            return self.load()
            
        except Exception as e:
            self.logger.error(f"保存配置失败: {e}")
            return False
    
    def get_all_gifts(self) -> List[Dict]:
        """
        获取所有礼物配置
        
        Returns:
            List[Dict]: 礼物列表
        """
        return self._gifts
    
    def get_gift_by_name(self, name: str) -> Optional[Dict]:
        """
        根据礼物名称获取配置
        
        Args:
            name: 礼物名称
            
        Returns:
            Optional[Dict]: 礼物配置，如果不存在返回None
        """
        if not name:
            return None
        
        name = str(name).strip()
        
        for gift in self._gifts:
            gift_name = gift.get('name')
            if gift_name:
                gift_name_str = str(gift_name).strip()
                if gift_name_str == name:
                    return gift
        
        return None
    
    def get_gift_by_id(self, gift_id: int) -> Optional[Dict]:
        """
        根据礼物ID获取配置
        
        Args:
            gift_id: 礼物ID
            
        Returns:
            Optional[Dict]: 礼物配置，如果不存在返回None
        """
        for gift in self._gifts:
            if gift.get('id') == gift_id:
                return gift
        return None
    
    def add_gift(self, name: str, value: int, level: str) -> bool:
        """
        添加礼物配置
        
        Args:
            name: 礼物名称
            value: 礼物价值（钻石的数量）
            level: 价值等级（巨、大、中、小、微、无）
            
        Returns:
            bool: 添加是否成功
        """
        # 检查礼物是否已存在
        if self.get_gift_by_name(name):
            self.logger.warning(f"礼物已存在: {name}")
            return False
        
        # 验证价值等级
        if level not in VALUE_LEVELS:
            self.logger.warning(f"无效的价值等级: {level}")
            return False
        
        gift = {
            'name': name,
            'value': value,
            'level': level
        }
        
        self._gifts.append(gift)
        return True
    
    def update_gift(self, old_name: str, new_name: str = None, value: int = None, level: str = None) -> bool:
        """
        更新礼物配置
        
        Args:
            old_name: 原礼物名称（用于查找）
            new_name: 新礼物名称（可选，如果要修改名称）
            value: 礼物价值（可选）
            level: 价值等级（可选）
            
        Returns:
            bool: 更新是否成功
        """
        gift = self.get_gift_by_name(old_name)
        if not gift:
            self.logger.warning(f"礼物不存在: {old_name}")
            return False
        
        # 如果要修改名称
        if new_name is not None and new_name != '':
            new_name = str(new_name).strip()
            if new_name != old_name:
                # 检查新名称是否已存在
                if self.get_gift_by_name(new_name):
                    self.logger.warning(f"礼物名称已存在: {new_name}")
                    return False
                # 更新名称
                gift['name'] = new_name
        
        if value is not None:
            gift['value'] = value
        
        if level is not None:
            if level not in VALUE_LEVELS:
                self.logger.warning(f"无效的价值等级: {level}")
                return False
            gift['level'] = level
        
        return True
    
    def delete_gift(self, name: str) -> bool:
        """
        删除礼物配置
        
        Args:
            name: 礼物名称
            
        Returns:
            bool: 删除是否成功
        """
        for i, gift in enumerate(self._gifts):
            if gift.get('name') == name:
                self._gifts.pop(i)
                return True
        
        self.logger.warning(f"礼物不存在: {name}")
        return False
    
    def update_gift_by_id(self, gift_id: int, new_name: str = None, value: int = None, level: str = None) -> bool:
        """
        根据ID更新礼物配置
        
        Args:
            gift_id: 礼物ID
            new_name: 新礼物名称（可选）
            value: 礼物价值（可选）
            level: 价值等级（可选）
            
        Returns:
            bool: 更新是否成功
        """
        gift = self.get_gift_by_id(gift_id)
        if not gift:
            self.logger.warning(f"礼物ID不存在: {gift_id}")
            return False
        
        if new_name is not None and new_name != '':
            new_name = str(new_name).strip()
            old_name = gift.get('name')
            if new_name != old_name:
                if self.get_gift_by_name(new_name):
                    self.logger.warning(f"礼物名称已存在: {new_name}")
                    return False
                gift['name'] = new_name
        
        if value is not None:
            gift['value'] = value
        
        if level is not None:
            if level not in VALUE_LEVELS:
                self.logger.warning(f"无效的价值等级: {level}")
                return False
            gift['level'] = level
        
        return True
    
    def delete_gift_by_id(self, gift_id: int) -> bool:
        """
        根据ID删除礼物配置
        
        Args:
            gift_id: 礼物ID
            
        Returns:
            bool: 删除是否成功
        """
        for i, gift in enumerate(self._gifts):
            if gift.get('id') == gift_id:
                self._gifts.pop(i)
                return True
        
        self.logger.warning(f"礼物ID不存在: {gift_id}")
        return False
    
    def get_gift_value(self, name: str) -> int:
        """
        获取礼物价值
        
        Args:
            name: 礼物名称
            
        Returns:
            int: 礼物价值，如果不存在返回0
        """
        gift = self.get_gift_by_name(name)
        if gift:
            return gift.get('value', 0)
        return 0
    
    def get_gift_level(self, name: str) -> str:
        """
        获取礼物价值等级
        
        Args:
            name: 礼物名称
            
        Returns:
            str: 价值等级，如果不存在返回'无'
        """
        gift = self.get_gift_by_name(name)
        if gift:
            return gift.get('level', '无')
        return '无'
    
    def get_gifts_by_level(self, level: str) -> List[Dict]:
        """
        根据价值等级获取礼物列表
        
        Args:
            level: 价值等级
            
        Returns:
            List[Dict]: 礼物列表
        """
        return [gift for gift in self._gifts if gift.get('level') == level]
    
    def sort_gifts_by_value(self, reverse: bool = True) -> List[Dict]:
        """
        按价值排序礼物
        
        Args:
            reverse: 是否降序排序，默认为True
            
        Returns:
            List[Dict]: 排序后的礼物列表
        """
        return sorted(self._gifts, key=lambda x: x.get('value', 0), reverse=reverse)
    
    def sort_gifts_by_level(self) -> List[Dict]:
        """
        按价值等级排序礼物（从高到低）
        
        Returns:
            List[Dict]: 排序后的礼物列表
        """
        def get_level_index(level):
            try:
                return VALUE_LEVEL_ORDER.index(level)
            except ValueError:
                return len(VALUE_LEVEL_ORDER)
        
        return sorted(self._gifts, key=lambda x: get_level_index(x.get('level', '无')))


# 创建全局实例
_gift_config_manager = None

def get_gift_config_manager() -> GiftConfigManager:
    """
    获取礼物配置管理器实例（单例模式）
    
    Returns:
        GiftConfigManager: 礼物配置管理器实例
    """
    global _gift_config_manager
    if _gift_config_manager is None:
        _gift_config_manager = GiftConfigManager()
    return _gift_config_manager


if __name__ == '__main__':
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    manager = get_gift_config_manager()
    
    # 显示所有礼物
    print("所有礼物:")
    for gift in manager.get_all_gifts():
        print(f"  {gift['name']}: {gift['value']} ({gift['level']})")
    
    # 按价值等级排序
    print("\n按价值等级排序:")
    for gift in manager.sort_gifts_by_level():
        print(f"  {gift['name']}: {gift['value']} ({gift['level']})")
