# Production Telegram benchmark procedure

Run this only on a production-like VPS, using a dedicated bot, premium relay
account, log channel, and disposable test chat. It measures the real pipeline;
synthetic local files do not represent Telegram throughput.

1. Pin the deployed commit and record all environment values that affect this
   test: `MAX_ACTIVE_TRANSFERS`, `MAX_FFMPEG_JOBS`,
   `MAX_CONCURRENT_TRANSMISSIONS`, `FFMPEG_TIMEOUT_SECONDS`, and disk reserve
   settings. Do not record tokens or session strings.
2. Run `python3 scripts/preflight_benchmark.py` from the bot working directory
   and save its JSON output with the commit SHA.
3. Enable INFO logging. The pipeline emits `download`, `ffmpeg_metadata`,
   `ffmpeg_thumbnail`, `upload`, and `cleanup` records with elapsed seconds,
   MiB/s where byte size is known, and active counts.
4. Use valid test media of 100 MiB, 2 GiB, and 4 GiB. For each size, run:
   direct/no metadata; relay/no metadata where applicable; metadata on; custom
   thumbnail; auto thumbnail. Record elapsed time for every stage and whether
   the final Telegram filename/container matches the requested output.
5. Start with one job. Repeat at two concurrent jobs, then increase only one
   configured limit per run. Stop increasing when p95 completion time worsens,
   disk reserve admission rejects jobs, RAM/swap pressure rises, or any retry,
   FloodWait, cleanup failure, or corruption occurs.
6. Capture before/peak/after `df -B1 .`, `free -b`, `iostat -xz 1` (if
   installed), and `pidstat -rud -p <bot-pid> 1` (if installed). Record
   network interface counters and Telegram retry/FloodWait counts.

Report total elapsed time, per-stage elapsed time, download/upload MiB/s,
peak RSS, CPU, disk read/write bytes, disk free space, active transfer/FFmpeg
counts, retries, FloodWaits, failures, and cleanup results. Do not describe a
configuration as faster until this matrix demonstrates it.
