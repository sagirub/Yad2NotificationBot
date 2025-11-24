import uuid
from typing import Dict, List, Optional

# --- IMPORTANT FOR LAMBDA ---
# This global dict is for demo purposes ONLY.
# An AWS Lambda function is stateless. This dict will be WIPED on every
# "cold start". You MUST replace this with a persistent database
# like AWS DynamoDB or RDS.
MOCK_DB: Dict[str, List[Dict[str, str]]] = {
    # "user_id": [
    #     {"id": "uuid-123", "name": "Search 1", "link": "http://..."},
    # ]
}

# --- DB Helper Functions ---
# It's cleaner to have your handlers call functions
# than to manipulate the DB directly.

async def get_searches(user_id: str) -> List[Dict[str, str]]:
    """Fetches all searches for a user."""
    return MOCK_DB.get(user_id, [])

async def add_search(user_id: str, name: str, link: str) -> Dict[str, str]:
    """Adds a new search and returns it."""
    new_search = {
        "id": str(uuid.uuid4()),  # Generate a unique ID
        "name": name,
        "link": link
    }
    MOCK_DB.setdefault(user_id, []).append(new_search)
    return new_search

async def delete_search(user_id: str, search_id: str) -> Optional[Dict[str, str]]:
    """Deletes a search by its unique ID and returns it."""
    if user_id not in MOCK_DB:
        return None
        
    search_list = MOCK_DB[user_id]
    removed_search = None
    for i, search in enumerate(search_list):
        if search["id"] == search_id:
            removed_search = search_list.pop(i)
            break
    
    return removed_search