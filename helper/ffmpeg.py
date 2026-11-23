import os, time, asyncio, shlex, math, re, json
from PIL import Image
from helper.utils import metadata_text
from config import Config

async def _stop_process(process):
    if process.returncode is None:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        finally:
            try:
                await process.wait()
            except Exception:
                pass

async def _communicate_with_timeout(process, timeout, label):
    """Drain process pipes while guaranteeing a timeout/cancellation cleanup."""
    try:
        return await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        await _stop_process(process)
        raise RuntimeError(f"{label} timed out after {timeout}s")
    except asyncio.CancelledError:
        await _stop_process(process)
        raise

async def get_stream_languages(input_file):
    audio_langs = []
    sub_langs = []
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=index,codec_type:stream_tags=language,lang,LANGUAGE",
            "-of", "json", input_file
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        if stdout:
            data = json.loads(stdout.decode('utf-8', errors='ignore'))
            audio_idx = 0
            sub_idx = 0
            for stream in data.get("streams", []):
                ctype = stream.get("codec_type")
                tags = stream.get("tags") or {}
                lang = None
                for k, v in tags.items():
                    if k.lower() in ("language", "lang") and v:
                        lang = str(v).strip()
                        break

                if ctype == "audio":
                    audio_langs.append((audio_idx, lang))
                    audio_idx += 1
                elif ctype == "subtitle":
                    sub_langs.append((sub_idx, lang))
                    sub_idx += 1
    except Exception as e:
        print(f"Error probing stream languages: {e}")
    return audio_langs, sub_langs

async def get_attachment_tags(input_file):
    """filename/mimetype of every attachment stream (MKV fonts, cover art...).

    `-map_metadata -1` wipes these tags, and the Matroska muxer then refuses to
    write the file ("Attachment stream N has no filename tag"). We read them
    first and set them again so fonts survive and the remux does not fail.
    """
    result = []
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error", "-select_streams", "t",
            "-show_entries", "stream=index:stream_tags=filename,mimetype",
            "-of", "json", input_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        if stdout:
            data = json.loads(stdout.decode('utf-8', errors='ignore'))
            for position, stream in enumerate(data.get("streams", [])):
                tags = {str(k).lower(): v for k, v in (stream.get("tags") or {}).items()}
                result.append((position, tags.get("filename"), tags.get("mimetype")))
    except Exception as e:
        print(f"Error probing attachment tags: {e}")
    return result

async def fix_thumb(thumb, max_size=320):
    width = 0
    height = 0
    try:
        if thumb and os.path.exists(thumb):
            if os.path.getsize(thumb) == 0:
                try: os.remove(thumb)
                except Exception: pass
                return 0, 0, None

            with Image.open(thumb) as img:
                img = img.convert("RGB")
                width, height = img.size

                # Enforce Maximum thumbnail size
                if width > max_size or height > max_size:
                    if width > height:
                        height = int(height * max_size / width)
                        width = max_size
                    else:
                        width = int(width * max_size / height)
                        height = max_size

                resample_filter = getattr(Image, "Resampling", Image).LANCZOS
                img = img.resize((width, height), resample_filter)
                img.save(thumb, "JPEG", quality=95, optimize=True)
    except Exception as e:
        print(f"Error in fix_thumb: {e}")
        if thumb and os.path.exists(thumb):
            try: os.remove(thumb)
            except Exception: pass
        thumb = None

    return width, height, thumb

async def normalize_thumbnail(thumb):
    """Single decode/convert/encode pass for Telegram-compatible JPEG thumbs."""
    if not thumb or not os.path.isfile(thumb):
        return None
    try:
        with Image.open(thumb) as image:
            image.convert("RGB").save(thumb, "JPEG")
        return thumb
    except Exception as exc:
        print(f"Error normalizing thumbnail: {exc}")
        return None

