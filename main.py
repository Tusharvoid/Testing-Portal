# Streamlit Cloud package installer for main.py
import os
import sys

# Fix for inotify limits and Python path on Streamlit Cloud
if os.path.exists("/mount/src"):
    print("🔍 Main.py on Streamlit Cloud - applying optimizations...")
    os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"
    os.environ["STREAMLIT_RUNNER_POST_PROCESS_ENABLED"] = "false"
    
    # Fix Python path for Streamlit Cloud packages
    user_site = "/home/appuser/.local/lib/python3.13/site-packages"
    if user_site not in sys.path and os.path.exists(user_site):
        sys.path.insert(0, user_site)
        print(f"✅ Added {user_site} to Python path")
    
    try:
        from streamlit_packages import ensure_packages
        ensure_packages()
    except Exception as e:
        print(f"⚠️ Package installer error in main.py: {e}")

import json
import time
import traceback

# Enhanced import with error handling for Streamlit Cloud
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from webdriver_manager.chrome import ChromeDriverManager
    
    # Also try Firefox as fallback
    try:
        from selenium.webdriver.firefox.options import Options as FirefoxOptions
        from selenium.webdriver.firefox.service import Service as FirefoxService
        from webdriver_manager.firefox import GeckoDriverManager
        FIREFOX_AVAILABLE = True
    except ImportError:
        FIREFOX_AVAILABLE = False
        
    SELENIUM_AVAILABLE = True
    print("✅ Selenium imported successfully")
except ImportError as e:
    print(f"❌ Selenium import failed: {e}")
    SELENIUM_AVAILABLE = False
    FIREFOX_AVAILABLE = False

# Import chrome setup
try:
    from chrome_setup import get_chrome_paths
    print("✅ Chrome setup imported successfully")
except ImportError as e:
    print(f"⚠️ Chrome setup import failed: {e}")
    def get_chrome_paths():
        return None, None


def find_element(driver, target):
    # Recognize locator prefixes used by Selenium IDE
    if not target:
        return None
    if target.startswith('id='):
        return driver.find_element(By.ID, target[3:])
    if target.startswith('css='):
        return driver.find_element(By.CSS_SELECTOR, target[4:])
    if target.startswith('xpath='):
        return driver.find_element(By.XPATH, target[6:])
    if target.startswith('name='):
        return driver.find_element(By.NAME, target[5:])
    if target.startswith('link='):
        return driver.find_element(By.LINK_TEXT, target[5:])
    if target.startswith('class='):
        return driver.find_element(By.CLASS_NAME, target[6:])
    # fallback: try CSS selector then id
    try:
        return driver.find_element(By.CSS_SELECTOR, target)
    except Exception:
        try:
            return driver.find_element(By.ID, target)
        except Exception:
            raise


