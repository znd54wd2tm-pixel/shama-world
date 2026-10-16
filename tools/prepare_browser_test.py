"""Create only an isolated local browser fixture, never a production balance hook."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from seed_data import seed_content
from database import get_connection
from services.users import get_or_create_user
from services.businesses import award_enterprise

root=Path(__file__).resolve().parents[1]
directory=root/'.test-data'
directory.mkdir(exist_ok=True)
path=directory/'browser.sqlite3'
assert path.resolve().parent==directory.resolve()
seed_content(path)
user=get_or_create_user(path,{'id':900000001,'first_name':'Dev','last_name':'User'})
with get_connection(path) as c:
    c.execute('UPDATE users SET balance=1000000 WHERE id=?',(user['id'],))
    c.execute('INSERT INTO user_settings(user_id,fast_open) VALUES (?,0) ON CONFLICT(user_id) DO UPDATE SET fast_open=0',(user['id'],))
    award_enterprise(c,user['id'],1)
print('Local fixture ready at .test-data/browser.sqlite3')
