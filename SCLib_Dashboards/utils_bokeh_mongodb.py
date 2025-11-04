"""
MongoDB utilities for Bokeh dashboards
"""
import os
from mongo_connection import get_mongo_client, close_all_connections
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def connect_to_mongodb():
    """Connect to MongoDB and return client and collections"""
    try:
        mongo_url = os.getenv('MONGO_URL')
        db_name = os.getenv('DB_NAME')
        
        if not mongo_url or not db_name:
            print("❌ MongoDB configuration missing")
            return None, None, None, None, None, None
        
        client = get_mongo_client()
        mymongodb = client[db_name]
        collection = mymongodb['visstoredatas']  # Your actual collection name
        collection1 = mymongodb['user_profile']  # Your actual collection name
        team_collection = mymongodb['teams']
        shared_team_collection = mymongodb['shared_team']
        
        print(f"✅ Connected to MongoDB: {db_name}")
        return client, mymongodb, collection, collection1, team_collection, shared_team_collection
        
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        return None, None, None, None, None, None

def cleanup_mongodb():
    """Clean up MongoDB connection using existing function"""
    try:
        close_all_connections()
        print("MongoDB connections cleaned up")
    except Exception as e:
        print(f"Error cleaning up MongoDB connections: {e}")

def check_dataset_access(collection, collection1, team_collection, shared_team_collection, uuid, user_email, is_public=False):
    """Check if user has access to a dataset
    Returns: (is_authorized, access_type, message)
    """
    try:
        # Check if dataset is public
        if is_public:
            # Check for both boolean True and string "true" values
            public_doc = collection.find_one({
                'uuid': uuid, 
                '$or': [
                    {'is_public': True},
                    {'is_public': 'true'},
                    {'is_public': 'True'}
                ]
            })
            if public_doc:
                return True, "public", "Dataset is publicly accessible"
        
        # Check direct user access
        #user_with_uuid = collection.find_one({'uuid': uuid, 'user': user_email})
        
        user_with_uuid = collection.find_one({'$or': [{'uuid': uuid}, {'google_drive_link': uuid}], 'user': user_email})
        user_with_sharing = collection1.find_one({'$or': [{'uuid': uuid}, {'google_drive_link': uuid}], 'user': user_email})

        if user_with_uuid or user_with_sharing:
            print('User Authorized for this dataset')
            return True, "direct", "You have direct access to this dataset"
        
        # Check team sharing
        print(f"🔍 DEBUG: Checking team sharing for user_email: {user_email} (type: {type(user_email)})")
        print(f"🔍 DEBUG: Looking for dataset uuid: {uuid}")
        
        # Find teams where any of the user's emails are in the emails array
        if isinstance(user_email, list):
            # user_email is an array of emails
            print(f"🔍 DEBUG: user_email is a list, using $in query")
            teams = team_collection.find({'emails': {'$in': user_email}})
        else:
            # user_email is a single email string
            print(f"🔍 DEBUG: user_email is a string, using direct query")
            teams = team_collection.find({'emails': user_email})
        
        # Convert to list to see results
        teams_list = list(teams)
        print(f"🔍 DEBUG: Found {len(teams_list)} teams for user")
        
        for i, team in enumerate(teams_list):
            print(f"🔍 DEBUG: Team {i+1}: {team.get('team_name', 'NO_NAME')} - emails: {team.get('emails', [])}")
        
        team_names = [team['team_name'] for team in teams_list]
        print(f"🔍 DEBUG: Team names: {team_names}")
        
        if team_names:
            # Check if any of these teams have the dataset shared
            print(f"🔍 DEBUG: Looking for dataset {uuid} in shared_team collection with teams: {team_names}")
            shared_team = shared_team_collection.find_one({
                '$or': [{'uuid': uuid}, {'google_drive_link': uuid}],
                'team': {'$in': team_names}
            })
            print(f"🔍 DEBUG: Shared team result: {shared_team}")
            if shared_team:
                print(f"✅ DEBUG: Found team sharing access!")
                return True, "team", f"You have access through team: {shared_team.get('team', 'Unknown')}"
            else:
                print(f"❌ DEBUG: No team sharing found for this dataset")
        else:
            print(f"❌ DEBUG: No teams found for user")
        
        return False, "no_access", "You don't have access to this dataset. Please contact the dataset owner to request access."
        
    except Exception as e:
        print(f"❌ Database lookup failed: {e}")
        return False, "error", f"Database error: {str(e)}"
