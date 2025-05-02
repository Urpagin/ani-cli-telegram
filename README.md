# ani-cli-telegram

> [!IMPORTANT]  
> Only works on systems that can execute bash scripts and use ffmpeg.

## What is it?

Watch any anime with friends on your Telegram group.
You can use the `/anime` command to launch the streaming of an anime.

## Requirements

- ffmpeg
- python3

## Quickstart

1. Make a telegram bot
2. Put the bot token and the stream url in a `.env` file at the root of the project as so:

```
BOT_TOKEN=...
STREAM_URL=...
```

4. Setup python. (make a venv and `pip install -r requirements.txt` in the bot directory)
3. Launch the `bot/main.py` file.
4. Launch the stream from your telegram client. *You can now use the bot*
4. `/help` on your telegram group

## Stream URL

1. Go to your group.
2. Go to the stream settings.
3. Copy the 'Stream Key' and the 'Server URL'.
4. Populate the `.env`'s `STREAM_URL` with this format: `<stream_key><server_url>`
   E.g.: `STREAM_URL=rtmps://bv7-3.rtmp.t.me/s/9264019635:f87dKLOz61Pb7-3lfm8ijz`

## Bot Token

1. https://www.siteguarding.com/en/how-to-get-telegram-bot-api-token
2. Bot Settings > Group Privacy > then disable the privacy mode.
3. Invite your bot to your group. If you've already invited it, kick him and re-invite it.

## Completeness & Quality

"Quick and dirty".