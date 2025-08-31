"""
Streamlit Cloud Package Installer
This module ensures all required packages are installed when the app starts on Streamlit Cloud
"""

import subprocess
import sys
import os
import importlib
import site

# Fix Python path for Streamlit Cloud
if os.path.exists("/mount/src"):
    # Add common Streamlit Cloud package locations to Python path
    user_site = "/home/appuser/.local/lib/python3.13/site-packages"
    if user_site not in sys.path and os.path.exists(user_site):
        sys.path.insert(0, user_site)
        print(f"✅ Added {user_site} to Python path")
    
    # Also try the site-packages approach
    try:
        import site
        site.addsitedir(user_site)
    except:
        pass

def install_and_import(package_name, import_name=None):
    """Install package if not available and import it."""
    if import_name is None:
        import_name = package_name.split("==")[0]  # Remove version if present
    
    try:
        # Try to import the package
        importlib.import_module(import_name)
        print(f"✅ {package_name} is already available")
        return True
    except ImportError:
        print(f"❌ {package_name} not found, installing...")
        
        try:
            # Install the package with safer options
            cmd = [
                sys.executable, "-m", "pip", "install", 
                "--user", "--no-warn-script-location", 
                "--prefer-binary",       # Use wheels when possible
                package_name
            ]
            
            subprocess.check_call(cmd, timeout=300)  # 5 minute timeout
            
            # Force reload of site packages
            if os.path.exists("/mount/src"):
                user_site = "/home/appuser/.local/lib/python3.13/site-packages"
                if user_site not in sys.path:
                    sys.path.insert(0, user_site)
                
                # Invalidate import cache
                importlib.invalidate_caches()
            
            # Try importing again
            importlib.import_module(import_name)
            print(f"✅ {package_name} installed and imported successfully")
            return True
            
        except subprocess.TimeoutExpired:
            print(f"⏰ {package_name} installation timed out")
            return False
        except Exception as e:
            print(f"❌ Failed to install {package_name}: {e}")
            # Try without version constraints as fallback
            try:
                base_package = package_name.split("==")[0]
                subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "--prefer-binary", base_package], timeout=120)
                
                # Force reload again
                if os.path.exists("/mount/src"):
                    importlib.invalidate_caches()
                
                importlib.import_module(import_name)
                print(f"✅ {base_package} (latest version) installed successfully")
                return True
            except:
                print(f"❌ Complete failure installing {package_name}")
                return False

def ensure_packages():
    """Ensure all required packages are installed for Streamlit Cloud."""
    print("🔍 Checking required packages for Streamlit Cloud...")
    
    # Essential packages for the Testing Portal (excluding problematic ones)
    packages = [
        ("selenium==4.15.0", "selenium"),
        ("webdriver-manager==4.0.1", "webdriver_manager"),
        ("pymongo==4.6.0", "pymongo"),
        ("requests==2.31.0", "requests"),
        ("psutil==5.9.4", "psutil"),
        ("beautifulsoup4==4.12.2", "bs4"),
        # Note: lxml removed - causes compilation errors on Streamlit Cloud
    ]
    
    success_count = 0
    for package_spec, import_name in packages:
        if install_and_import(package_spec, import_name):
            success_count += 1
    
    print(f"📊 Package Status: {success_count}/{len(packages)} packages available")
    
    if success_count == len(packages):
        print("🚀 All packages ready for Testing Portal!")
        return True
    else:
        print("⚠️  Some packages failed to install - check logs above")
        return False

# Auto-run when imported
if __name__ == "__main__" or os.path.exists("/mount/src"):
    # Only run on Streamlit Cloud or when explicitly called
    ensure_packages()
