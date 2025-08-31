import os
import datetime
from pymongo import MongoClient, ASCENDING, DESCENDING
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def get_mongo_uri():
    """Get MongoDB URI from Streamlit secrets or environment variables."""
    try:
        # Try to import streamlit and get from secrets
        import streamlit as st
        logger.info("Streamlit imported successfully")
        
        if hasattr(st, 'secrets'):
            logger.info("Streamlit secrets available")
            
            # Try mongo.uri first (recommended format)
            if 'mongo' in st.secrets and 'uri' in st.secrets['mongo']:
                uri = st.secrets['mongo']['uri']
                logger.info(f"✅ Using MongoDB URI from secrets (mongo.uri): {uri[:50]}...")
                return uri
            
            # Try MONGO_URI as fallback
            elif 'MONGO_URI' in st.secrets:
                uri = st.secrets['MONGO_URI']
                logger.info(f"✅ Using MongoDB URI from secrets (MONGO_URI): {uri[:50]}...")
                return uri
            
            # Try mongo_uri as another fallback
            elif 'mongo_uri' in st.secrets:
                uri = st.secrets['mongo_uri']
                logger.info(f"✅ Using MongoDB URI from secrets (mongo_uri): {uri[:50]}...")
                return uri
            
            else:
                logger.warning("❌ No mongo configuration found in secrets")
                logger.info(f"Available secrets keys: {list(st.secrets.keys())}")
        else:
            logger.warning("❌ Streamlit secrets not available")
            
    except ImportError:
        logger.info("ℹ️ Streamlit not available (running outside streamlit)")
    except Exception as e:
        logger.warning(f"❌ Could not access Streamlit secrets: {e}")
    
    # Fallback to environment variable
    env_uri = os.environ.get("MONGO_URI")
    if env_uri:
        logger.info(f"✅ Using MongoDB URI from environment: {env_uri[:50]}...")
        return env_uri
    
    # Final fallback to localhost
    fallback_uri = "mongodb://localhost:27017/"
    logger.warning(f"⚠️ Using fallback MongoDB URI: {fallback_uri}")
    return fallback_uri

# MongoDB connection with connection pooling and error handling
MONGO_URI = get_mongo_uri()
logger.info(f"🔗 Initializing MongoDB connection with URI: {MONGO_URI[:30]}...")

try:
    client = MongoClient(
        MONGO_URI,
        maxPoolSize=5,  # Reduced pool size for cloud
        serverSelectionTimeoutMS=10000,  # 10 second timeout
        socketTimeoutMS=5000,  # 5 second socket timeout
        connectTimeoutMS=10000,  # 10 second connection timeout
        heartbeatFrequencyMS=30000,  # 30 second heartbeat
        retryWrites=True,
        retryReads=True
    )
    
    # Test the connection immediately
    logger.info("🔍 Testing MongoDB connection...")
    client.admin.command('ping')
    logger.info("✅ MongoDB connection successful!")
    
    db = client["side_test_db"]
    runs_collection = db["runs"]
    logger.info("✅ Database and collection initialized successfully!")
    
    # Create indexes for better query performance
    try:
        logger.info("📊 Creating database indexes...")
        runs_collection.create_index([("timestamp", DESCENDING)])
        runs_collection.create_index([("app_name", ASCENDING)])
        runs_collection.create_index([("app_name", ASCENDING), ("timestamp", DESCENDING)])
        logger.info("✅ Database indexes created successfully!")
    except Exception as e:
        logger.warning(f"⚠️ Could not create indexes: {e}")
        
except Exception as e:
    logger.error(f"❌ Failed to connect to MongoDB: {e}")
    logger.info("🔄 Setting database to None - app will run in read-only mode")
    client = None
    db = None
    runs_collection = None

# Log final database status
if runs_collection is not None:
    logger.info("🎯 Database Status: CONNECTED and READY")
else:
    logger.warning("🚫 Database Status: NOT AVAILABLE (read-only mode)")

def save_run(app_name, user_params, param_map, screenshot_steps, zip_bytes, 
             original_side_bytes=None, modified_side_bytes=None, side_name=None):
    """Save test run to database with error handling."""
    if runs_collection is None:
        logger.warning("Database not available - skipping save")
        return None
    
    try:
        logger.info(f"Saving run for app: {app_name}")
        run_doc = {
            "app_name": app_name or "Unknown",
            "side_name": side_name,
            "user_params": user_params or {},
            "param_map": param_map or {},
            "screenshot_steps": screenshot_steps or [],
            "timestamp": datetime.datetime.utcnow(),
            "zip_file": zip_bytes,
            "original_side": original_side_bytes,
            "modified_side": modified_side_bytes,
            # Add metadata for better querying
            "zip_size": len(zip_bytes) if zip_bytes else 0,
            "has_screenshots": bool(screenshot_steps),
            "param_count": len(param_map) if param_map else 0
        }
        
        result = runs_collection.insert_one(run_doc)
        logger.info(f"✅ Saved run for {app_name} with ID: {result.inserted_id}")
        return result.inserted_id
        
    except Exception as e:
        logger.error(f"❌ Failed to save run: {e}")
        raise

