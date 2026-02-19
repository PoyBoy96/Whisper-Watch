# Whisper Watch Team Rollout

## Direct answer: do teammates need Whisper installed?

No. They do **not** need to install Whisper or Python when using the packaged app.

Your current `WhisperWatch.exe` bundle already includes the transcription runtime (`faster-whisper` and dependencies).

What each machine still needs in local mode:

- Enough disk/RAM for model use.
- First run model download (for `large-v3`) unless you pre-seed model cache.

## Exactly what to send your team (today)

Use this if you want everyone running the app locally.

1. Send `dist\WhisperWatch\` as a zip (portable package).
2. Include these run steps in your team message:
   - Unzip anywhere (for example `C:\Apps\WhisperWatch`).
   - Run `WhisperWatch.exe`.
   - Drag/drop media and transcribe.
3. Tell them first launch may download model files.
4. Tell them where SRT exports go by default:
   - `C:\Users\<User>\Downloads\WhisperWatch`

If you build an installer later, send this single file instead:

- `dist-installer\WhisperWatchSetup.exe`

## Better approach for one network (recommended)

If you do **not** want model/runtime duplicated on every PC, run one central transcription host:

1. Pick one strong machine on your LAN as the Whisper server.
2. Install and run Whisper Watch service there (single model cache, single queue).
3. Teammates upload files to that host via browser/client.
4. Server performs transcription and returns SRT/text.

Benefits:

- No Whisper runtime or model on every user machine.
- One shared queue and predictable performance.
- Centralized updates.

Tradeoff:

- Requires server uptime and basic LAN service setup.

## Suggested team message template

```
Whisper Watch is ready.

Install: unzip attached WhisperWatch package and run WhisperWatch.exe.
No Python/Whisper install required.

First launch may take longer while model files are prepared.
Default SRT output folder:
C:\Users\<YourUser>\Downloads\WhisperWatch

If you want central/shared processing instead of local machine processing, tell me and I’ll move us to a single LAN server deployment.
```