async def get_duration(file_path):
    try:
        command = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", file_path
        ]
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15)
        except asyncio.TimeoutError:
            try:
                process.kill()
            except Exception:
                pass
            return 0

        if stdout:
            val = stdout.decode().strip()
            if val and val.lower() != "n/a":
                return int(float(val))
    except Exception as e:
        print(f"Error getting duration with ffprobe format: {e}")

    # Fallback to stream duration
    try:
        command = [
            "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", file_path
        ]
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15)
        except asyncio.TimeoutError:
            try:
                process.kill()
            except Exception:
                pass
            return 0

        if stdout:
            val = stdout.decode().strip()
            if val and val.lower() != "n/a":
                return int(float(val))
    except Exception as e:
        print(f"Error getting duration with ffprobe stream: {e}")

    return 0

async def get_video_resolution(file_path):
    try:
        command = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0", file_path
        ]
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15)
        except asyncio.TimeoutError:
            try:
                process.kill()
            except Exception:
                pass
            return 0, 0

        if stdout:
            parts = stdout.decode().strip().split('x')
            if len(parts) == 2:
                return int(parts[0]), int(parts[1])
    except Exception as e:
        print(f"Error getting video resolution with ffprobe: {e}")
    return 0, 0

async def take_screen_shot(video_file, output_directory, ttl):
    out_put_file_name = f"{output_directory}/{time.time_ns()}.jpg"
    for seek_time in [str(ttl), "00:00:01", "00:00:00"]:
        file_genertor_command = [
            "ffmpeg",
            "-y",
            "-nostdin",
            "-threads",
            str(getattr(Config, "FFMPEG_THREADS", 0)),
            "-ss",
            seek_time,
            "-i",
            video_file,
            "-vframes",
            "1",
            "-q:v",
            "2",
            out_put_file_name
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *file_genertor_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15)
            except asyncio.TimeoutError:
                try:
                    process.kill()
                except Exception:
                    pass
                print(f"FFmpeg take_screen_shot timed out for seek_time {seek_time}!")
                continue

            if os.path.exists(out_put_file_name) and os.path.getsize(out_put_file_name) > 0:
                return out_put_file_name
            else:
                if os.path.exists(out_put_file_name):
                    try: os.remove(out_put_file_name)
                    except Exception: pass
        except Exception as e:
            print(f"Error taking screenshot with FFmpeg (seek_time {seek_time}): {e}")
            if os.path.exists(out_put_file_name):
                try: os.remove(out_put_file_name)
                except Exception: pass
    return None