def get_recent_runs(limit=10):
    """Get recent runs with optimized query and error handling."""
    if runs_collection is None:
        logger.warning("Database not available, returning empty list")
        return []
    
    try:
        logger.info(f"Fetching {limit} recent runs...")
        # Use projection to limit data transfer
        projection = {
            "app_name": 1,
            "side_name": 1,
            "user_params": 1,
            "param_map": 1,
            "screenshot_steps": 1,
            "timestamp": 1,
            "zip_file": 1,
            "original_side": 1,
            "modified_side": 1,
            "zip_size": 1,
            "has_screenshots": 1,
            "param_count": 1
        }
        
        # Limit maximum records to prevent memory issues
        safe_limit = min(limit, 100)
        
        cursor = runs_collection.find(
            {}, 
            projection
        ).sort("timestamp", DESCENDING).limit(safe_limit)
        
        results = list(cursor)
        logger.info(f"✅ Retrieved {len(results)} runs from database")
        return results
        
    except Exception as e:
        logger.error(f"❌ Failed to get recent runs: {e}")
        return []

def get_runs_for_app(app_name, limit=20):
    """Get runs for a specific app with better performance."""
    if runs_collection is None or not app_name:
        return []
    
    try:
        cursor = runs_collection.find(
            {"app_name": app_name}
        ).sort("timestamp", DESCENDING).limit(limit)
        
        return list(cursor)
        
    except Exception as e:
        logger.error(f"Failed to get runs for app {app_name}: {e}")
        return []

def delete_runs_for_app(app_name):
    """Delete all runs for a given app name."""
    if runs_collection is None or not app_name:
        return 0
    
    try:
        result = runs_collection.delete_many({"app_name": app_name})
        logger.info(f"Deleted {result.deleted_count} runs for app: {app_name}")
        return result.deleted_count
    except Exception as e:
        logger.error(f"Failed to delete runs for app {app_name}: {e}")
        return 0

def delete_all_runs():
    """Delete all runs from the database."""
    if runs_collection is None:
        return 0
    
    try:
        result = runs_collection.delete_many({})
        logger.info(f"Deleted all {result.deleted_count} runs")
        return result.deleted_count
    except Exception as e:
        logger.error(f"Failed to delete all runs: {e}")
        return 0

def get_app_list():
    """Get list of unique app names for better performance."""
    if runs_collection is None:
        return []
    
    try:
        # Use aggregation for better performance
        pipeline = [
            {"$group": {"_id": "$app_name"}},
            {"$sort": {"_id": 1}},
            {"$limit": 50}  # Limit results
        ]
        
        result = runs_collection.aggregate(pipeline)
        return [doc["_id"] for doc in result if doc["_id"]]
        
    except Exception as e:
        logger.error(f"Failed to get app list: {e}")
        return []

def cleanup_old_runs(days=30):
    """Clean up runs older than specified days."""
    if runs_collection is None:
        return 0
    
    try:
        cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=days)
        result = runs_collection.delete_many({"timestamp": {"$lt": cutoff_date}})
        logger.info(f"Cleaned up {result.deleted_count} old runs")
        return result.deleted_count
    except Exception as e:
        logger.error(f"Failed to cleanup old runs: {e}")
        return 0

def check_database_health():
    """Check if database connection is healthy."""
    if client is None or runs_collection is None:
        return False, "Database not initialized"
    
    try:
        # Simple ping test with timeout
        client.admin.command('ping')
        return True, "Database connection healthy"
    except Exception as e:
        return False, f"Database connection failed: {e}"

def get_database_status():
    """Get detailed database status information."""
    status = {
        "connected": False,
        "message": "Unknown",
        "uri_source": "Unknown",
        "collection_available": False
    }
    
    try:
        # Check URI source
        if "streamlit" in str(type(get_mongo_uri())):
            status["uri_source"] = "Streamlit Secrets"
        else:
            status["uri_source"] = "Environment/Fallback"
        
        # Check connection
        if client is not None:
            client.admin.command('ping')
            status["connected"] = True
            status["message"] = "Successfully connected"
            
            if runs_collection is not None:
                status["collection_available"] = True
        else:
            status["message"] = "Client not initialized"
            
    except Exception as e:
        status["message"] = f"Connection error: {e}"
    
    return status
