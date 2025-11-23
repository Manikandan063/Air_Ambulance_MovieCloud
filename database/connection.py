from pymongo import MongoClient
from config import settings
import certifi

class MongoDB:
    client: MongoClient = None

db = MongoDB()

def connect_to_mongo():
    try:
        db.client = MongoClient(settings.MONGODB_URL, tlsCAFile=certifi.where())
        # Test the connection
        db.client.admin.command('ping')
        print("✅ Connected to MongoDB Atlas successfully!")
        return True
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        return False

def close_mongo_connection():
    if db.client:
        db.client.close()
        print("Disconnected from MongoDB Atlas")

def get_database():
    return db.client[settings.DATABASE_NAME]

def get_collection(collection_name: str):
    return get_database()[collection_name]