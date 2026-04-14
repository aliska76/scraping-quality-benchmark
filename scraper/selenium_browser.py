"""
Selenium fetcher with proxy authentication via Chrome extension.
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from typing import Optional, Dict, Tuple, List
from scraper.base import BaseFetcher
import asyncio
import time
import os
import zipfile
import shutil


class SeleniumFetcher(BaseFetcher):
    """
    Selenium fetcher with proxy authentication via Chrome extension.
    """
    
    def __init__(
        self,
        proxy_config: Optional[Dict[str, str]] = None,
        headless: bool = True,
        timeout: int = 30,
        incognito: bool = True,
        user_agents: Optional[List[str]] = None
    ):
        self.proxy_config = proxy_config
        self.headless = headless
        self.timeout = timeout
        self.incognito = incognito
        self.user_agents = user_agents or [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
        ]
        self._ua_index = 0
    
    def _get_next_user_agent(self) -> str:
        ua = self.user_agents[self._ua_index % len(self.user_agents)]
        self._ua_index += 1
        return ua
    
    def _reset_ua_index(self):
        self._ua_index = 0
    
    def _create_proxy_extension(self, proxy_server: str, username: str, password: str, temp_dir: str) -> str:
        """Create a Chrome extension for proxy authentication."""
        manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Chrome Proxy",
            "permissions": [
                "proxy",
                "tabs",
                "unlimitedStorage",
                "storage",
                "<all_urls>",
                "webRequest",
                "webRequestBlocking"
            ],
            "background": {
                "scripts": ["background.js"]
            },
            "minimum_chrome_version": "22.0.0"
        }
        """
        
        background_js = f"""
        var config = {{
                mode: "fixed_servers",
                rules: {{
                  singleProxy: {{
                    scheme: "http",
                    host: "{proxy_server.split(':')[0]}",
                    port: parseInt("{proxy_server.split(':')[1]}")
                  }},
                  bypassList: ["localhost"]
                }}
              }};
        
        chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
        
        function callbackFn(details) {{
            return {{
                authCredentials: {{
                    username: "{username}",
                    password: "{password}"
                }}
            }};
        }}
        
        chrome.webRequest.onAuthRequired.addListener(
                    callbackFn,
                    {{urls: ["<all_urls>"]}},
                    ['blocking']
        );
        """
        
        # Create extension directory
        extension_dir = os.path.join(temp_dir, "proxy_auth_extension")
        os.makedirs(extension_dir, exist_ok=True)
        
        with open(os.path.join(extension_dir, "manifest.json"), "w") as f:
            f.write(manifest_json)
        with open(os.path.join(extension_dir, "background.js"), "w") as f:
            f.write(background_js)
        
        # Create zip file
        zip_path = os.path.join(temp_dir, "proxy_auth.zip")
        with zipfile.ZipFile(zip_path, 'w') as zp:
            zp.write(os.path.join(extension_dir, "manifest.json"), "manifest.json")
            zp.write(os.path.join(extension_dir, "background.js"), "background.js")
        
        return zip_path
    
    def _cleanup_temp_dir(self, temp_dir: str):
        """Clean up temporary directory."""
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                print(f"[SELENIUM] Failed to cleanup {temp_dir}: {e}")
    
    def _create_driver(self, user_agent: str = None):
        """Create a Chrome driver with proxy extension."""
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument('--headless')
        if self.incognito:
            chrome_options.add_argument('--incognito')
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        ua = user_agent or self._get_next_user_agent()
        chrome_options.add_argument(f'user-agent={ua}')
        
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        
        # Create temp directory for extension
        import tempfile
        temp_dir = tempfile.mkdtemp(prefix="selenium_proxy_")
        
        # Add proxy extension if credentials provided
        extension_path = None
        if self.proxy_config:
            server = self.proxy_config.get('server', '')
            username = self.proxy_config.get('username', '')
            password = self.proxy_config.get('password', '')
            
            if server and username and password:
                server_clean = server.replace('http://', '').replace('https://', '')
                extension_path = self._create_proxy_extension(server_clean, username, password, temp_dir)
                chrome_options.add_extension(extension_path)
            elif server:
                chrome_options.add_argument(f'--proxy-server={server}')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(self.timeout)
        
        # Store temp_dir and extension_path for cleanup
        driver._temp_dir = temp_dir
        driver._extension_path = extension_path
        
        return driver, ua
    
    async def fetch(self, url: str, timeout: int = None) -> Tuple[int, str]:
        """Fetch a URL using Selenium."""
        timeout_sec = timeout or self.timeout
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._sync_fetch,
                url,
                timeout_sec
            )
            return result
        except Exception as e:
            print(f"[SELENIUM] Error: {type(e).__name__}: {e}")
            return 500, ""
    
    def _sync_fetch(self, url: str, timeout: int) -> Tuple[int, str]:
        """Synchronous fetch (runs in thread pool)."""
        driver = None
        try:
            driver, ua = self._create_driver()
            print(f"[SELENIUM] Fetching {url[:70]}...")
            
            driver.get(url)
            time.sleep(3)
            
            content = driver.page_source
            
            if content:
                print(f"[SELENIUM] Got {len(content)} chars")
                return 200, content
            else:
                print(f"[SELENIUM] Empty content")
                return 204, ""
                
        except TimeoutException:
            print(f"[SELENIUM] Timeout for {url}")
            return 408, ""
        except WebDriverException as e:
            print(f"[SELENIUM] WebDriver error: {e}")
            return 500, ""
        except Exception as e:
            print(f"[SELENIUM] Error: {type(e).__name__}: {e}")
            return 500, ""
        finally:
            if driver:
                # Cleanup temp files
                temp_dir = getattr(driver, '_temp_dir', None)
                if temp_dir:
                    self._cleanup_temp_dir(temp_dir)
                driver.quit()
    
    async def fetch_with_retry(self, url: str, max_attempts: int = 2, timeout: int = None) -> Tuple[int, str]:
        """Fetch with User-Agent rotation retries."""
        self._reset_ua_index()
        
        for attempt in range(max_attempts):
            print(f"[SELENIUM] Attempt {attempt + 1}/{max_attempts}")
            status, content = await self.fetch(url, timeout=timeout)
            
            if status in [200, 204]:
                return status, content
            
            print(f"[SELENIUM] Attempt {attempt + 1} failed (status {status}), retrying...")
        
        return status, content