async def add_metadata(input_path, output_path, metadata, site, ms=None, is_custom_site=False, user_id=None):
    try:
        if not os.path.exists(input_path) or os.path.getsize(input_path) == 0:
            return None

        # Determine if we should add site based on user custom site or existing tag
        add_site = True

        if not is_custom_site:
            # If it's NOT a custom site, only replace if OFFICIAL_SITE tag already exists
            probe_site_cmd = [
                "ffprobe", "-v", "error", "-show_entries", "format_tags=OFFICIAL_SITE",
                "-of", "default=noprint_wrappers=1:nokey=1", input_path
            ]
            process = await asyncio.create_subprocess_exec(
                *probe_site_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await process.communicate()
            if not stdout.decode().strip():
                add_site = False

        # Check for ASS/SSA subtitles to decide if we need to force MKV
        if output_path.lower().endswith(".mp4"):
            probe_cmd = [
                "ffprobe", "-v", "error", "-select_streams", "s",
                "-show_entries", "stream=codec_name", "-of", "csv=p=0", input_path
            ]
            probe_proc = await asyncio.create_subprocess_exec(*probe_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, _ = await probe_proc.communicate()
            if b"ass" in stdout or b"ssa" in stdout:
                output_path = output_path.rsplit(".", 1)[0] + ".mkv"

        q_input = shlex.quote(input_path)
        temp_output = f"{output_path}.tmp.{os.getpid()}.{time.time_ns()}"
        q_output = shlex.quote(temp_output)
        q_meta = shlex.quote(metadata)

        cmd = f"ffmpeg -y -threads 0 -i {q_input} -map 0 -c copy -map_metadata -1 -map_metadata:s -1 -map_chapters -1 -metadata title={q_meta} -metadata:s:v title={q_meta} -metadata:s:a title={q_meta} -metadata:s:s title={q_meta} "

        if add_site and site:
            q_site = shlex.quote(site)
            cmd += f"-metadata OFFICIAL_SITE={q_site} "

        cmd += q_output

        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()

        if process.returncode == 0 and os.path.exists(temp_output) and os.path.getsize(temp_output) > 0:
            os.replace(temp_output, output_path)
            return output_path

        if os.path.exists(temp_output):
            try: os.remove(temp_output)
            except Exception: pass
        if stderr:
            print(f"FFmpeg metadata error: {stderr.decode('utf-8', errors='ignore')[-2000:]}")
        return None
    except Exception as e:
        print(f"Error Occurred While Adding Metadata : {str(e)}")
        return None

# Extensions FFmpeg can infer an output muxer for. Anything else is remuxed to MKV.
_KNOWN_OUTPUT_EXTS = {
    ".mkv", ".mp4", ".m4v", ".mov", ".webm", ".avi", ".ts", ".mts", ".m2ts",
    ".flv", ".wmv", ".mpg", ".mpeg", ".3gp", ".ogv", ".mka", ".m4a", ".mp3",
    ".flac", ".ogg", ".opus", ".wav", ".aac",
}
_MP4_LIKE_EXTS = {".mp4", ".m4v", ".mov", ".3gp", ".m4a"}
# Subtitle codecs that cannot be copied (or converted) into MP4-like containers.
_MP4_INCOMPATIBLE_SUBS = (b"ass", b"ssa", b"pgs", b"dvd_sub", b"dvb_sub", b"xsub")
# Failures that a different stream mapping will never fix - stop retrying.
_FATAL_FFMPEG_ERRORS = ("no space left", "permission denied", "read-only file system")

_ROBUST_INPUT_FLAGS = ["-fflags", "+genpts", "-analyzeduration", "100M", "-probesize", "100M"]
_ROBUST_OUTPUT_FLAGS = ["-ignore_unknown", "-max_muxing_queue_size", "9999", "-avoid_negative_ts", "make_zero"]


async def _run_ffmpeg_attempt(cmd, label):
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await _communicate_with_timeout(process, Config.FFMPEG_TIMEOUT_SECONDS, label)
    return process.returncode, (stderr or b"")


async def change_metadata(input_file, output_file, metadata, filename="", site=""):
    """Rewrite container/stream metadata without re-encoding.

    FFmpeg's `-map 0 -c copy` fails on some files (attachments, data/timecode
    tracks, odd subtitle codecs, broken timestamps, MP4-incompatible streams).
    Instead of giving up on the first failure we retry with progressively safer
    stream mappings and, as a last resort, an MKV container. The returned path
    is the file that was actually produced (its extension can change).
    """
    temp_output = None
    try:
        if not os.path.exists(input_file) or os.path.getsize(input_file) == 0:
            return False

        author, title, video_title, audio_title, subtitle_title = await metadata_text(metadata, filename, site)
        meta_tag = title or author or metadata or "Encoded"

        out_root, out_ext = os.path.splitext(output_file)
        out_ext = out_ext.lower()

        # MP4-like containers cannot hold ASS/SSA/PGS/... subtitles -> use MKV up-front.
        if out_ext in _MP4_LIKE_EXTS:
            probe_cmd = [
                "ffprobe", "-v", "error", "-select_streams", "s",
                "-show_entries", "stream=codec_name", "-of", "csv=p=0", input_file
            ]
            try:
                probe_proc = await asyncio.create_subprocess_exec(*probe_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                stdout, _ = await asyncio.wait_for(probe_proc.communicate(), timeout=10)
                if any(codec in stdout for codec in _MP4_INCOMPATIBLE_SUBS):
                    output_file = out_root + ".mkv"
                    out_ext = ".mkv"
            except Exception as e:
                print(f"Error checking sub codec in change_metadata: {e}")

        # Unknown extension (e.g. ".bin", none): FFmpeg cannot pick a muxer.
        if out_ext not in _KNOWN_OUTPUT_EXTS:
            output_file = os.path.splitext(output_file)[0] + ".mkv"
            out_ext = ".mkv"

        v_tag = video_title or meta_tag
        a_tag = audio_title or meta_tag
        s_tag = subtitle_title or meta_tag

        audio_langs, sub_langs = await get_stream_languages(input_file)
        attachments = await get_attachment_tags(input_file)

        def build_cmd(target_ext, temp_path, map_args, codec_args, robust, with_subs, keep_attachments):
            cmd = ['ffmpeg', '-y', '-nostdin', '-hide_banner', '-nostats', '-loglevel', 'error', '-threads', '0']
            if robust:
                cmd += _ROBUST_INPUT_FLAGS
            cmd += ['-i', input_file]
            cmd += map_args
            cmd += codec_args
            cmd += [
                '-map_metadata', '-1',
                '-map_metadata:s', '-1',
                '-map_chapters', '-1',
                '-metadata', f'title={meta_tag}',
                '-metadata', f'author={author or meta_tag}',
                '-metadata', f'artist={author or meta_tag}',
                '-metadata', f'comment={meta_tag}',
                '-metadata', f'encoder={meta_tag}',
                '-metadata:s:v', f'title={v_tag}',
                '-metadata:s:a', f'title={a_tag}',
            ]
            if with_subs:
                cmd += ['-metadata:s:s', f'title={s_tag}']

            for idx, lang in audio_langs:
                if lang:
                    cmd.extend([f'-metadata:s:a:{idx}', f'language={lang}'])
            if with_subs:
                for idx, lang in sub_langs:
                    if lang:
                        cmd.extend([f'-metadata:s:s:{idx}', f'language={lang}'])

            if keep_attachments:
                for idx, att_name, att_mime in attachments:
                    cmd.extend([f'-metadata:s:t:{idx}', f'filename={att_name or f"attachment_{idx}"}'])
                    cmd.extend([f'-metadata:s:t:{idx}', f'mimetype={att_mime or "application/octet-stream"}'])

            if site:
                cmd.extend(['-metadata', f'OFFICIAL_SITE={site}'])
            if robust:
                cmd += _ROBUST_OUTPUT_FLAGS
            if target_ext == '.mkv':
                cmd.extend(['-f', 'matroska'])
            cmd.append(temp_path)
            return cmd

        AV_S = ['-map', '0:v?', '-map', '0:a?', '-map', '0:s?']
        AV = ['-map', '0:v?', '-map', '0:a?', '-sn', '-dn']

        # (label, target extension, map args, codec args, robust flags, keep subtitles, keep attachments)
        attempts = [("full copy", out_ext, ['-map', '0'], ['-c', 'copy'], False, True, True)]
        attempts.append(("v/a/s only", out_ext, AV_S, ['-c', 'copy'], True, True, False))
        if out_ext in _MP4_LIKE_EXTS:
            attempts.append(("subs->mov_text", out_ext, AV_S, ['-c', 'copy', '-c:s', 'mov_text'], True, True, False))
        attempts.append(("video+audio only", out_ext, AV, ['-c', 'copy'], True, False, False))
        if out_ext != '.mkv':
            attempts.append(("mkv container", '.mkv', ['-map', '0'], ['-c', 'copy'], True, True, True))
            attempts.append(("mkv v/a/s only", '.mkv', AV_S, ['-c', 'copy'], True, True, False))

        last_error = ""
        for number, (label, target_ext, map_args, codec_args, robust, with_subs, keep_attachments) in enumerate(attempts, 1):
            final_path = output_file if target_ext == out_ext else os.path.splitext(output_file)[0] + target_ext
            base, ext = os.path.splitext(final_path)
            # Keep the real extension at the end so FFmpeg can always infer the muxer.
            temp_output = f"{base}.tmp.{os.getpid()}.{time.time_ns()}{ext}"

            cmd = build_cmd(target_ext, temp_output, map_args, codec_args, robust, with_subs, keep_attachments)
            returncode, stderr = await _run_ffmpeg_attempt(cmd, f"FFmpeg metadata remux ({label})")

            if returncode == 0 and os.path.exists(temp_output) and os.path.getsize(temp_output) > 0:
                os.replace(temp_output, final_path)
                temp_output = None
                if number > 1:
                    print(f"Metadata added using fallback attempt {number} ({label}).")
                return final_path

            last_error = stderr.decode('utf-8', errors='ignore')[-2000:]
            if os.path.exists(temp_output):
                try: os.remove(temp_output)
                except Exception: pass
            temp_output = None
            print(f"FFmpeg metadata attempt {number}/{len(attempts)} ({label}) failed: {last_error}")

            if any(token in last_error.lower() for token in _FATAL_FFMPEG_ERRORS):
                break

        return None
    except Exception as e:
        if temp_output and os.path.exists(temp_output):
            try: os.remove(temp_output)
            except Exception: pass
        print(f"Error in change_metadata: {e}")
        return None

async def split_large_file(input_path, output_dir, file_size, duration, split_size_mb=1900, progress_callback=None):
    try:
        chunk_size = split_size_mb * 1024 * 1024

        num_chunks = math.ceil(file_size / chunk_size)
        if num_chunks <= 1:
            return [input_path]

        if duration > 0 and file_size > 0:
            chunk_duration = int(((chunk_size * 0.95) / file_size) * duration)
        else:
            chunk_duration = 600

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        base_name = os.path.basename(input_path)
        name, ext = os.path.splitext(base_name)

        safe_name = name.replace('%', '%%')
        safe_ext = ext.replace('%', '%%')
        output_template = f"{output_dir}/{safe_name}.part%03d{safe_ext}"

        command = [
            'ffmpeg', '-y', '-nostdin', '-threads', str(getattr(Config, 'FFMPEG_THREADS', 0)), '-i', input_path,
            '-c', 'copy', '-map', '0',
            '-segment_time', str(chunk_duration),
            '-f', 'segment',
            '-reset_timestamps', '1',
            output_template
        ]

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )

        if progress_callback and duration > 0:
            last_update_time = 0
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                line_str = line.decode('utf-8', errors='ignore')
                match = re.search(r'time=(\d{2}):(\d{2}):(\d{2})', line_str)
                if match:
                    hours, minutes, seconds = map(int, match.groups())
                    current_secs = hours * 3600 + minutes * 60 + seconds
                    percentage = min(100.0, (current_secs / duration) * 100)

                    current_time = time.time()
                    if current_time - last_update_time >= 1.0 or percentage >= 100.0:
                        size_match = re.search(r'size=\s*(\d+)\s*kB', line_str)
                        size_str = ""
                        if size_match:
                            size_kb = int(size_match.group(1))
                            size_bytes = size_kb * 1024
                            from helper.utils import humanbytes
                            size_str = humanbytes(size_bytes)

                        await progress_callback(percentage, size_str)
                        last_update_time = current_time

        stderr_data = []
        if process.stderr:
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
                stderr_data.append(line)

        await process.wait()

        if process.returncode != 0:
            stderr_str = b"".join(stderr_data).decode('utf-8', errors='ignore')
            print(f"FFmpeg Split Error (code {process.returncode}): {stderr_str}")
            return []

        all_files = os.listdir(output_dir)
        chunk_files = [f for f in all_files if f.startswith(name + ".part") and f.endswith(ext)]
        chunks = sorted([os.path.join(output_dir, f) for f in chunk_files])

        return chunks
    except Exception as e:
        print(f"Error splitting file: {e}")
        return []
