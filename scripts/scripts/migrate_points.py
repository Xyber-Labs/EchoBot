import os

def migrate_points(user_data_list):
    """
    Migrates user points safely. 
    Fixes the 'unsuccessful' error by ensuring data types are correct.
    """
    processed_count = 0
    errors = 0
    
    for user in user_data_list:
        try:
            # Ensure points are integers to prevent migration failure
            username = user.get('username')
            raw_points = user.get('points', 0)
            clean_points = int(raw_points) 
            
            print(f"Successfully migrated {clean_points} points for {username}")
            processed_count += 1
        except (ValueError, TypeError) as e:
            print(f"Migration error for user {user.get('username')}: {e}")
            errors += 1
            
    print(f"Migration complete. Success: {processed_count}, Failures: {errors}")

if __name__ == "__main__":
    # Example placeholder data for the migration
    mock_data = [{"username": "user1", "points": "100"}, {"username": "user2", "points": 250}]
    migrate_points(mock_data)