def run_side_test(side_file_path):
    """Run SIDE test with enhanced error handling for Streamlit Cloud."""
    
    if not SELENIUM_AVAILABLE:
        error_msg = "❌ Selenium is not available. Cannot run tests."
        print(error_msg)
        with open('selenium_error.log', 'w') as f:
            f.write(error_msg + "\n")
            f.write("Please check Streamlit Cloud logs for package installation issues.\n")
        return
    
    print(f"🔍 Loading SIDE file: {side_file_path}")
    try:
        with open(side_file_path, 'r') as f:
            side_data = json.load(f)
        print(f"✅ SIDE file loaded successfully with {len(side_data.get('tests', []))} tests")
    except Exception as e:
        print(f"❌ Failed to load SIDE file: {e}")
        return

    # Setup headless Chrome with optimized options for Streamlit Cloud
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-web-security')
    options.add_argument('--disable-features=VizDisplayCompositor')
    options.add_argument('--remote-debugging-port=9222')
    options.add_argument('--window-size=1920,1080')
    
    # Additional options for Streamlit Cloud compatibility
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--disable-background-timer-throttling')
    options.add_argument('--disable-renderer-backgrounding')
    options.add_argument('--disable-backgrounding-occluded-windows')
    options.add_argument('--disable-ipc-flooding-protection')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-default-apps')
    options.add_argument('--disable-hang-monitor')
    options.add_argument('--disable-prompt-on-repost')
    options.add_argument('--disable-domain-reliability')
    options.add_argument('--disable-component-extensions-with-background-pages')
    
    # Memory and process optimizations
    options.add_argument('--memory-pressure-off')
    options.add_argument('--max_old_space_size=4096')
    options.add_argument('--single-process')  # Important for resource-constrained environments
    
    # Enhanced Chrome setup for Streamlit Cloud with auto-download
    driver = None
    try:
        print("🔍 Setting up Chrome and ChromeDriver...")
        
        # Strategy 1: Try with simple Chrome options first (most compatible)
        try:
            print("🔄 Attempting simple Chrome setup...")
            simple_options = Options()
            simple_options.add_argument('--headless=new')
            simple_options.add_argument('--no-sandbox')
            simple_options.add_argument('--disable-dev-shm-usage')
            simple_options.add_argument('--disable-gpu')
            simple_options.add_argument('--single-process')
            
            driver = webdriver.Chrome(options=simple_options)
            print("✅ Chrome WebDriver initialized with simple options")
            
        except Exception as simple_error:
            print(f"⚠️ Simple setup failed: {simple_error}")
            
            # Strategy 2: Try with webdriver-manager
            try:
                print("🔄 Attempting webdriver-manager setup...")
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
                print("✅ Chrome WebDriver initialized with webdriver-manager")
                
            except Exception as wdm_error:
                print(f"⚠️ WebDriver-manager failed: {wdm_error}")
                
                # Strategy 3: Try with downloaded Chrome (if available)
                chrome_binary, driver_binary = get_chrome_paths()
                
                if chrome_binary and driver_binary:
                    print(f"🔄 Attempting custom Chrome setup...")
                    print(f"   Chrome: {chrome_binary}")
                    print(f"   ChromeDriver: {driver_binary}")
                    
                    try:
                        # Set Chrome binary path
                        options.binary_location = chrome_binary
                        
                        # Try without explicit service first
                        driver = webdriver.Chrome(options=options)
                        print("✅ Chrome WebDriver initialized with custom Chrome (auto-service)")
                        
                    except Exception as custom_error:
                        print(f"⚠️ Custom Chrome failed: {custom_error}")
                        
                        # Final fallback - try minimal setup
                        try:
                            print("🔄 Final fallback: minimal Chrome setup...")
                            minimal_options = Options()
                            minimal_options.add_argument('--headless')
                            minimal_options.add_argument('--no-sandbox')
                            minimal_options.add_argument('--disable-dev-shm-usage')
                            
                            driver = webdriver.Chrome(options=minimal_options)
                            print("✅ Chrome WebDriver initialized with minimal setup")
                            
                        except Exception as minimal_error:
                            print(f"❌ All Chrome setup methods failed: {minimal_error}")
                            
                            # Ultimate fallback: Try Firefox if available
                            if FIREFOX_AVAILABLE:
                                try:
                                    print("🔄 Ultimate fallback: Attempting Firefox setup...")
                                    firefox_options = FirefoxOptions()
                                    firefox_options.add_argument('--headless')
                                    firefox_options.add_argument('--no-sandbox')
                                    
                                    # Try Firefox with webdriver-manager
                                    firefox_service = FirefoxService(GeckoDriverManager().install())
                                    driver = webdriver.Firefox(service=firefox_service, options=firefox_options)
                                    print("✅ Firefox WebDriver initialized as Chrome fallback")
                                    
                                except Exception as firefox_error:
                                    print(f"❌ Firefox fallback also failed: {firefox_error}")
                                    raise firefox_error
                            else:
                                raise minimal_error
                else:
                    print("❌ No Chrome binaries available and all methods failed")
                    raise Exception("No Chrome setup method succeeded")
                    
    except Exception as e:
        print(f"Chrome setup error: {e}")
        print("❌ Cannot initialize Chrome WebDriver - will attempt alternative approaches")
        raise e

    try:
        for t_index, test in enumerate(side_data.get('tests', [])):
            print(f"Running test: {test.get('name', t_index)}")
            for s_index, cmd in enumerate(test.get('commands', [])):
                command = (cmd.get('command') or '').strip()
                target = cmd.get('target', '')
                value = cmd.get('value', '')
                print(f"-> Step {s_index+1}: {command} target={target} value={value}")
                try:
                    if command.lower() == 'open':
                        url = target
                        driver.get(url)
                        time.sleep(1)
                    elif command.lower() in ('type', 'settext'):
                        el = find_element(driver, target)
                        el.clear()
                        el.send_keys(value)
                        time.sleep(0.3)
                    elif command.lower() in ('sendkeys',):
                        el = find_element(driver, target)
                        el.send_keys(value)
                        time.sleep(0.3)
                    elif command.lower() == 'click':
                        el = find_element(driver, target)
                        el.click()
                        time.sleep(0.5)
                    elif command.lower() == 'pause':
                        # value in milliseconds in SIDE usually
                        ms = int(value) if value else 1000
                        time.sleep(ms / 1000.0)
                    elif command.lower() == 'customscreenshot':
                        # save step-specific and global screenshot
                        step_file = f"screenshot_t{t_index+1}_s{s_index+1}.png"
                        driver.save_screenshot(step_file)
                        driver.save_screenshot('screenshot.png')
                        print(f"Saved screenshot: {step_file}")
                    else:
                        print(f"Unknown command: {command} - skipping")
                except Exception as e:
                    print(f"Error on step {s_index+1}: {e}")
                    traceback.print_exc()
                    # continue to next step
        print("Test run finished")
    finally:
        driver.quit()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python main.py <path_to_side_file>')
        sys.exit(1)
    run_side_test(sys.argv[1])