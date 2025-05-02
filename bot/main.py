#!/usr/bin/env python
# pylint: disable=unused-argument
# This program is dedicated to the public domain under the CC0 license.

"""
Simple Bot to reply to Telegram messages.

First, a few handler functions are defined. Then, those functions are passed to
the Application and registered at their respective places.
Then, the bot is started and runs until we press Ctrl-C on the command line.

Usage:
Basic Echobot example, repeats messages.
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""
import asyncio
import atexit
import json
import logging
import os
import signal
import subprocess
import threading

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
load_dotenv()

# Load env vars
TOKEN: str = os.getenv("BOT_TOKEN")
STREAM_URL = os.getenv("STREAM_URL")
if TOKEN is None or STREAM_URL is None:
    logger.error("BOT_TOKEN or STREAM_URL is None. Fix your env vars.")
    exit(1)

# Set of tuples (PID, Anime Episode Name)
# Global lock and state
ffmpeg_lock = threading.Lock()
ffmpeg_instances: set[tuple[int, str]] = set()


def run_ani_cli(anime: str, range_ep: str, idx: str) -> str:
    """Runs ani-cli and returns the output"""
    cmd = [
        '/home/urpagin/Documents/PROGRAMMING/other/ani-cli-telegram/ani-cli',
        anime,
        '-S', idx,
        '-e', range_ep,
    ]

    # Capture both stdout and stderr so you pick up the JSON blob
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        # check=True,
        text=True,
    )

    return proc.stdout.strip()


def cleanup_ffmpeg():
    """Kill all the ffmpeg processes."""
    with ffmpeg_lock:
        for pid, _ in ffmpeg_instances:
            try:
                kill_sig = signal.SIGTERM
                os.waitpid(pid, 0)
                os.kill(pid, kill_sig)
                logger.info(f"KILLED PID {pid} with signal {kill_sig}!")
            except ProcessLookupError:
                pass
            except PermissionError:
                # cannot kill it
                raise
        ffmpeg_instances.clear()
        logger.info(f"Cleaned up {len(ffmpeg_instances)} ffmpeg instances")


atexit.register(cleanup_ffmpeg)


def ffmpeg_stream(
        stream_url: str,
        referer: str,
        episode_url: str,
        episode_name: str) -> int:
    """
    Streams the media to the RTMPS server via ffmpeg.
    If previous_pid is given, terminate that process first.
    Returns the PID of the newly-launched ffmpeg.
    """
    # Terminate previous processes, if any
    with ffmpeg_lock:
        if ffmpeg_instances:
            for pid, _ in ffmpeg_instances:
                try:
                    os.kill(pid, signal.SIGTERM)
                    os.waitpid(pid, 0)
                    logger.info(f"Killed old PID {pid}")
                except ProcessLookupError:
                    pass
            ffmpeg_instances.clear()

    # 2) build and launch the new ffmpeg process
    cmd = [
        "ffmpeg",
        "-re",
        "-headers", f"Referer: {referer}\r\n",
        "-i", episode_url,
        "-c", "copy",
        "-f", "flv",
        stream_url,
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,  # send ffmpeg’s stdout to /dev/null
        stderr=subprocess.STDOUT  # funnel stderr into stdout (which is /dev/null)
    )

    pid = proc.pid
    ffmpeg_instances.add((pid, episode_name))
    logger.info(f"Started ffmpeg PID={pid} for {episode_name}")
    return pid


def input_to_stream(anime: str, range_ep: str, idx: str) -> str:
    logger.info(f"input_to_stream() input: {anime=} {range_ep=}")

    cmd_output: str = run_ani_cli(anime, range_ep, idx)
    logger.info(f"Raw output: {cmd_output}")

    cmd_json: str = cmd_output.split('\n')[-1]
    logger.info(f"Raw json: {cmd_json}")

    # If it’s JSON, load it:
    try:
        args = json.loads(cmd_json)

        ref: str = args[0].split('=')[-1]
        ep_url: str = args[1] if args[1] else f"Error:\n{cmd_output}"
        ep_name: str = args[2]
    except json.JSONDecodeError:
        raise RuntimeError(f"Expected JSON but got:\n{cmd_json}")

    ffmpeg_stream(STREAM_URL, ref, ep_url, ep_name)
    return ep_name


async def anime_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "Usage: /anime <anime name> % <episode> % <entry number>\n"
            "e.g.: /anime blue lock % 5 % 1"
        )
        return

    anime, range_ep, idx, *_ = " ".join(context.args).split("%")
    anime = anime.strip()
    range_ep = range_ep.strip()
    idx = idx.strip()
    await update.message.reply_text(
        f"Searching for episode {range_ep} of {anime}... (Selecting the {idx}th entry on the result list)")

    try:
        # offload the blocking work to a thread:
        loop = asyncio.get_running_loop()
        episode = await loop.run_in_executor(
            None,
            input_to_stream,
            anime,
            range_ep,
            idx
        )

        await update.message.reply_text(
            f"Streaming {episode}!\n"
            "Please wait, there is a delay of about 15 seconds."
        )
    except Exception as e:
        await update.message.reply_text(
            f"Failed to play anime: {e}"
        )
        raise e


async def playing_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with ffmpeg_lock:
        if not ffmpeg_instances:
            await update.message.reply_text("Nothing is playing. Use the /anime command to play something!")
            return

        res: str = 'Currently playing: '
        for pid, ep_name in ffmpeg_instances:
            res += f'{ep_name} (ffmpeg pid={pid})\n'

        await update.message.reply_text(res)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Execute these commands for more detail about them:\n- /anime\n- /playing")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and notify the user."""
    # Log full stack trace
    logger.error("Unhandled exception in update %s", update, exc_info=context.error)

    # Inform the user (if possible)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ An unexpected error occurred. Please try again later."
        )


def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("anime", anime_command))
    application.add_handler(CommandHandler("playing", playing_command))

    # Register the error handler
    application.add_error_handler(error_handler)

    # Run the bot until the user presses Ctrl-C
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
