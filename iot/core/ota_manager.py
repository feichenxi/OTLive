import os
import json
import requests
import hashlib
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logger = logging.getLogger(__name__)


class OTAManager:
    def __init__(self, firmware_dir: str = "firmware"):
        self.firmware_dir = firmware_dir
        self.versions_file = os.path.join(firmware_dir, "versions.json")
        self.devices: List[Dict] = []
        self.max_workers = 3
        
    def load_versions(self) -> Dict:
        if not os.path.exists(self.versions_file):
            return {"latest": "0.0.0", "versions": []}
        with open(self.versions_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def save_versions(self, data: Dict):
        with open(self.versions_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def add_firmware_version(self, version: str, file_path: str, notes: str = ""):
        versions = self.load_versions()
        firmware_filename = f"firmware_v{version}.bin"
        dest_path = os.path.join(self.firmware_dir, firmware_filename)
        
        import shutil
        shutil.copy2(file_path, dest_path)
        
        new_version = {
            "version": version,
            "file": firmware_filename,
            "release_date": self._get_current_date(),
            "notes": notes,
            "compatible": [version]
        }
        
        versions["versions"].append(new_version)
        versions["latest"] = version
        self.save_versions(versions)
        logger.info(f"固件版本 {version} 已添加")
    
    def parse_version(self, version_str: str) -> List[int]:
        return list(map(int, version_str.split('.')))
    
    def compare_versions(self, v1: str, v2: str) -> int:
        ver1 = self.parse_version(v1)
        ver2 = self.parse_version(v2)
        
        for i in range(3):
            if ver1[i] > ver2[i]:
                return 1
            if ver1[i] < ver2[i]:
                return -1
        return 0
    
    def needs_update(self, device_version: str, target_version: str) -> bool:
        return self.compare_versions(device_version, target_version) < 0
    
    def get_device_info(self, ip: str) -> Optional[Dict]:
        try:
            response = requests.get(f"http://{ip}/ota/info", timeout=5)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"获取设备 {ip} 信息失败: {e}")
        return None
    
    def update_single_device(self, ip: str, firmware_path: str) -> Dict:
        result = {
            "ip": ip,
            "success": False,
            "message": "",
            "device_info": None
        }
        
        try:
            device_info = self.get_device_info(ip)
            result["device_info"] = device_info
            
            if not device_info:
                result["message"] = "无法获取设备信息"
                return result
            
            with open(firmware_path, 'rb') as f:
                files = {'firmware': f}
                response = requests.post(
                    f"http://{ip}/ota/upload",
                    files=files,
                    timeout=300
                )
            
            if response.status_code == 200:
                requests.post(f"http://{ip}/ota/reboot", timeout=5)
                result["success"] = True
                result["message"] = "更新成功"
                logger.info(f"设备 {ip} 更新成功")
            else:
                result["message"] = f"上传失败: {response.status_code}"
            
        except Exception as e:
            result["message"] = str(e)
            logger.error(f"设备 {ip} 更新失败: {e}")
        
        return result
    
    def batch_update(self, devices: List[str], firmware_path: str, 
                     max_workers: Optional[int] = None) -> List[Dict]:
        workers = max_workers or self.max_workers
        results = []
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_ip = {
                executor.submit(self.update_single_device, ip, firmware_path): ip
                for ip in devices
            }
            
            for future in as_completed(future_to_ip):
                results.append(future.result())
        
        return results
    
    def _get_current_date(self) -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")
