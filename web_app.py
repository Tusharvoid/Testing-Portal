# Streamlit Cloud package installer - MUST BE FIRST
import os
import sys
import warnings

# Comprehensive warning suppression for deprecated Streamlit parameters
warnings.filterwarnings("ignore", message=".*use_column_width.*")
warnings.filterwarnings("ignore", message=".*deprecated.*", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*deprecated.*", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*use_column_width.*", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*use_column_width.*", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*use_column_width.*", category=UserWarning)

# Set environment variable to suppress Streamlit warnings globally
os.environ['STREAMLIT_SUPPRESS_DEPRECATION_WARNINGS'] = 'true'
os.environ['PYTHONWARNINGS'] = 'ignore::DeprecationWarning,ignore::FutureWarning'

# Fix for inotify limits and Python path on Streamlit Cloud
if os.path.exists("/mount/src"):
    print("🔍 Detected Streamlit Cloud environment - applying optimizations...")
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
        print(f"⚠️ Package installer error: {e}")

import streamlit as st
import json
import re
import tempfile
import subprocess
import zipfile
import io
import time
import base64
import gc  # Garbage collection for memory management
from typing import Dict, List
from db_manager import save_run, get_recent_runs, delete_all_runs, delete_runs_for_app

# Custom warning override to prevent UI warnings
def custom_showwarning(message, category, filename, lineno, file=None, line=None):
    """Custom warning handler that suppresses deprecated parameter warnings."""
    msg_str = str(message)
    if 'use_column_width' in msg_str or 'deprecated' in msg_str.lower():
        return  # Suppress these warnings completely
    # Show other warnings normally
    import warnings
    warnings._showwarning_orig(message, category, filename, lineno, file, line)

# Override the warning display function
import warnings
if hasattr(warnings, '_showwarning_orig'):
    pass  # Already overridden
else:
    warnings._showwarning_orig = warnings.showwarning
    warnings.showwarning = custom_showwarning

# Optional imports for enhanced monitoring
try:
    import psutil  # Process and system monitoring
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

# Check selenium availability
try:
    import selenium
    SELENIUM_AVAILABLE = True
    selenium_version = selenium.__version__
except ImportError:
    SELENIUM_AVAILABLE = False
    selenium_version = "Not installed"

# System status logging
import logging
logger = logging.getLogger(__name__)
logger.info(f"🔍 System Status Check:")
logger.info(f"  - Selenium: {'✅ Available' if SELENIUM_AVAILABLE else '❌ Missing'} (v{selenium_version})")
logger.info(f"  - Psutil: {'✅ Available' if PSUTIL_AVAILABLE else '❌ Missing'}")
logger.info(f"  - Python: {os.sys.version}")
logger.info(f"  - Working Directory: {os.getcwd()}")

if not SELENIUM_AVAILABLE:
    logger.error("❌ CRITICAL: Selenium not available - tests will fail!")
    logger.info("💡 Check requirements.txt and Streamlit Cloud package installation")

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================
# Additional warning suppression at Streamlit level
try:
    import streamlit.logger
    import logging
    
    # Create a custom filter for Streamlit's logger
    class DeprecationWarningFilter(logging.Filter):
        def filter(self, record):
            # Filter out deprecation warnings from logs
            message = getattr(record, 'getMessage', lambda: '')()
            return not ('use_column_width' in message or 'deprecated' in message.lower())
    
    # Apply filter to Streamlit's loggers
    for logger_name in ['streamlit', 'streamlit.web', 'streamlit.runtime']:
        try:
            logger = logging.getLogger(logger_name)
            logger.addFilter(DeprecationWarningFilter())
        except:
            pass
except:
    pass

