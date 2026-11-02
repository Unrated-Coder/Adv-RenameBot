import asyncio
import pytest
import pytest_asyncio
import mongomock_motor
from helper.database import Database
from helper.utils import metadata_text

@pytest.fixture
def mock_db():
    db = Database("mongodb://localhost:27017", "test_db")
    db._client = mongomock_motor.AsyncMongoMockClient()
    db.db = db._client.get_database("test_db")
    db.col = db.db.get_collection("user")
    db.premium = db.db.get_collection("premium")
    return db

@pytest.mark.asyncio
async def test_database_metadata_and_site(mock_db):
    user_id = 123456789

    # Default values check
    mode = await mock_db.get_metadata(user_id)
    assert mode is False

    code = await mock_db.get_metadata_code(user_id)
    assert code == "By :- @Unrated_Coder"

    is_meta_custom = await mock_db.get_metadata_custom_status(user_id)
    assert is_meta_custom is False

    site = await mock_db.get_metadata_site(user_id)
    assert site == "https://www.anireal-anime.top/"

    is_site_custom = await mock_db.get_site_custom_status(user_id)
    assert is_site_custom is False

    class MockUser:
        def __init__(self, uid):
            self.id = uid
            self.mention = "User"
            self.username = "user"
    class MockBot:
        def __init__(self):
            self.mention = "Bot"
        async def send_message(self, *args, **kwargs):
            pass

    await mock_db.add_user(MockBot(), type("Msg", (), {"from_user": MockUser(user_id)})())

    # Set custom metadata code and enable mode
    await mock_db.set_metadata_code(user_id, "By :- @MyCustomChannel", is_custom=True)
    await mock_db.set_metadata(user_id, True)

    assert await mock_db.get_metadata(user_id) is True
    assert await mock_db.get_metadata_code(user_id) == "By :- @MyCustomChannel"
    assert await mock_db.get_metadata_custom_status(user_id) is True

    # Set custom site
    await mock_db.set_metadata_site(user_id, "https://mycustomsite.com", is_custom=True)
    assert await mock_db.get_metadata_site(user_id) == "https://mycustomsite.com"
    assert await mock_db.get_site_custom_status(user_id) is True

@pytest.mark.asyncio
async def test_metadata_text_parsing():
    raw_code = "--change-title {filename}\n--change-author @Unrated_Coder\n--change-video-title {site}"
    filename = "Sample.mp4"
    site = "https://mysite.org"

    author, title, video_title, audio_title, subtitle_title = await metadata_text(raw_code, filename=filename, site=site)

    assert title == "Sample.mp4"
    assert author == "@Unrated_Coder"
    assert video_title == "https://mysite.org"
    assert audio_title is None
    assert subtitle_title is None

@pytest.mark.asyncio
async def test_metadata_text_fallback():
    raw_code = "By :- @Unrated_Coder"
    author, title, video_title, audio_title, subtitle_title = await metadata_text(raw_code)

    assert author == "By :- @Unrated_Coder"
    assert title == "By :- @Unrated_Coder"
    assert video_title == "By :- @Unrated_Coder"

@pytest.mark.asyncio
async def test_progress_status_text():
    from helper.utils import progress_for_pyrogram
    import time
    class MockMsg:
        def __init__(self):
            self.text = ""
            self.edit_count = 0
        async def edit(self, text, reply_markup=None):
            self.text = text
            self.edit_count += 1

    msg = MockMsg()
    start = time.time() - 5
    await progress_for_pyrogram(50, 100, "MyMovie.mkv", msg, start, op_type="download")
    assert "Downloading..." in msg.text
    assert "MyMovie.mkv" in msg.text
    assert "10.0  ʙ/s" in msg.text or "10.0 ʙ/s" in msg.text
    assert msg.edit_count == 1

    # Call immediately again (< 4.0s) - should be rate limited and NOT edit message
    await progress_for_pyrogram(60, 100, "MyMovie.mkv", msg, start, op_type="download")
    assert msg.edit_count == 1

    # Call with current == total - should edit immediately regardless of time interval
    await progress_for_pyrogram(100, 100, "MyMovie.mkv", msg, start, op_type="upload")
    assert "Uploading..." in msg.text
    assert msg.edit_count == 2

@pytest.mark.asyncio
async def test_remove_path_directory_handling(tmp_path):
    from helper.utils import remove_path
    dir_path = tmp_path / "test_dir"
    dir_path.mkdir()

    # remove_path should safely ignore directories without throwing IsADirectoryError
    await remove_path(str(dir_path))
    assert dir_path.exists()

@pytest.mark.asyncio
async def test_stream_languages_parsing(monkeypatch):
    from helper.ffmpeg import get_stream_languages
    import json, asyncio

    fake_json = json.dumps({
        "streams": [
            {"index": 0, "codec_type": "video"},
            {"index": 1, "codec_type": "audio", "tags": {"language": "Japanese"}},
            {"index": 2, "codec_type": "subtitle", "tags": {"language": "English"}},
            {"index": 3, "codec_type": "subtitle", "tags": {}}
        ]
    }).encode('utf-8')

    class DummyProc:
        async def communicate(self):
            return fake_json, b""

    async def dummy_subprocess(*args, **kwargs):
        return DummyProc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", dummy_subprocess)

    audio_langs, sub_langs = await get_stream_languages("test.mkv")
    assert audio_langs == [(0, "Japanese")]
    assert sub_langs == [(0, "English"), (1, None)]

