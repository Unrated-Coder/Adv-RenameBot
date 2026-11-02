import pytest
import pytest_asyncio
import mongomock_motor
from pyrogram import enums
from pyrogram.errors import UserNotParticipant
from plugins.force_sub import is_user_subscribed, get_unsubscribed_channels, build_fsub_buttons
from helper.database import Database
from config import Config

@pytest.fixture
def mock_db():
    db = Database("mongodb://localhost:27017", "test_db")
    db._client = mongomock_motor.AsyncMongoMockClient()
    db.db = db._client.get_database("test_db")
    db.col = db.db.get_collection("user")
    db.premium = db.db.get_collection("premium")
    db.fsub = db.db.get_collection("fsub")
    return db

class MockUser:
    def __init__(self, id, first_name="User"):
        self.id = id
        self.first_name = first_name

class MockMember:
    def __init__(self, status):
        self.status = status

class MockChat:
    def __init__(self, id, title="Test Channel", username="testchannel", invite_link="https://t.me/testchannel"):
        self.id = id
        self.title = title
        self.username = username
        self.invite_link = invite_link

class MockClient:
    def __init__(self, member_status=enums.ChatMemberStatus.MEMBER, join_requests=None):
        self.member_status = member_status
        self.join_requests = join_requests or []

    async def get_chat_member(self, chat_id, user_id):
        if self.member_status is None:
            raise UserNotParticipant
        return MockMember(self.member_status)

    async def get_chat_join_requests(self, chat_id, query=""):
        for req_user_id in self.join_requests:
            if str(req_user_id) in query or query == "":
                class Req:
                    user = MockUser(req_user_id)
                yield Req()

    async def get_chat(self, chat_id):
        return MockChat(chat_id)

    async def export_chat_invite_link(self, chat_id):
        return f"https://t.me/invite_{chat_id}"


@pytest.mark.asyncio
async def test_is_user_subscribed_member():
    client = MockClient(member_status=enums.ChatMemberStatus.MEMBER)
    assert await is_user_subscribed(client, -100123456789, 111) is True


@pytest.mark.asyncio
async def test_is_user_subscribed_not_participant_no_join_request():
    client = MockClient(member_status=None, join_requests=[])
    assert await is_user_subscribed(client, -100123456789, 111) is False


@pytest.mark.asyncio
async def test_is_user_subscribed_with_join_request():
    client = MockClient(member_status=None, join_requests=[111])
    assert await is_user_subscribed(client, -100123456789, 111, mode="normal") is False
    assert await is_user_subscribed(client, -100123456789, 111, mode="request") is True


@pytest.mark.asyncio
async def test_get_unsubscribed_channels(monkeypatch):
    async def mock_get_fsub_channels():
        return [
            {'_id': -1001, 'title': 'Channel 1', 'invite_link': 'https://t.me/ch1'},
            {'_id': -1002, 'title': 'Channel 2', 'invite_link': 'https://t.me/ch2'}
        ]

    from helper.database import unrated_coder
    monkeypatch.setattr(unrated_coder, "get_fsub_channels", mock_get_fsub_channels)
    monkeypatch.setattr(Config, "FORCE_SUB", "")

    # User subscribed to Channel 1 but not Channel 2
    class CustomClient(MockClient):
        async def get_chat_member(self, chat_id, user_id):
            if chat_id == -1001:
                return MockMember(enums.ChatMemberStatus.MEMBER)
            raise UserNotParticipant

    client = CustomClient(member_status=None)
    unsub = await get_unsubscribed_channels(client, 111)
    assert len(unsub) == 1
    assert unsub[0]['id'] == -1002
    assert unsub[0]['title'] == 'Channel 2'


def test_build_fsub_buttons():
    unsubscribed = [
        {'id': -1001, 'title': 'My Cool Channel', 'invite_link': 'https://t.me/cool'},
        {'id': -1002, 'title': 'Updates', 'invite_link': 'https://t.me/updates'}
    ]
    markup = build_fsub_buttons(unsubscribed)
    buttons = markup.inline_keyboard
    assert len(buttons) == 3
    assert buttons[0][0].text == "My Cool Channel"
    assert buttons[0][0].url == "https://t.me/cool"
    assert buttons[1][0].text == "Updates"
    assert buttons[1][0].url == "https://t.me/updates"
    assert buttons[2][0].text == "🔄 Try Again"
    assert buttons[2][0].callback_data == "cb_fsub_check"


@pytest.mark.asyncio
async def test_cb_fsub_check(monkeypatch):
    from plugins.force_sub import cb_fsub_check

    class MockQueryMsg:
        def __init__(self):
            self.deleted = False
            self.edited = False

        async def delete(self):
            self.deleted = True

        async def edit_reply_markup(self, reply_markup):
            self.edited = True

    class MockQuery:
        def __init__(self, user_id):
            self.from_user = MockUser(user_id)
            self.message = MockQueryMsg()
            self.answer_text = None
            self.alert = False

        async def answer(self, text, show_alert=False):
            self.answer_text = text
            self.alert = show_alert

    # Case 1: Verified (no unsubscribed channels)
    async def mock_get_unsub_none(client, user_id):
        return []

    monkeypatch.setattr("plugins.force_sub.get_unsubscribed_channels", mock_get_unsub_none)
    query = MockQuery(111)
    await cb_fsub_check(None, query)
    assert "verified" in query.answer_text.lower()
    assert query.message.deleted is True

    # Case 2: Still unsubscribed
    async def mock_get_unsub_exist(client, user_id):
        return [{'id': -1001, 'title': 'Channel 1', 'invite_link': 'https://t.me/ch1'}]

    monkeypatch.setattr("plugins.force_sub.get_unsubscribed_channels", mock_get_unsub_exist)
    query2 = MockQuery(111)
    await cb_fsub_check(None, query2)
    assert "haven't joined" in query2.answer_text.lower() or "not joined" in query2.answer_text.lower()
    assert query2.message.edited is True


@pytest.mark.asyncio
async def test_database_fsub_advanced(mock_db):
    cid = -100999888
    # Add channel with mode and auto_approve
    await mock_db.add_fsub_channel(cid, "Test Ch", mode="request", auto_approve=True, invite_link="https://t.me/testch")
    info = await mock_db.get_fsub_info(cid)
    assert info['_id'] == cid
    assert info['title'] == "Test Ch"
    assert info['mode'] == "request"
    assert info['auto_approve'] is True

    # Update mode
    await mock_db.update_fsub_mode(cid, "normal")
    info = await mock_db.get_fsub_info(cid)
    assert info['mode'] == "normal"

    # Toggle auto_approve
    await mock_db.set_fsub_auto_approve(cid, False)
    info = await mock_db.get_fsub_info(cid)
    assert info['auto_approve'] is False

    # Remove all
    await mock_db.remove_all_fsub_channels()
    assert len(await mock_db.get_fsub_channels()) == 0
