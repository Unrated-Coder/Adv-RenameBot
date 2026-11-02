import motor.motor_asyncio, datetime, pytz

from config import Config
from helper.utils import send_log

class Database:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.user
        self.premium = self.db.premium
        self.settings = self.db.settings
        self.fsub = self.db.fsub

    def new_user(self, id):
        return dict(
            _id=int(id),
            join_date=datetime.date.today().isoformat(),
            file_id=None,
            caption=None,
            prefix=None,
            suffix=None,
            used_limit=0,
            usertype="Free",
            uploadlimit=Config.FREE_UPLOAD_LIMIT,
            daily=0,
            metadata_mode=False,
            metadata_code="By :- @Unrated_Coder",
            is_metadata_custom=False,
            metadata_site=getattr(Config, "DEFAULT_SITE", "https://www.anireal-anime.top/"),
            is_site_custom=False,
            expiry_time=None,
            has_free_trial=False,
            ban_status=dict(
                is_banned=False,
                ban_duration=0,
                banned_on=datetime.date.max.isoformat(),
                ban_reason=''
            )
        )

    async def add_user(self, b, m):
        u = m.from_user
        if not await self.is_user_exist(u.id):
            user = self.new_user(u.id)
            await self.col.insert_one(user)            
            await send_log(b, u)

    async def is_user_exist(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return bool(user)

    async def total_users_count(self):
        count = await self.col.count_documents({})
        return count

    async def get_all_users(self):
        all_users = self.col.find({})
        return all_users

    async def delete_user(self, user_id):
        await self.col.delete_many({'_id': int(user_id)})
    
    async def set_thumbnail(self, id, file_id):
        await self.col.update_one({'_id': int(id)}, {'$set': {'file_id': file_id}})

    async def get_thumbnail(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('file_id', None)

    async def set_caption(self, id, caption):
        await self.col.update_one({'_id': int(id)}, {'$set': {'caption': caption}})

    async def get_caption(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('caption', None)

    async def set_prefix(self, id, prefix):
        await self.col.update_one({'_id': int(id)}, {'$set': {'prefix': prefix}})

    async def get_prefix(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('prefix', None)

    async def set_suffix(self, id, suffix):
        await self.col.update_one({'_id': int(id)}, {'$set': {'suffix': suffix}})

    async def get_suffix(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return user.get('suffix', None)

    async def set_metadata_mode(self, id, bool_meta):
        await self.col.update_one({'_id': int(id)}, {'$set': {'metadata_mode': bool_meta}})

    async def get_metadata_mode(self, id):
        user = await self.col.find_one({'_id': int(id)})
        if not user:
            return False
        return user.get('metadata_mode', False)

    async def set_metadata(self, id, bool_meta):
        await self.set_metadata_mode(id, bool_meta)

    async def get_metadata(self, id):
        return await self.get_metadata_mode(id)

    async def set_metadata_code(self, id, metadata_code, is_custom=True):
        await self.col.update_one(
            {'_id': int(id)},
            {'$set': {'metadata_code': metadata_code, 'is_metadata_custom': is_custom}}
        )

    async def get_metadata_code(self, id):
        user = await self.col.find_one({'_id': int(id)})
        if not user:
            return "By :- @Unrated_Coder"
        return user.get('metadata_code', "By :- @Unrated_Coder")

    async def get_metadata_custom_status(self, id):
        user = await self.col.find_one({'_id': int(id)})
        if not user:
            return False
        return user.get('is_metadata_custom', False)

    async def set_metadata_site(self, id, metadata_site, is_custom=True):
        await self.col.update_one(
            {'_id': int(id)},
            {'$set': {'metadata_site': metadata_site, 'is_site_custom': is_custom}}
        )

    async def get_metadata_site(self, id):
        user = await self.col.find_one({'_id': int(id)})
        default_site = getattr(Config, "DEFAULT_SITE", "https://www.anireal-anime.top/")
        if not user:
            return default_site
        return user.get('metadata_site', default_site)

    async def get_site_custom_status(self, id):
        user = await self.col.find_one({'_id': int(id)})
        if not user:
            return False
        return user.get('is_site_custom', False)

    async def set_used_limit(self, id, used):
        await self.col.update_one({'_id': int(id)}, {'$set': {'used_limit': used}})
      
    async def set_usertype(self, id, type):
        await self.col.update_one({'_id': int(id)}, {'$set': {'usertype': type}})

    async def set_uploadlimit(self, id, limit):
        await self.col.update_one({'_id': int(id)}, {'$set': {'uploadlimit': limit}})
  
    async def set_reset_dailylimit(self, id, date):
        await self.col.update_one({'_id': int(id)}, {'$set': {'daily': date}})
        
    async def reset_uploadlimit_access(self, user_id):
        seconds = 1440 * 60
        reset_date = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        zero_usage = 0
        
        user_data = await self.get_user_data(user_id)
        if user_data:
            expiry_time = user_data.get("daily")
            current_time = datetime.datetime.now()
            
            needs_reset = (
                expiry_time is None or
                expiry_time == 0 or
                not isinstance(expiry_time, datetime.datetime) or
                current_time > expiry_time
            )
            
            if needs_reset:
                await self.col.update_one(
                    {'_id': user_id}, 
                    {'$set': {
                        'daily': reset_date,
                        'used_limit': zero_usage
                    }}
                )
                        
    async def get_user_data(self, id) -> dict:
        user_data = await self.col.find_one({'_id': int(id)})
        return user_data or None
        
    async def get_user(self, user_id):
        user_data = await self.premium.find_one({"id": user_id})
        return user_data

    async def add_premium(self, user_id, user_data, limit=None, type=None):    
        await self.premium.update_one(
            {"id": user_id}, 
            {"$set": user_data}, 
            upsert=True
        )
        
        if Config.UPLOAD_LIMIT_MODE and limit and type:
            await self.col.update_one(
                {'_id': user_id}, 
                {'$set': {
                    'usertype': type,
                    'uploadlimit': limit
                }}
            )
    
    async def remove_premium(self, user_id, limit=Config.FREE_UPLOAD_LIMIT, type="Free"):
        await self.premium.update_one(
            {"id": user_id}, 
            {"$set": {
                "expiry_time": None,
                "has_free_trial": False
            }}
        )
        
        if Config.UPLOAD_LIMIT_MODE and limit and type:
            await self.col.update_one(
                {'_id': user_id}, 
                {'$set': {
                    'usertype': type,
                    'uploadlimit': limit
                }}
            )
          
    async def checking_remaining_time(self, user_id):
        user_data = await self.get_user(user_id)
        if not user_data:
            return None
        expiry_time = user_data.get("expiry_time")
        if not expiry_time or not isinstance(expiry_time, datetime.datetime):
            return None
        time_left = expiry_time - datetime.datetime.now()
        if time_left.total_seconds() <= 0:
            return None
        return time_left

    async def has_premium_access(self, user_id):
        user_data = await self.get_user(user_id)
        if user_data:
            expiry_time = user_data.get("expiry_time")
            if expiry_time is None:
                return False
            elif isinstance(expiry_time, datetime.datetime) and datetime.datetime.now() <= expiry_time:
                return True
            else:
                await self.remove_premium(user_id)
        return False

    async def total_premium_users_count(self):
        count = await self.premium.count_documents({"expiry_time": {"$gt": datetime.datetime.now()}})
        return count

    async def get_all_premium_users(self):
        all_premium_users = self.premium.find({"expiry_time": {"$gt": datetime.datetime.now()}})
        return all_premium_users

    async def get_free_trial_status(self, user_id):
        user_data = await self.get_user(user_id)
        if user_data:
            return user_data.get("has_free_trial", False)
        return False

    async def give_free_trial(self, user_id):
        seconds = 720 * 60
        expiry_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        user_data = {
            "id": user_id, 
            "expiry_time": expiry_time, 
            "has_free_trial": True
        }
        
        if Config.UPLOAD_LIMIT_MODE:
            limit_type = "Trial"
            upload_limit = 536870912000
            await self.add_premium(user_id, user_data, upload_limit, limit_type)
        else:
            await self.add_premium(user_id, user_data)
                    
    async def remove_ban(self, id):
        ban_status = dict(
            is_banned=False,
            ban_duration=0,
            banned_on=datetime.date.max.isoformat(),
            ban_reason=''
        )
        await self.col.update_one({'_id': int(id)}, {'$set': {'ban_status': ban_status}})

    async def ban_user(self, user_id, ban_duration, ban_reason):
        ban_status = dict(
            is_banned=True,
            ban_duration=ban_duration,
            banned_on=datetime.date.today().isoformat(),
            ban_reason=ban_reason)
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'ban_status': ban_status}})

    async def get_ban_status(self, id):
        default = dict(
            is_banned=False,
            ban_duration=0,
            banned_on=datetime.date.max.isoformat(),
            ban_reason='')
        user = await self.col.find_one({'_id': int(id)})
        return user.get('ban_status', default)

    async def get_all_banned_users(self):
        banned_users = self.col.find({'ban_status.is_banned': True})
        return banned_users

    async def total_banned_users_count(self):
        count = await self.col.count_documents({'ban_status.is_banned': True})
        return count

    async def get_bot_settings(self):
        doc = await self.settings.find_one({'_id': 'bot_settings'})
        if not doc:
            default_settings = {
                '_id': 'bot_settings',
                'premium_mode': getattr(Config, 'PREMIUM_MODE', True),
                'parallel_task_limit': 1,
                'queue_mode': True,
                'queue_task_limit': 5,
                'restart_broadcast_mode': True,
                'max_file_size': '2GB'
            }
            await self.settings.insert_one(default_settings)
            return default_settings
        return doc

    async def update_bot_setting(self, key, value):
        await self.settings.update_one(
            {'_id': 'bot_settings'},
            {'$set': {key: value}},
            upsert=True
        )

    async def add_fsub_channel(self, channel_id: int, channel_title: str, mode: str = "normal", auto_approve: bool = False, invite_link: str = None):
        doc = {
            '_id': int(channel_id),
            'title': channel_title,
            'mode': mode,
            'auto_approve': auto_approve,
            'invite_link': invite_link
        }
        await self.fsub.update_one(
            {'_id': int(channel_id)},
            {'$set': doc},
            upsert=True
        )

    async def update_fsub_mode(self, channel_id: int, mode: str):
        await self.fsub.update_one(
            {'_id': int(channel_id)},
            {'$set': {'mode': mode}}
        )

    async def set_fsub_auto_approve(self, channel_id: int, auto_approve: bool):
        await self.fsub.update_one(
            {'_id': int(channel_id)},
            {'$set': {'auto_approve': auto_approve}}
        )

    async def get_fsub_info(self, channel_id: int):
        doc = await self.fsub.find_one({'_id': int(channel_id)})
        return doc or None

    async def remove_fsub_channel(self, channel_id: int):
        await self.fsub.delete_one({'_id': int(channel_id)})

    async def remove_all_fsub_channels(self):
        await self.fsub.delete_many({})

    async def get_fsub_channels(self):
        channels = []
        async for ch in self.fsub.find({}):
            channels.append(ch)
        return channels

unrated_coder = Database(Config.DB_URL or "mongodb://localhost:27017", Config.DB_NAME or "Adv-RenameBot")
unratedbotz = unrated_coder