@pytest.mark.asyncio
async def test_change_metadata_clears_old_stream_tags(tmp_path, monkeypatch):
    import os, shutil, subprocess, json
    from helper.ffmpeg import change_metadata

    ffmpeg_bin = shutil.which("ffmpeg") or (os.path.exists("/tmp/bin/ffmpeg") and "/tmp/bin/ffmpeg")
    ffprobe_bin = shutil.which("ffprobe") or (os.path.exists("/tmp/bin/ffprobe") and "/tmp/bin/ffprobe")

    if not ffmpeg_bin or not ffprobe_bin:
        pytest.skip("ffmpeg/ffprobe binary not available for change_metadata test")

    if "/tmp/bin" in str(ffmpeg_bin):
        monkeypatch.setenv("PATH", f"/tmp/bin:{os.environ.get('PATH', '')}")

    input_file = str(tmp_path / "input.mkv")
    output_file = str(tmp_path / "output.mkv")

    # Create test input file with old global and stream metadata
    create_cmd = [
        ffmpeg_bin, "-y",
        "-t", "1", "-f", "lavfi", "-i", "color=c=blue:s=320x240",
        "-t", "1", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-c:v", "mpeg4", "-c:a", "aac",
        "-metadata", "title=Old Global Title",
        "-metadata", "comment=Old Global Comment",
        "-metadata:s:v:0", "title=Old Video Title",
        "-metadata:s:v:0", "comment=Old Video Comment",
        "-metadata:s:v:0", "description=Old Video Description",
        "-metadata:s:v:0", "handler_name=Old Video Handler",
        "-metadata:s:a:0", "title=Old Audio Title",
        "-metadata:s:a:0", "comment=Old Audio Comment",
        input_file
    ]
    subprocess.run(create_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    res = await change_metadata(input_file, output_file, "By :- @NewChannel")
    assert res == output_file
    assert os.path.exists(output_file)

    probe_cmd = [
        ffprobe_bin, "-v", "error",
        "-show_entries", "format_tags:stream_tags",
        "-of", "json", output_file
    ]
    stdout = subprocess.check_output(probe_cmd)
    data = json.loads(stdout.decode('utf-8'))

    # Verify stream tags: old comment/description/handler_name should be gone, handler_name not set
    v_tags = data["streams"][0].get("tags", {})
    a_tags = data["streams"][1].get("tags", {})

    assert v_tags.get("title") == "By :- @NewChannel"
    assert "COMMENT" not in v_tags and "comment" not in v_tags
    assert "DESCRIPTION" not in v_tags and "description" not in v_tags
    assert "HANDLER_NAME" not in v_tags and "handler_name" not in v_tags

    assert a_tags.get("title") == "By :- @NewChannel"
    assert "COMMENT" not in a_tags and "comment" not in a_tags
    assert "HANDLER_NAME" not in a_tags and "handler_name" not in a_tags

    # Verify global format tags
    fmt_tags = data["format"].get("tags", {})
    assert fmt_tags.get("title") == "By :- @NewChannel"


@pytest.mark.asyncio
async def test_ffmpeg_timeout_stops_process():
    from helper.ffmpeg import _communicate_with_timeout

    class SlowProcess:
        returncode = None
        killed = False
        async def communicate(self):
            await asyncio.sleep(1)
        def kill(self):
            self.killed = True
        async def wait(self):
            self.returncode = -9

    process = SlowProcess()
    with pytest.raises(RuntimeError, match="timed out"):
        await _communicate_with_timeout(process, 0.01, "test ffmpeg")
    assert process.killed is True


@pytest.mark.asyncio
async def test_change_metadata_returns_actual_mkv_path_for_ass_mp4(tmp_path, monkeypatch):
    """The caller must upload MKV when FFmpeg switches containers for ASS."""
    import os
    import json
    from helper.ffmpeg import change_metadata

    input_file = str(tmp_path / "input.mp4")
    output_file = str(tmp_path / "output.mp4")
    with open(input_file, "wb") as handle:
        handle.write(b"input")

    class Process:
        def __init__(self, stdout=b"", output=None):
            self.stdout = stdout
            self.output = output
            self.returncode = 0
        async def communicate(self):
            if self.output:
                with open(self.output, "wb") as handle:
                    handle.write(b"output")
            return self.stdout, b""

    calls = []
    async def fake_subprocess(*command, **kwargs):
        calls.append(command)
        if command[0] == "ffprobe" and any("codec_name" in arg for arg in command):
            return Process(b"ass\n")
        if command[0] == "ffprobe":
            return Process(json.dumps({"streams": []}).encode())
        return Process(output=command[-1])

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_subprocess)
    result = await change_metadata(input_file, output_file, "tag")
    assert result == str(tmp_path / "output.mkv")
    assert os.path.exists(result)


@pytest.mark.asyncio
async def test_normalize_thumbnail_single_jpeg_output(tmp_path):
    from PIL import Image
    from helper.ffmpeg import normalize_thumbnail

    thumb = tmp_path / "thumb.png"
    Image.new("RGBA", (20, 10), (255, 0, 0, 128)).save(thumb)
    result = await normalize_thumbnail(str(thumb))
    assert result == str(thumb)
    with Image.open(thumb) as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"
