from src.auth import verify_password
from src.database import get_user_by_username

# Get admin user from database
admin_user = get_user_by_username('admin')
if admin_user:
    stored_hash = admin_user['password_hash']
    print(f'Stored hash: {stored_hash}')
    
    # Test verification
    test_password = 'adminpassword'
    is_valid = verify_password(test_password, stored_hash)
    print(f'Password verification result: {is_valid}')
else:
    print('Admin user not found!')
