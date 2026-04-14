"""
Configuration loader for the scraping pipeline.
"""

import os
import json
import platform
from pathlib import Path
from typing import Optional, Dict, Any, List


class Config:
    """Configuration manager."""
    
    def __init__(self, config_dir: str = "config_files"):
        self.config_dir = Path(config_dir)
        self.config = self._load_defaults()
        self.user_agents_by_os = {}
        
        # Load main config.json
        main_config_path = self.config_dir / "config.json"
        if main_config_path.exists():
            file_config = self._load_json(main_config_path)
            if file_config:
                self._merge(file_config)
        
        # Load user_agents.json
        ua_config_path = self.config_dir / "user_agents.json"
        if ua_config_path.exists():
            ua_config = self._load_json(ua_config_path)
            if ua_config:
                self.user_agents_by_os = ua_config
        
        self._load_from_env()
    
    def _load_defaults(self) -> Dict[str, Any]:
        return {
            "scraper": {
                "timeout": 10,
                "max_retries": 2,
                "max_concurrent": 10,
                "use_playwright": False,
                "use_selenium": False,
                "allow_direct_fallback": False,
                "retry_without_compression": True,
                "min_content_length": 500
            },
            "playwright": {
                "headless": True,
                "timeout": 30000
            },
            "selenium": {
                "headless": True,
                "timeout": 30,
                "incognito": True
            },
            "proxy": {
                "enabled": True
            },
        }
    
    def _load_json(self, path: Path) -> Optional[Dict[str, Any]]:
        if not path.exists():
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARNING] Failed to load {path}: {e}")
            return None
    
    def _merge(self, override: Dict[str, Any]):
        for key, value in override.items():
            if key in self.config and isinstance(self.config[key], dict) and isinstance(value, dict):
                self._merge_dict(self.config[key], value)
            else:
                self.config[key] = value
    
    def _merge_dict(self, target: Dict, source: Dict):
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._merge_dict(target[key], value)
            else:
                target[key] = value
    
    def _load_from_env(self):
        if os.getenv('SCRAPER_TIMEOUT'):
            self.config['scraper']['timeout'] = int(os.getenv('SCRAPER_TIMEOUT'))
        if os.getenv('SCRAPER_USE_PLAYWRIGHT'):
            self.config['scraper']['use_playwright'] = os.getenv('SCRAPER_USE_PLAYWRIGHT').lower() == 'true'
    
    def load_proxy_from_json(self, proxy_json_path: str = "proxy.json") -> Optional[str]:
        if not self.get('proxy.enabled', True):
            return None
        
        json_path = Path(proxy_json_path)
        if not json_path.exists():
            return self.get('proxy.url')
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                proxy_data = json.load(f)
            
            proxy = proxy_data.get('proxy', {})
            username = proxy.get('username')
            password = proxy.get('password')
            hostname = proxy.get('hostname')
            
            if username and password and hostname:
                port = proxy.get('port', {}).get('http', 65534)
                if ':' in hostname:
                    hostname = hostname.split(':')[0]
                return f"http://{username}:{password}@{hostname}:{port}"
        except Exception as e:
            print(f"[WARNING] Failed to load proxy.json: {e}")
        
        return self.get('proxy.url')
    
    def get_user_agents_for_os(self, os_name: str = None) -> List[str]:
        if os_name is None:
            system = platform.system().lower()
            if system == 'windows':
                os_name = 'windows'
            elif system == 'darwin':
                os_name = 'macos'
            elif system == 'linux':
                os_name = 'linux'
            else:
                os_name = 'windows'
        
        agents = self.user_agents_by_os.get(os_name, [])
        
        if not agents and os_name != 'windows':
            agents = self.user_agents_by_os.get('windows', [])
        
        if not agents:
            agents = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"]

        print("agents", agents)
        
        return agents
    
    def get(self, key: str, default=None):
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value
    
    @property
    def use_playwright(self) -> bool:
        return self.get('scraper.use_playwright', False)
    
    @property
    def timeout(self) -> int:
        return self.get('scraper.timeout', 10)
    
    @property
    def max_retries(self) -> int:
        return self.get('scraper.max_retries', 2)
    
    @property
    def max_concurrent(self) -> int:
        return self.get('scraper.max_concurrent', 10)
    
    @property
    def playwright_headless(self) -> bool:
        return self.get('playwright.headless', True)
    
    @property
    def playwright_timeout(self) -> int:
        return self.get('playwright.timeout', 15000)
    
    @property
    def retry_without_compression(self) -> bool:
        """Check if retry without compression is enabled."""
        return self.get('scraper.retry_without_compression', True)
    
    @property
    def allow_direct_fallback(self) -> bool:
        """Check if direct connection (without proxy) is allowed as fallback."""
        return self.get('scraper.allow_direct_fallback', False)

    @property
    def use_selenium(self) -> bool:
        """Check if Selenium should be used as fallback."""
        return self.get('scraper.use_selenium', False)

    @property
    def selenium_headless(self) -> bool:
        return self.get('selenium.headless', True)

    @property
    def selenium_timeout(self) -> int:
        return self.get('selenium.timeout', 30)

    @property
    def selenium_incognito(self) -> bool:
        return self.get('selenium.incognito', True)
    
    @property
    def min_content_length(self) -> int:
        """Minimum content length to consider as good content."""
        return self.get('scraper.min_content_length', 500)

_instance = None

def get_config(config_dir: str = "config_files") -> Config:
    global _instance
    if _instance is None:
        _instance = Config(config_dir)
    return _instance