st.set_page_config(
    page_title="Testing Portal", 
    page_icon="⚡", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Performance monitoring
@st.cache_data(ttl=60)
def get_system_stats():
    """Get system performance statistics."""
    if not PSUTIL_AVAILABLE:
        return {'memory_percent': 0, 'memory_available': 0, 'cpu_percent': 0}
    
    try:
        memory = psutil.virtual_memory()
        return {
            'memory_percent': memory.percent,
            'memory_available': memory.available // (1024**2),  # MB
            'cpu_percent': psutil.cpu_percent(interval=1)
        }
    except:
        return {'memory_percent': 0, 'memory_available': 0, 'cpu_percent': 0}

# Cache static data to improve performance
@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_cached_apps():
    """Get cached list of applications."""
    return list_apps_from_history()

@st.cache_data(ttl=60)  # Cache for 1 minute  
def get_cached_recent_runs(limit=50):
    """Get cached recent runs."""
    try:
        return get_recent_runs(limit)
    except:
        return []

# Custom CSS for professional styling
st.markdown("""
<style>
    .section-header {
        font-size: 1.5rem;
        font-weight: 500;
        color: #374151;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
    }
    .sidebar-header {
        font-size: 1.75rem;
        font-weight: 600;
        color: #1f2937;
        margin-bottom: 1rem;
    }
    .status-ok {
        color: #059669;
        font-weight: 600;
    }
    .status-error {
        color: #dc2626;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def safe_st_image(image, caption=None, use_container_width=True, **kwargs):
    """Safe wrapper for st.image that ensures no deprecated parameters are used."""
    # Remove any deprecated parameters that might be passed
    safe_kwargs = {k: v for k, v in kwargs.items() 
                   if k not in ['use_column_width']}
    
    # Ensure we use the correct parameter
    return st.image(
        image=image,
        caption=caption,
        use_container_width=use_container_width,
        **safe_kwargs
    )

def safe_rerun():
    """Compatibility wrapper for rerunning a Streamlit script."""
    try:
        if hasattr(st, 'experimental_rerun'):
            st.experimental_rerun()
        else:
            st.stop()
    except Exception:
        st.stop()

# ============================================================================
# CORE FUNCTIONS
# ============================================================================
def parse_side(side_bytes: bytes) -> Dict:
    """Parse SIDE file bytes into dictionary."""
    return json.loads(side_bytes)

def extract_params_and_steps(side_data: Dict):
    """Extract parameters and steps from SIDE data."""
    params, steps = [], []
    for t_index, test in enumerate(side_data.get('tests', [])):
        for s_index, cmd in enumerate(test.get('commands', [])):
            step_desc = f"Test {t_index+1} - Step {s_index+1}: {cmd.get('command')} {cmd.get('target','')}"
            steps.append(step_desc)
            
            if cmd.get('command') in ['type', 'sendKeys', 'setText']:
                params.append({
                    'test': t_index,
                    'step': s_index,
                    'name': cmd.get('target', ''),
                    'value': cmd.get('value', '')
                })
    return params, steps

def apply_param_map_and_screenshots(side_data: Dict, param_map: Dict, screenshot_steps: List[str]):
    """Apply parameter mapping and insert screenshot commands."""
    for t_index, test in enumerate(side_data.get('tests', [])):
        # Update parameter values
        for s_index, cmd in enumerate(test.get('commands', [])):
            key = f"t{t_index}_s{s_index}"
            if key in param_map and param_map[key] is not None:
                cmd['value'] = param_map[key]
        
        # Insert screenshot commands
        insert_indices = [
            s_index for s_index, cmd in enumerate(test.get('commands', []))
            if f"Test {t_index+1} - Step {s_index+1}: {cmd.get('command')} {cmd.get('target','')}" in screenshot_steps
        ]
        
        for idx in sorted(insert_indices, reverse=True):
            test['commands'].insert(idx+1, {
                'command': 'customScreenshot', 
                'target': '', 
                'value': ''
            })

def list_apps_from_history():
    """Get list of unique app names from database."""
    try:
        runs = get_recent_runs(200)
        names = []
        for r in runs:
            name = r.get('app_name') or 'Unnamed'
            if name not in names and name != 'Unnamed':
                names.append(name)
        return names
    except:
        return []

def ping_url(url: str, timeout: int = 5):
    """Ping a URL and return status information."""
    if not url:
        return False, None, 'No URL provided'
    
    try:
        import requests
        start = time.time()
        response = requests.get(url, timeout=timeout)
        latency = (time.time() - start) * 1000.0
        return response.status_code < 400, latency, response.status_code
    except Exception as e:
        return False, None, str(e)

def run_test_and_get_results(side_data, app_name, test_type="test"):
    """Execute test and return ZIP results with optimizations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        side_path = os.path.join(tmpdir, f"{app_name or 'app'}_{test_type}.side")
        with open(side_path, 'w') as f:
            json.dump(side_data, f, separators=(',', ':'))  # Compact JSON
        
        log_path = os.path.join(tmpdir, 'run.log')
        
        # Change to the temp directory so screenshots are created there
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        
        try:
            # Use optimized Python execution for different environments
            main_script = os.path.join(original_cwd, "main.py")
            
            # Try different Python paths for different environments
            python_candidates = [
                os.path.join(original_cwd, "venv", "bin", "python"),  # Local venv
                "python3",  # System Python 3
                "python"    # System Python
            ]
            
            python_cmd = None
            for candidate in python_candidates:
                try:
                    if os.path.exists(candidate) or candidate in ["python3", "python"]:
                        python_cmd = candidate
                        break
                except:
                    continue
            
            if not python_cmd:
                python_cmd = "python3"  # Fallback
            
            # Run with timeout and optimized settings
            with open(log_path, 'w') as logf:
                process = subprocess.run(
                    [python_cmd, main_script, side_path], 
                    stdout=logf, 
                    stderr=subprocess.STDOUT,
                    timeout=300,  # 5 minute timeout
                    env=dict(os.environ, PYTHONUNBUFFERED='1')
                )
        except subprocess.TimeoutExpired:
            with open(log_path, 'a') as logf:
                logf.write("\n\nERROR: Test execution timed out after 5 minutes")
        except Exception as e:
            with open(log_path, 'a') as logf:
                logf.write(f"\n\nERROR: {str(e)}")
        finally:
            os.chdir(original_cwd)
        
        # Create optimized results ZIP
        files_to_zip = []
        
        # Add log file if it exists and has content
        if os.path.exists(log_path) and os.path.getsize(log_path) > 0:
            files_to_zip.append(log_path)
        
        # Add SIDE file
        if os.path.exists(side_path):
            files_to_zip.append(side_path)
        
        # Add screenshots (limit to reasonable number)
        screenshot_count = 0
        for filename in os.listdir(tmpdir):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')) and screenshot_count < 20:
                screenshot_path = os.path.join(tmpdir, filename)
                files_to_zip.append(screenshot_path)
                screenshot_count += 1
        
        # Create compressed ZIP
        zip_path = os.path.join(tmpdir, 'results.zip')
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for fpath in files_to_zip:
                if os.path.exists(fpath):
                    arcname = os.path.basename(fpath)
                    zf.write(fpath, arcname)
        
        # Return ZIP bytes
        if os.path.exists(zip_path):
            with open(zip_path, 'rb') as zf:
                return zf.read()
        else:
            # Create minimal ZIP if main ZIP creation failed
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr('error.txt', 'Test execution failed - no results generated')
            buffer.seek(0)
            return buffer.getvalue()

# ============================================================================
# SIDEBAR CONFIGURATION
# ============================================================================
with st.sidebar:
    st.markdown('<h2 class="sidebar-header">Testing Platform</h2>', unsafe_allow_html=True)
    st.markdown("---")
    
    # Database Management
    if st.button('Clear All Data', key='delete_all_db', help="Delete all test runs from database"):
        deleted = delete_all_runs()
        st.warning(f"Deleted {deleted} runs from database")
    
    # App Management
    st.markdown("### Applications")
    apps = list_apps_from_history()
    new_app_name = st.text_input("Create new application", key="sidebar_new_app", placeholder="Enter application name")
    
    # App selection
    options = [new_app_name] + [a for a in apps if a != new_app_name] if new_app_name else apps
    selected_app = st.selectbox("Select application", options=options, index=0, key="sidebar_selected_app") if options else None

    # Delete app option
    if selected_app and st.button("Delete Application", key="del_app_btn", help="Remove all runs for this application"):
        deleted = delete_runs_for_app(selected_app)
        st.info(f"Deleted {deleted} runs for application '{selected_app}'")
        safe_rerun()

    # User Parameters
    st.markdown("### Global Parameters")
    user_params = {}
    param_count = st.number_input("Number of parameters", min_value=0, max_value=20, value=0, key="param_count")
    
    for i in range(param_count):
        col1, col2 = st.columns(2)
        with col1:
            k = st.text_input(f"Key {i+1}", key=f"user_param_name_{i}", placeholder="parameter_name")
        with col2:
            v = st.text_input(f"Value {i+1}", key=f"user_param_value_{i}", placeholder="parameter_value")
        if k:
            user_params[k] = v
    
    st.markdown("---")
    st.caption("Selenium Testing Platform v1.0")

# ============================================================================
# MAIN APPLICATION
# ============================================================================


def render_app_tab(selected_app):
    """Render the main application interface for the selected app."""
    
    # Initialize session state for new SIDE files
    if 'new_side' not in st.session_state:
        st.session_state['new_side'] = {
            'id': 'new-side',
            'version': '1.0',
            'name': selected_app or 'New SIDE',
            'tests': [],
            'suites': [],
            'urls': [],
            'plugins': []
        }
    
    # Update the SIDE file name if app changes
    new_side = st.session_state['new_side']
    if new_side['name'] != (selected_app or 'New SIDE'):
        new_side['name'] = selected_app or 'New SIDE'
        st.session_state['new_side'] = new_side
    
    st.markdown(f'<h2 class="section-header">Application: {selected_app}</h2>', unsafe_allow_html=True)
    
    # ========================================================================
    # URL MONITORING SECTION
    # ========================================================================
    with st.expander("URL Monitoring", expanded=False):
        url_key = f"app_url_{selected_app}"
        if url_key not in st.session_state:
            st.session_state[url_key] = ''
        
        app_url = st.text_input('Application URL', key=url_key, placeholder="https://example.com")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button('Ping Now', key=f'ping_now_{selected_app}'):
                if app_url:
                    ok, latency, info = ping_url(app_url)
                    if ok:
                        st.markdown(f'<span class="status-ok">✓ Status: {info} ({latency:.0f} ms)</span>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<span class="status-error">✗ Down: {info}</span>', unsafe_allow_html=True)
                else:
                    st.warning("Please enter a URL first")
        
        with col2:
            checks = st.number_input('Monitor checks', min_value=1, max_value=50, value=5, key=f'mon_checks_{selected_app}')
        
        with col3:
            if st.button('Start Monitor', key=f'start_mon_{selected_app}'):
                if app_url:
                    with st.expander('Monitor Results', expanded=True):
                        progress_bar = st.progress(0)
                        results_placeholder = st.empty()
                        
                        for i in range(int(checks)):
                            ok, latency, info = ping_url(app_url)
                            timestamp = time.strftime('%H:%M:%S')
                            
                            if ok:
                                results_placeholder.markdown(f'<span class="status-ok">{timestamp} — OK — {info} ({latency:.0f} ms)</span>', unsafe_allow_html=True)
                            else:
                                results_placeholder.markdown(f'<span class="status-error">{timestamp} — DOWN — {info}</span>', unsafe_allow_html=True)
                            
                            progress_bar.progress((i + 1) / checks)
                            time.sleep(0.5)
                else:
                    st.warning("Please enter a URL first")

    # ========================================================================
    # SIDE FILE MANAGEMENT
    # ========================================================================
    st.markdown('<h3 class="section-header">Test File Management</h3>', unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["Upload & Execute", "Manual Editor", "Test History"])
    
    with tab1:
        st.markdown("### Upload SIDE File")
        uploaded_file = st.file_uploader(
            f"Upload Selenium IDE (.side) file for {selected_app}", 
            type=["side"], 
            key=f"upload_{selected_app}"
        )
        
        if uploaded_file:
            try:
                uploaded_bytes = uploaded_file.read()
                side_data = parse_side(uploaded_bytes)
                st.success("File parsed successfully!")
                
                # Store uploaded data in session state for use in manual editor
                st.session_state[f'uploaded_side_{selected_app}'] = side_data
                
                side_params, screenshot_steps = extract_params_and_steps(side_data)
                param_map = {}  # Initialize param_map regardless of side_params
                screenshot_choices = []  # Initialize screenshot_choices
                
                if side_params:
                    st.markdown("#### Parameter Mapping")
                    user_params_lc = {k.lower(): v for k, v in user_params.items()}
                    
                    for idx, p in enumerate(side_params):
                        key = f"t{p['test']}_s{p['step']}"
                        default_val = p.get('value', '')
                        
                        # Auto-detect placeholders like ${KEY}
                        try:
                            match = re.search(r"\$\{([^}]+)\}", str(default_val))
                            if match:
                                placeholder = match.group(1).strip().lower()
                                if placeholder in user_params_lc:
                                    default_val = user_params_lc[placeholder]
                        except:
                            pass
                        
                        st.write(f"**Test {p['test']+1} Step {p['step']+1}:** `{p['name']}` (current: `{p['value']}`)")
                        val = st.text_input(
                            f"Value for {p['name']} ({key})", 
                            value=default_val, 
                            key=f"map_{selected_app}_{key}"
                        )
                        param_map[key] = val
                
                if screenshot_steps:
                    st.markdown("#### Screenshot Options")
                    screenshot_choices = st.multiselect(
                        "Select steps to take screenshots after", 
                        screenshot_steps, 
                        key=f"screenshots_{selected_app}"
                    )
                
                # Add button to load into manual editor
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Load into Manual Editor", key=f"load_manual_{selected_app}"):
                        st.session_state['new_side'] = side_data.copy()
                        st.success("SIDE file loaded into manual editor! Check the 'Create Manual' tab.")
                        
                with col2:
                    # Run test button with loading state
                    run_button_key = f"run_main_{selected_app}"
                    
                    if st.button("🚀 Run Test & Save Results", key=run_button_key, use_container_width=True, type="primary"):
                        # Create progress indicators
                        progress_container = st.container()
                        with progress_container:
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            
                        try:
                            # Step 1: Apply configurations
                            status_text.text("⚙️ Applying parameter mapping...")
                            progress_bar.progress(20)
                            
                            if side_params and param_map:
                                apply_param_map_and_screenshots(side_data, param_map, screenshot_choices)
                            elif screenshot_choices:
                                apply_param_map_and_screenshots(side_data, {}, screenshot_choices)
                            
                            # Step 2: Execute test
                            status_text.text("🔄 Running test automation...")
                            progress_bar.progress(40)
                            
                            start_time = time.time()
                            zip_bytes = run_test_and_get_results(side_data, selected_app, "uploaded")
                            execution_time = time.time() - start_time
                            
                            progress_bar.progress(80)
                            status_text.text("💾 Saving results to database...")
                            
                            # Step 3: Save to database
                            try:
                                save_run(
                                    selected_app, user_params, param_map, 
                                    screenshot_choices, zip_bytes, 
                                    original_side_bytes=uploaded_bytes, 
                                    modified_side_bytes=json.dumps(side_data, separators=(',', ':')).encode()
                                )
                                
                                progress_bar.progress(100)
                                status_text.text("✅ Test completed successfully!")
                                
                                # Provide download link
                                st.success(f"Test completed in {execution_time:.2f} seconds!")
                                st.download_button(
                                    "📥 Download Results ZIP", 
                                    zip_bytes, 
                                    f"{selected_app}_results_{int(time.time())}.zip", 
                                    "application/zip",
                                    key=f"download_main_{selected_app}_{int(time.time())}"
                                )
                                
                            except Exception as db_error:
                                st.error(f"Database save error: {str(db_error)}")
                                # Still offer download even if DB save fails
                                st.download_button(
                                    "📥 Download Results ZIP (DB Save Failed)", 
                                    zip_bytes, 
                                    f"{selected_app}_results_{int(time.time())}.zip", 
                                    "application/zip",
                                    key=f"download_main_error_{selected_app}_{int(time.time())}"
                                )
                            
                        except Exception as e:
                            progress_bar.progress(100)
                            status_text.text("❌ Test execution failed")
                            st.error(f"Test execution failed: {str(e)}")
                        
                        finally:
                            # Clear progress indicators after a delay
                            time.sleep(2)
                            progress_container.empty()
                        
            except Exception as e:
                st.error(f"Error processing file: {e}")
    
    with tab2:
        st.markdown("### Create Manual SIDE File")
        
        # Option to load from database
        st.markdown("#### Load from Database")
        try:
            all_runs = get_recent_runs(100)
            db_side_files = [r for r in all_runs if r.get('original_side') and r.get('app_name') == selected_app]
            if db_side_files:
                db_file_names = [f"{r.get('side_name', 'Unnamed')} - {r.get('timestamp', '').strftime('%Y-%m-%d %H:%M') if r.get('timestamp') else 'Unknown'}" for r in db_side_files]
                selected_db_file = st.selectbox("Select SIDE file from database", db_file_names, key=f"db_file_select_{selected_app}")
                
                if st.button("Load from Database", key=f"load_db_{selected_app}"):
                    selected_idx = db_file_names.index(selected_db_file)
                    selected_run = db_side_files[selected_idx]
                    try:
                        db_side_data = json.loads(selected_run['original_side'])
                        st.session_state['new_side'] = db_side_data.copy()
                        st.success("✅ SIDE file loaded from database for editing!")
                        st.info("🔄 Scroll down to see the loaded tests and steps for editing.")
                        # Don't rerun - let the user see the loaded content immediately
                    except Exception as e:
                        st.error(f"Failed to load SIDE file: {e}")
        except Exception as e:
            st.error(f"Failed to fetch database files: {e}")
        
        # Ensure new_side is refreshed from session state after potential loading
        new_side = st.session_state['new_side']
        
        st.markdown("---")
        
        # Show current SIDE file status
        st.markdown("#### Current SIDE File Status")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**SIDE File Name:** {new_side.get('name', 'New SIDE')}")
            st.write(f"**Number of Tests:** {len(new_side.get('tests', []))}")
        with col2:
            if new_side.get('tests'):
                total_commands = sum(len(test.get('commands', [])) for test in new_side['tests'])
                st.write(f"**Total Commands:** {total_commands}")
                st.write(f"**SIDE Version:** {new_side.get('version', '1.0')}")
        
        # Debug info for loaded SIDE
        if st.checkbox("🔧 Show SIDE Debug Info", key=f"debug_side_{selected_app}"):
            st.json(new_side)
        
        # Add new test
        if st.button('Add Test', key=f'add_test_{selected_app}'):
            new_side['tests'].append({
                'id': f'test-{len(new_side["tests"])+1}',
                'name': f'Test {len(new_side["tests"])+1}',
                'commands': []
            })
            st.session_state['new_side'] = new_side
            st.success('Test added!')
            safe_rerun()
        
        # Edit existing tests
        for t_idx, test in enumerate(new_side['tests']):
            with st.expander(f"Test: {test['name']}", expanded=False):
                
                # Test controls
                col1, col2 = st.columns([3, 1])
                with col1:
                    test['name'] = st.text_input(f"Test Name", value=test['name'], key=f"test_name_{selected_app}_{t_idx}")
                with col2:
                    if st.button('Delete Test', key=f'del_test_{selected_app}_{t_idx}'):
                        new_side['tests'].pop(t_idx)
                        st.session_state['new_side'] = new_side
                        safe_rerun()
                
                # Commands/Steps - Show all command details
                for c_idx, cmd in enumerate(test['commands']):
                    with st.expander(f"Step {c_idx+1}: {cmd.get('command', '')} - {cmd.get('target', '')[:50]}{'...' if len(cmd.get('target', '')) > 50 else ''}", expanded=False):
                        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                        
                        with col1:
                            cmd['command'] = st.text_input(
                                "Command", value=cmd.get('command',''), 
                                key=f"cmd_{selected_app}_{t_idx}_{c_idx}",
                                placeholder="e.g., open, click, type"
                            )
                        with col2:
                            cmd['target'] = st.text_area(
                                "Target", value=cmd.get('target',''), 
                                key=f"target_{selected_app}_{t_idx}_{c_idx}",
                                placeholder="CSS selector, XPath, or URL",
                                height=100
                            )
                        with col3:
                            cmd['value'] = st.text_area(
                                "Value", value=cmd.get('value',''), 
                                key=f"value_{selected_app}_{t_idx}_{c_idx}",
                                placeholder="Text, value, or data",
                                height=100
                            )
                        with col4:
                            st.write("")  # Spacing
                            if st.button('Delete', key=f'del_step_{selected_app}_{t_idx}_{c_idx}', help="Delete step"):
                                test['commands'].pop(c_idx)
                                st.session_state['new_side'] = new_side
                                safe_rerun()
                        
                        # Show additional command details if available
                        if cmd.get('comment'):
                            st.text_area("Comment", value=cmd.get('comment', ''), 
                                       key=f"comment_{selected_app}_{t_idx}_{c_idx}", 
                                       placeholder="Step description or notes")
                        
                        # Show all other properties
                        other_props = {k: v for k, v in cmd.items() if k not in ['command', 'target', 'value', 'comment']}
                        if other_props:
                            st.json(other_props)
                
                # Add step button
                if st.button('Add Step', key=f'add_step_{selected_app}_{t_idx}'):
                    test['commands'].append({'command': '', 'target': '', 'value': ''})
                    st.session_state['new_side'] = new_side
                    safe_rerun()
        
        # Save and run manual SIDE file
        if new_side['tests']:
            st.markdown('<h4 class="section-header">Save & Execute</h4>', unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                manual_side_name = st.text_input(
                    'SIDE file name for database', 
                    value=f'{selected_app or "new"}_manual', 
                    key=f'side_name_{selected_app}'
                )
                
                if st.button('Save to Database', key=f'save_db_{selected_app}'):
                    side_json = json.dumps(new_side, indent=2)
                    try:
                        save_run(
                            selected_app, user_params, {}, [], b'', 
                            original_side_bytes=side_json.encode(), 
                            modified_side_bytes=None, 
                            side_name=manual_side_name
                        )
                        st.success(f'SIDE file "{manual_side_name}" saved to database for app "{selected_app}"!')
                    except Exception as e:
                        st.error(f'Failed to save to database: {e}')
            
            with col2:
                # Test selection for running
                if new_side['tests']:
                    test_names = [t.get('name', f"Test {i+1}") for i, t in enumerate(new_side['tests'])]
                    sel_test = st.selectbox(
                        'Select test to run', 
                        range(len(test_names)), 
                        format_func=lambda i: test_names[i], 
                        key=f'manual_test_select_{selected_app}'
                    )
                    
                    if st.button('Run Selected Test', key=f'run_manual_test_{selected_app}'):
                        with st.spinner("Running manual test..."):
                            test_side = dict(new_side)
                            test_side['tests'] = [new_side['tests'][sel_test]]
                            zip_bytes = run_test_and_get_results(test_side, selected_app, "manual")
                            
                            # Save manual test run to database
                            try:
                                save_run(
                                    selected_app, user_params, {}, [], zip_bytes,
                                    original_side_bytes=json.dumps(test_side).encode(),
                                    modified_side_bytes=None,
                                    side_name=f"manual_run_{test['name']}"
                                )
                                st.success('Manual test run saved to database!')
                            except Exception as e:
                                st.error(f'Failed to save test run: {e}')
                            
                            st.download_button(
                                'Download Manual Test Results', 
                                data=zip_bytes, 
                                file_name=f'{selected_app}_manual_results.zip', 
                                mime='application/zip'
                            )
            
            # Download SIDE file
            side_json = json.dumps(new_side, indent=2)
            b64 = base64.b64encode(side_json.encode()).decode()
            st.markdown(
                f'<a href="data:application/json;base64,{b64}" download="{selected_app or "new"}.side">Download SIDE File</a>', 
                unsafe_allow_html=True
            )
    
    with tab3:
        st.markdown("### Test Run History")
        
        # Performance monitoring section
        if st.checkbox("Show Performance Stats", key=f"perf_{selected_app}"):
            with st.container():
                col1, col2, col3 = st.columns(3)
                try:
                    stats = get_system_stats()
                    with col1:
                        st.metric("Memory Usage", f"{stats['memory_percent']:.1f}%")
                    with col2:
                        st.metric("Available Memory", f"{stats['memory_available']} MB")
                    with col3:
                        st.metric("CPU Usage", f"{stats['cpu_percent']:.1f}%")
                except:
                    pass
        
        # History pagination and filtering
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            history_limit = st.selectbox("Records to load", [10, 25, 50, 100], index=1, key=f"hist_limit_{selected_app}")
        with col2:
            sort_order = st.selectbox("Sort by", ["Newest First", "Oldest First"], key=f"hist_sort_{selected_app}")
        with col3:
            if st.button("🔄 Refresh", key=f"hist_refresh_{selected_app}"):
                st.cache_data.clear()
                st.rerun()
        
        try:
            # Get runs with pagination
            all_runs = get_cached_recent_runs(limit=history_limit * 2)  # Get extra for filtering
            app_runs = [r for r in all_runs if (r.get('app_name') or 'Unnamed') == selected_app]
            
            # Apply sorting
            if sort_order == "Oldest First":
                app_runs = app_runs[::-1]
            
            # Limit results
            app_runs = app_runs[:history_limit]
            
            if app_runs:
                st.caption(f"Showing {len(app_runs)} recent runs for {selected_app}")
                
                # Debug section for screenshot issues
                if st.checkbox("🔧 Enable Screenshot Debug Mode", key=f"debug_screenshots_{selected_app}"):
                    st.warning("Debug mode enabled - this will show detailed information about ZIP file contents")
                
                debug_mode = st.session_state.get(f"debug_screenshots_{selected_app}", False)
                
                for i, run in enumerate(app_runs):
                    timestamp = run.get('timestamp')
                    ts_str = timestamp.strftime('%Y-%m-%d %H:%M:%S') if timestamp else 'Unknown'
                    
                    # Use session state to track expanded state for better performance
                    expanded_key = f"expanded_{selected_app}_{i}"
                    is_expanded = st.session_state.get(expanded_key, False)
                    
                    with st.expander(f"{ts_str} - {run.get('app_name','')}", expanded=is_expanded):
                        # Store expansion state
                        st.session_state[expanded_key] = True
                        
                        # Run details in more compact format
                        details_col1, details_col2 = st.columns(2)
                        with details_col1:
                            params = run.get('user_params', {})
                            if params:
                                st.write(f"**User Params:** {len(params)} items")
                                if st.button("Show Params", key=f"show_params_{i}"):
                                    st.json(params)
                            else:
                                st.write("**User Params:** None")
                            
                            param_map = run.get('param_map', {})
                            if param_map:
                                st.write(f"**Parameter Map:** {len(param_map)} mappings")
                            else:
                                st.write("**Parameter Map:** None")
                        
                        with details_col2:
                            screenshots = run.get('screenshot_steps', [])
                            
                            # Enhanced screenshot info with preview
                            zip_bytes = run.get('zip_file', b'')
                            if zip_bytes:
                                try:
                                    with io.BytesIO(zip_bytes) as zb, zipfile.ZipFile(zb) as zf:
                                        screenshot_files = [name for name in zf.namelist() 
                                                          if name.lower().endswith(('.png', '.jpg', '.jpeg'))]
                                        
                                        if screenshot_files:
                                            st.write(f"**Screenshots:** {len(screenshot_files)} files")
                                            # Show screenshot filenames as preview
                                            with st.expander(f"📸 Preview ({len(screenshot_files)} screenshots)", expanded=False):
                                                for img_name in sorted(screenshot_files):
                                                    st.text(f"• {img_name}")
                                        else:
                                            st.write(f"**Screenshots:** {len(screenshots)} steps configured (no files)")
                                except:
                                    st.write(f"**Screenshots:** {len(screenshots)} steps")
                            else:
                                st.write(f"**Screenshots:** {len(screenshots)} steps")
                            
                            # Show file sizes if available
                            zip_size = len(zip_bytes) // 1024
                            if zip_size > 0:
                                st.write(f"**Results Size:** {zip_size} KB")
                            else:
                                st.write("**Results Size:** No data")
                        
                        # Download buttons in single row
                        btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)
                        
                        with btn_col1:
                            zip_bytes = run.get('zip_file', b'')
                            if zip_bytes:
                                st.download_button(
                                    '📥 Results ZIP', data=zip_bytes, 
                                    file_name=f'{selected_app}_results_{ts_str.replace(":", "")}.zip', 
                                    mime='application/zip', 
                                    key=f"dl_{run.get('_id', i)}"
                                )
                        
                        with btn_col2:
                            if run.get('original_side'):
                                st.download_button(
                                    '📄 Original SIDE', data=run.get('original_side'), 
                                    file_name=f'{selected_app}_original.side', 
                                    mime='application/json', 
                                    key=f"orig_{run.get('_id', i)}"
                                )
                        
                        with btn_col3:
                            if run.get('modified_side'):
                                st.download_button(
                                    '📝 Modified SIDE', data=run.get('modified_side'), 
                                    file_name=f'{selected_app}_modified.side', 
                                    mime='application/json', 
                                    key=f"mod_{run.get('_id', i)}"
                                )
                        
                        with btn_col4:
                            # Enhanced screenshot viewer - shows ALL screenshots
                            if zip_bytes and st.button("� View All Screenshots", key=f"view_ss_{i}"):
                                try:
                                    with io.BytesIO(zip_bytes) as zb, zipfile.ZipFile(zb) as zf:
                                        screenshot_files = []
                                        
                                        # Collect all screenshot files with debug info
                                        if debug_mode:
                                            st.write(f"🔍 **Debug: All files in ZIP:** {zf.namelist()}")
                                        
                                        for name in zf.namelist():
                                            if name.lower().endswith(('.png', '.jpg', '.jpeg')):
                                                screenshot_files.append(name)
                                                if debug_mode:
                                                    st.write(f"✅ **Found screenshot:** {name}")
                                        
                                        if screenshot_files:
                                            # Add cache clearing controls at the top
                                            cache_col1, cache_col2, cache_col3 = st.columns([1, 1, 2])
                                            with cache_col1:
                                                if st.button("🔄 Clear All Cache", key=f"clear_cache_{i}"):
                                                    st.cache_data.clear()
                                                    st.cache_resource.clear()
                                                    st.success("✅ Cache cleared!")
                                                    st.rerun()
                                            with cache_col2:
                                                if st.button("⚡ Force Refresh", key=f"force_refresh_{i}"):
                                                    # Clear everything and restart
                                                    for key in list(st.session_state.keys()):
                                                        if 'screenshot' in key or 'cache' in key:
                                                            del st.session_state[key]
                                                    st.cache_data.clear()
                                                    st.cache_resource.clear()
                                                    st.rerun()
                                            with cache_col3:
                                                st.info("💡 If you see deprecation warnings, click 'Force Refresh' to clear them")
                                            
                                            if debug_mode:
                                                st.success(f"🎯 **Debug: Found {len(screenshot_files)} screenshot files total**")
                                                st.write(f"**Screenshot list:** {screenshot_files}")
                                            
                                            st.markdown(f"### 📸 Screenshots ({len(screenshot_files)} found)")
                                            
                                            # Sort screenshots by name for better organization
                                            screenshot_files.sort()
                                            
                                            # Display all screenshots in a grid layout
                                            num_screenshots = len(screenshot_files)
                                            
                                            # Use columns for better layout if multiple screenshots
                                            if num_screenshots <= 2:
                                                cols = st.columns(num_screenshots)
                                            elif num_screenshots <= 4:
                                                cols = st.columns(2)
                                            else:
                                                cols = st.columns(3)
                                            
                                            for idx, name in enumerate(screenshot_files):
                                                img_data = zf.read(name)
                                                
                                                # Determine which column to use
                                                if num_screenshots <= 2:
                                                    col_idx = idx
                                                elif num_screenshots <= 4:
                                                    col_idx = idx % 2
                                                else:
                                                    col_idx = idx % 3
                                                
                                                with cols[col_idx]:
                                                    # Create expandable image viewer with better memory handling
                                                    with st.expander(f"📸 {name}", expanded=True):
                                                        # Use a unique key for each image to prevent media file conflicts
                                                        img_key = f"img_{i}_{idx}_{name.replace('.', '_')}"
                                                        
                                                        try:
                                                            # Use safe wrapper to prevent any deprecation warnings
                                                            safe_st_image(
                                                                image=img_data,
                                                                caption=f"Screenshot: {name}",
                                                                use_container_width=True,
                                                                output_format="PNG"
                                                            )
                                                            
                                                            # Add download button for individual screenshot
                                                            st.download_button(
                                                                "💾 Download This Screenshot",
                                                                data=img_data,
                                                                file_name=name,
                                                                mime="image/png",
                                                                key=f"dl_img_{i}_{idx}_{name.replace('.', '_')}"
                                                            )
                                                        except Exception as img_error:
                                                            st.error(f"Could not display {name}: {img_error}")
                                                            # Still provide download option even if display fails
                                                            st.download_button(
                                                                "💾 Download (Display Failed)",
                                                                data=img_data,
                                                                file_name=name,
                                                                mime="image/png",
                                                                key=f"dl_img_err_{i}_{idx}_{name.replace('.', '_')}"
                                                            )
                                        else:
                                            st.info("No screenshots found in this run")
                                            
                                except Exception as e:
                                    st.error(f"Could not load screenshots: {e}")
                                    if st.checkbox("Show Error Details", key=f"img_debug_{i}"):
                                        st.exception(e)
                        
                        # Additional Gallery View Option
                        if zip_bytes:
                            try:
                                with io.BytesIO(zip_bytes) as zb, zipfile.ZipFile(zb) as zf:
                                    screenshot_files = [name for name in zf.namelist() 
                                                      if name.lower().endswith(('.png', '.jpg', '.jpeg'))]
                                    
                                    if len(screenshot_files) > 1:
                                        if st.button(f"🖼️ Gallery View ({len(screenshot_files)} screenshots)", key=f"gallery_{i}"):
                                            st.markdown("### 📸 Screenshot Gallery")
                                            
                                            # Create a more compact gallery grid
                                            num_cols = min(4, len(screenshot_files))
                                            cols = st.columns(num_cols)
                                            
                                            for idx, name in enumerate(sorted(screenshot_files)):
                                                img_data = zf.read(name)
                                                col_idx = idx % num_cols
                                                
                                                with cols[col_idx]:
                                                    try:
                                                        # Use safe wrapper to prevent any deprecation warnings
                                                        safe_st_image(
                                                            image=img_data,
                                                            caption=name,
                                                            use_container_width=True,
                                                            output_format="PNG"
                                                        )
                                                        st.download_button(
                                                            "💾",
                                                            data=img_data,
                                                            file_name=name,
                                                            mime="image/png",
                                                            key=f"gallery_dl_{i}_{idx}_{name.replace('.', '_')}",
                                                            help=f"Download {name}"
                                                        )
                                                    except Exception as gallery_error:
                                                        st.error(f"Could not display {name}")
                                                        st.download_button(
                                                            "💾 Download",
                                                            data=img_data,
                                                            file_name=name,
                                                            mime="image/png",
                                                            key=f"gallery_dl_err_{i}_{idx}_{name.replace('.', '_')}",
                                                            help=f"Download {name} (display failed)"
                                                        )
                            except:
                                pass  # Silently fail for gallery view
                
                # Memory cleanup after displaying runs
                if len(app_runs) > 20:
                    gc.collect()  # Force garbage collection for large datasets
                    
            else:
                st.info("No test runs found for this application.")
                # Suggest creating a test
                st.markdown("**Get started by:**")
                st.markdown("1. Upload a SIDE file in the 'Upload & Execute' tab")
                st.markdown("2. Create a manual test in the 'Manual Editor' tab")
                
        except Exception as e:
            st.error(f"Failed to fetch history: {e}")
            # Show debug info in development
            if st.checkbox("Show Error Details", key=f"debug_{selected_app}"):
                st.exception(e)

# ============================================================================
# MAIN EXECUTION
# ============================================================================
if selected_app:
    render_app_tab(selected_app)
else:
    st.markdown('<h3 class="section-header">Select or create an application from the sidebar to get started</h3>', unsafe_allow_html=True)
    st.markdown("""
    **Platform Features:**
    - Multiple application management
    - Upload and execute SIDE files  
    - Create manual test scripts
    - URL monitoring and health checks
    - Test result history with screenshots
    - MongoDB database integration
    - Direct screenshot viewing in UI
    """)
