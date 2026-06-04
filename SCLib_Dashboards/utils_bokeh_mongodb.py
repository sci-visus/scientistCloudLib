"""
MongoDB utilities for Bokeh dashboards
"""
import os
import re
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


def _email_candidates_for_access(user_email):
    """Normalize email list for owner/share/team lookups (matches datasets/by-user API)."""
    if user_email is None:
        return []
    emails = user_email if isinstance(user_email, list) else [user_email]
    out = []
    for raw in emails:
        if not raw:
            continue
        s = str(raw).strip()
        if s and s not in out:
            out.append(s)
        low = s.lower()
        if low and low not in out:
            out.append(low)
    return out


def _find_dataset_doc(collection, identifier):
    """Resolve a dataset document from uuid, remote link, or source path."""
    if not identifier:
        return None
    identifier = str(identifier).strip()
    doc = collection.find_one({
        '$or': [
            {'uuid': identifier},
            {'google_drive_link': identifier},
            {'source_path': identifier},
        ]
    })
    if doc:
        return doc
    if identifier.startswith('http'):
        doc = collection.find_one({'google_drive_link': {'$regex': re.escape(identifier)}})
        if doc:
            return doc
    return None


def _teams_for_user(team_collection, email_candidates):
    """Teams the user belongs to: (team uuids, team names)."""
    if not email_candidates:
        return [], []
    teams = list(team_collection.find({
        '$or': [
            {'emails': {'$in': email_candidates}},
            {'owner': {'$in': email_candidates}},
        ]
    }))
    team_uuids = [str(t.get('uuid')) for t in teams if t.get('uuid')]
    team_names = [str(t.get('team_name')) for t in teams if t.get('team_name')]
    return team_uuids, team_names


def _profile_team_refs(collection1, email_candidates):
    profile_team_refs = []
    prof = collection1.find_one({'email': {'$in': email_candidates}})
    if prof:
        for key in ('team_id', 'team_uuid'):
            val = prof.get(key)
            if val not in (None, '', []):
                profile_team_refs.append(str(val))
    return list(dict.fromkeys(profile_team_refs))


def check_dataset_access(collection, collection1, team_collection, shared_team_collection, uuid, user_email, is_public=False):
    """Check if user has access to a dataset (aligned with GET /api/v1/datasets/by-user).
    Returns: (is_authorized, access_type, message)
    """
    try:
        dataset_doc = _find_dataset_doc(collection, uuid)
        access_uuid = (dataset_doc or {}).get('uuid') or uuid

        # Check if dataset is public
        if is_public:
            public_doc = collection.find_one({
                'uuid': access_uuid,
                '$or': [
                    {'is_public': True},
                    {'is_public': 'true'},
                    {'is_public': 'True'},
                ],
            })
            if public_doc:
                return True, "public", "Dataset is publicly accessible"

        if not user_email:
            return False, "no_access", "You don't have access to this dataset. Please contact the dataset owner to request access."

        email_candidates = _email_candidates_for_access(user_email)
        if not email_candidates:
            return False, "no_access", "You don't have access to this dataset. Please contact the dataset owner to request access."

        id_or = [{'uuid': access_uuid}, {'google_drive_link': uuid}, {'uuid': uuid}]
        if dataset_doc:
            id_or.append({'uuid': dataset_doc.get('uuid')})

        # Direct owner on dataset document
        if dataset_doc:
            owner_fields = ('user', 'user_email', 'user_id', 'owner')
            if any(dataset_doc.get(f) in email_candidates for f in owner_fields if dataset_doc.get(f)):
                return True, "direct", "You have direct access to this dataset"
            shared_with = dataset_doc.get('shared_with') or []
            if isinstance(shared_with, list) and any(s in email_candidates for s in shared_with):
                return True, "shared", "You have shared access to this dataset"

        user_with_uuid = collection.find_one({
            '$and': [
                {'$or': id_or},
                {'$or': [
                    {'user': {'$in': email_candidates}},
                    {'user_email': {'$in': email_candidates}},
                ]},
            ],
        })
        user_with_sharing = collection1.find_one({
            '$and': [
                {'$or': id_or},
                {'$or': [
                    {'user': {'$in': email_candidates}},
                    {'user_email': {'$in': email_candidates}},
                ]},
            ],
        })

        if user_with_uuid or user_with_sharing:
            return True, "direct", "You have direct access to this dataset"

        # shared_user collection
        shared_user_coll = collection.database['shared_user']
        if shared_user_coll.find_one({
            'uuid': access_uuid,
            '$or': [
                {'user': {'$in': email_candidates}},
                {'user_email': {'$in': email_candidates}},
            ],
        }):
            return True, "shared", "You have shared access to this dataset"

        team_uuids, team_names = _teams_for_user(team_collection, email_candidates)
        profile_team_refs = _profile_team_refs(collection1, email_candidates)

        # Team membership via dataset.team_uuid / team_id (same as by-user Method 2)
        if dataset_doc:
            ds_team = dataset_doc.get('team_uuid') or dataset_doc.get('team_id')
            if ds_team not in (None, '', []):
                ds_team_str = str(ds_team)
                if (
                    ds_team_str in team_uuids
                    or ds_team_str in team_names
                    or ds_team_str in profile_team_refs
                ):
                    print(
                        f"✅ Team access: user in team(s) {team_names!r}, "
                        f"dataset.team_uuid={ds_team_str!r}"
                    )
                    return True, "team", f"You have access through team: {ds_team_str}"

        # shared_team collection (by-user Method 1)
        if team_uuids or team_names:
            match_conditions = []
            if team_uuids:
                match_conditions.append({'team_uuid': {'$in': team_uuids}})
            if team_names:
                match_conditions.append({'team': {'$in': team_names}})
            if match_conditions:
                shared_team = shared_team_collection.find_one({
                    '$and': [
                        {'$or': [{'uuid': access_uuid}, {'uuid': uuid}, {'google_drive_link': uuid}]},
                        {'$or': match_conditions},
                    ],
                })
                if shared_team:
                    team_label = shared_team.get('team') or shared_team.get('team_uuid') or 'Unknown'
                    return True, "team", f"You have access through team: {team_label}"

        return False, "no_access", "You don't have access to this dataset. Please contact the dataset owner to request access."

    except Exception as e:
        print(f"❌ Database lookup failed: {e}")
        return False, "error", f"Database error: {str(e)}"
