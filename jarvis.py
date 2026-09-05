import sys
import os
import asyncio
import edge_tts
import threading
import uuid
import time
import subprocess
import re

from datetime import datetime, timedelta

from core.reminder import (
    add_reminder,
    get_due_reminders,
    delete_reminder,
    list_reminders
)

from core.brain import Brain
from core.system_control import handle_system_command
from services.app_control import open_app
from services.system_actions import handle_system_action

VOICE = "en-US-GuyNeural"

audio_process = None
browser_ai = None
is_speaking = False

FAST_COMMANDS = {
    "time": [
        "time",
        "what time",
        "current time"
    ],

    "battery": [
        "battery",
        "battery percentage"
    ],

    "brightness": [
        "brightness"
    ],

    "volume": [
        "volume"
    ],

    "screenshot": [
        "screenshot",
        "take screenshot"
    ]
}


def get_browser_ai():

    global browser_ai

    if browser_ai is None:

        print("[BOOT] Loading Browser AI...")

        from services.browser_ai import browser_ai as loaded_browser_ai

        browser_ai = loaded_browser_ai

        print("[BOOT] Browser AI Loaded")

    return browser_ai


def load_vision_service():

    print("[BOOT] Loading Vision Service...")

    from services.vision_service import VisionService

    vision = VisionService(
        on_known=on_ankur_detected,
        on_unknown=on_unknown_detected
    )

    print("[BOOT] Vision Service Loaded")

    return vision


def load_voice_service():

    print("[BOOT] Loading Voice Service...")

    from services.voice_service import VoiceService

    mic = VoiceService()

    print("[BOOT] Voice Service Loaded")

    return mic


def fast_intent(user_input):

    text = user_input.lower()

    # ── TIME ─────────────────────────────
    if any(

        re.search(
            rf"\b{re.escape(x)}\b",
            text
        )

        for x in FAST_COMMANDS["time"]
    ):

        return "time now"

    # ── BATTERY ──────────────────────────
    if any(

        re.search(
            rf"\b{re.escape(x)}\b",
            text
        )

        for x in FAST_COMMANDS["battery"]
    ):

        return "battery"

    # ── SCREENSHOT ───────────────────────
    if any(

        re.search(
            rf"\b{re.escape(x)}\b",
            text
        )

        for x in FAST_COMMANDS["screenshot"]
    ):

        return "take screenshot"

    # ── BRIGHTNESS ───────────────────────
    if re.search(r"\bbrightness\b", text):

        match = re.search(r"(\d+)", text)

        if match:

            value = match.group(1)

            return f"set brightness {value}"

        if "up" in text:

            return "brightness up"

        if "down" in text:

            return "brightness down"

    # ── VOLUME ───────────────────────────
    if re.search(r"\bvolume\b", text):

        if "up" in text:

            return "volume up"

        if "down" in text:

            return "volume down"

    return None


async def speak_async(text: str):

    filename = f"jarvis_{uuid.uuid4().hex}.mp3"

    communicate = edge_tts.Communicate(
        text,
        VOICE
    )

    await communicate.save(filename)

    return filename


def _speak_worker(text: str):

    global audio_process

    print(f"\nJARVIS: {text}\n")

    try:

        filename = asyncio.run(
            speak_async(text)
        )

        if audio_process:

            try:

                audio_process.kill()

                audio_process.wait()

            except:
                pass

        audio_process = subprocess.Popen(
            ["afplay", filename]
        )

        audio_process.wait()

        if os.path.exists(filename):

            os.remove(filename)

    except Exception as e:

        print(f"[Voice error]: {e}")


def speak(text: str):

    thread = threading.Thread(
        target=_speak_worker,
        args=(text,),
        daemon=True
    )

    thread.start()


def stop_speaking():

    global audio_process

    if audio_process:

        try:

            audio_process.kill()

            audio_process.wait()

            audio_process = None

        except:
            pass


def on_ankur_detected():

    speak("Welcome back sir.")


def on_unknown_detected():

    speak("Warning sir. Unknown person detected.")


def safe_stop_vision(vision):

    try:

        if vision:

            vision.stop()

    except:
        pass


def normalize_numbers(text):

    return (
        text
        .replace("one", "1")
        .replace("two", "2")
        .replace("three", "3")
        .replace("four", "4")
        .replace("five", "5")
        .replace("six", "6")
        .replace("seven", "7")
        .replace("eight", "8")
        .replace("nine", "9")
        .replace("ten", "10")
        .replace("fifteen", "15")
        .replace("twenty", "20")
        .replace("thirty", "30")
        .replace("forty", "40")
        .replace("fifty", "50")
        .replace("sixty", "60")
    )


def process_input(
    user_input,
    brain,
    vision,
    last_command,
    last_topic
):

    user_input = (
        user_input
        .strip()
        .lower()
    )

    user_input = normalize_numbers(user_input)

    fast_command = fast_intent(user_input)

    if fast_command:

        print(
            f"[Fast Intent]: {fast_command}"
        )

        system_reply = handle_system_command(
            fast_command
        )

        if system_reply:

            speak(system_reply)

            return vision, fast_command, "system"

    if user_input in [
        "clear memory",
        "forget everything"
    ]:

        brain.clear_memory()

        speak("Memory cleared sir.")

        return vision, last_command, last_topic

    if any(
        x in user_input
        for x in [
            "start vision",
            "open camera",
            "start camera",
            "activate vision"
        ]
    ):

        if vision is None:

            vision = load_vision_service()

        speak(vision.start())

        return vision, last_command, last_topic

    if any(
        x in user_input
        for x in [
            "stop vision",
            "close camera",
            "stop camera",
            "deactivate vision"
        ]
    ):

        if vision:

            speak(vision.stop())

        else:

            speak("Vision is not active, sir.")

        return vision, last_command, last_topic

    if any(
        x in user_input
        for x in [
            "what is this",
            "check webcam",
            "what am i showing",
            "analyze this",
            "look at this",
            "analyze object",
            "what do you see"
        ]
    ):

        speak(
            "Analyzing, sir. Give me a moment."
        )

        from vision_ai import describe_scene, answer_question

        if (
            "what is this" in user_input
            or "what do you see" in user_input
        ):

            result = answer_question(
                "What object or thing is shown? "
                "Be specific and brief."
            )

        else:

            result = describe_scene()

        speak(result)

        return vision, last_command, last_topic

    if user_input.startswith("play "):

        query = (
            user_input
            .replace("play ", "")
            .strip()
        )

        speak(
            f"Searching for {query}, sir."
        )

        browser = get_browser_ai()

        result = browser.search_youtube(
            query
        )

        speak(result)

        return vision, last_command, last_topic

    if user_input in [
        "pause",
        "resume",
        "pause video",
        "resume video"
    ]:

        browser = get_browser_ai()

        result = browser.pause_video()

        speak(result)

        return vision, last_command, last_topic

    if (
        "next video" in user_input
        or "next song" in user_input
    ):

        browser = get_browser_ai()

        result = browser.next_video()

        speak(result)

        return vision, last_command, last_topic

    if "fullscreen" in user_input:

        browser = get_browser_ai()

        result = browser.fullscreen()

        speak(result)

        return vision, last_command, last_topic

    if (
        "skip ad" in user_input
        or "skip the ad" in user_input
    ):

        browser = get_browser_ai()

        result = browser.skip_ad()

        speak(result)

        return vision, last_command, last_topic

    if (
        "close browser" in user_input
        or "close youtube" in user_input
    ):

        browser = get_browser_ai()

        result = browser.close_browser()

        speak(result)

        return vision, last_command, last_topic

    if (
        "what is playing" in user_input
        or "now playing" in user_input
    ):

        browser = get_browser_ai()

        result = browser.now_playing()

        speak(result)

        return vision, last_command, last_topic

    if "unmute" in user_input:

        browser = get_browser_ai()

        result = browser.mute_video()

        speak(result)

        return vision, last_command, last_topic

    if "mute" in user_input:

        browser = get_browser_ai()

        result = browser.mute_video()

        speak(result)

        return vision, last_command, last_topic

    if user_input.startswith("open "):

        app_name = (
            user_input
            .replace("open ", "")
            .strip()
        )

        result = open_app(app_name)

        speak(result)

        return vision, last_command, last_topic

    # ── LIST REMINDERS ───────────────────────────

    if any(x in user_input for x in [
        "list reminders",
        "show reminders",
        "what are my reminders",
        "what reminders",
        "my reminders"
    ]):

        reminders = list_reminders()

        if not reminders:

            speak("You have no pending reminders, sir.")

        else:

            speak(
                f"You have {len(reminders)} reminder"
                f"{'s' if len(reminders) > 1 else ''}, sir."
            )

            for i, r in enumerate(reminders, 1):

                speak(
                    f"Reminder {i}: {r['task']} "
                    f"at {r['time']}"
                )

        return vision, last_command, last_topic

    # ── DELETE REMINDER ──────────────────────────

    if any(x in user_input for x in [
        "delete reminder",
        "cancel reminder",
        "remove reminder",
        "delete the reminder",
        "cancel the reminder",
        "remove the reminder"
    ]):

        reminders = list_reminders()

        if not reminders:

            speak("You have no pending reminders, sir.")

        elif len(reminders) == 1:

            delete_reminder(reminders[0]["task"])

            speak(
                f"Reminder for {reminders[0]['task']} "
                f"deleted, sir."
            )

        else:

            # ask brain which reminder to delete
            tasks = ", ".join(
                [r["task"] for r in reminders]
            )

            task_to_delete = brain.think(
                f"The user said: '{user_input}'. "
                f"These are the current reminders: {tasks}. "
                f"Reply with ONLY the exact task name to delete, "
                f"nothing else."
            )

            result = delete_reminder(task_to_delete)

            if result:

                speak(
                    f"Reminder for {task_to_delete} "
                    f"deleted, sir."
                )

            else:

                speak(
                    "Could not find that reminder, sir."
                )

        return vision, last_command, last_topic

    # ── SET REMINDERS ────────────────────────────

    if any(x in user_input for x in [
        "remind",
        "reminder",
        "remember",
        "don't let me forget",
        "dont let me forget"
    ]):

        hours_match = re.search(
            r"(\d+)\s*hour[s]?",
            user_input
        )

        minutes_match = re.search(
            r"(\d+)\s*minute[s]?",
            user_input
        )

        # ── named time e.g. at 5pm ────────────────
        time_match = re.search(
            r"at (\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
            user_input
        )

        total_minutes = 0

        reminder_time = None

        if hours_match:

            total_minutes += int(hours_match.group(1)) * 60

        if minutes_match:

            total_minutes += int(minutes_match.group(1))

        if total_minutes > 0:

            reminder_time = (
                datetime.now()
                + timedelta(minutes=total_minutes)
            )

        elif time_match:

            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            period = time_match.group(3)

            if period == "pm" and hour != 12:
                hour += 12

            if period == "am" and hour == 12:
                hour = 0

            reminder_time = datetime.now().replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0
            )

            # if time already passed today set for tomorrow
            if reminder_time < datetime.now():

                reminder_time += timedelta(days=1)

        if reminder_time:

            task = brain.think(
                f"The user wants to set a reminder. "
                f"Extract ONLY the thing they want to be reminded about "
                f"from this sentence, in 2-4 words, nothing else, "
                f"no time information: '{user_input}'"
            )

            formatted_time = reminder_time.strftime(
                "%Y-%m-%d %H:%M"
            )

            add_reminder(task, formatted_time)

            if hours_match and minutes_match:

                speak(
                    f"Reminder set for "
                    f"{hours_match.group(1)} hour"
                    f"{'s' if int(hours_match.group(1)) > 1 else ''} "
                    f"and {minutes_match.group(1)} minute"
                    f"{'s' if int(minutes_match.group(1)) > 1 else ''}"
                    f", sir."
                )

            elif hours_match:

                h = int(hours_match.group(1))

                speak(
                    f"Reminder set for {h} hour"
                    f"{'s' if h > 1 else ''}, sir."
                )

            elif minutes_match:

                m = int(minutes_match.group(1))

                speak(
                    f"Reminder set for {m} minute"
                    f"{'s' if m > 1 else ''}, sir."
                )

            elif time_match:

                speak(
                    f"Reminder set for "
                    f"{reminder_time.strftime('%I:%M %p')}, sir."
                )

            return vision, last_command, last_topic

    system_action = handle_system_action(
        user_input
    )

    if system_action:

        speak(system_action)

        return vision, last_command, last_topic

    followup_triggers = [
        "and in",
        "what about",
        "how about",
        "and there",
        "what about in",
        "how about in",
        "and what about"
    ]

    is_followup = any(
        t in user_input
        for t in followup_triggers
    )

    if is_followup and last_command:

        result = brain.interpret_followup(
            user_input,
            last_command,
            last_topic
        )

        full_command = (
            result[0]
            if isinstance(result, tuple)
            else result
        )

        topic_type = (
            result[1]
            if isinstance(result, tuple)
            else "conversation"
        )

        print(
            f"[Interpreted as]: "
            f"{full_command} [{topic_type}]"
        )

        if topic_type == "system":

            system_reply = handle_system_command(
                full_command
            )

            if system_reply:

                speak(system_reply)

                return vision, full_command, "system"

        reply = brain.think(full_command)

        speak(reply)

        return vision, full_command, "conversation"

    intent = brain.get_intent(user_input)

    print(f"[Intent]: {intent}")

    if intent != "conversation":

        system_reply = handle_system_command(
            intent
        )

        if system_reply:

            speak(system_reply)

            return vision, intent, "system"

    reply = brain.think(user_input)

    speak(reply)

    return vision, user_input, "conversation"


def run():

    print("=================================")
    print("   J.A.R.V.I.S  BOOTING UP...   ")
    print("=================================\n")

    print("[1] Text only")
    print("[2] Voice + Text")
    print("[3] Wake Word — say JARVIS to activate")

    mode = input(
        "Choose mode (1, 2 or 3): "
    ).strip()

    use_voice = mode in ["2", "3"]

    use_wake_word = mode == "3"

    print("[BOOT] Loading Brain...")

    brain = Brain()

    print("[BOOT] Brain Loaded")

    # ── Reminder Watcher Thread ───────────────
    def reminder_watcher():

        while True:

            try:

                due = get_due_reminders()

                for reminder in due:

                    speak(
                        f"Reminder sir. {reminder['task']}"
                    )

            except Exception as e:

                print(f"[Reminder Error]: {e}")

            time.sleep(15)

    threading.Thread(
        target=reminder_watcher,
        daemon=True
    ).start()

    print("[BOOT] Reminder Watcher Started")

    vision = None

    mic = None

    if use_voice:

        try:

            mic = load_voice_service()

            if use_wake_word:

                speak(
                    "JARVIS online. "
                    "Say JARVIS anytime "
                    "to activate me, sir."
                )

            else:

                speak(
                    "Welcome back sir. "
                    "Voice mode activated."
                )

        except Exception as e:

            print(f"[Mic error]: {e}")

            use_voice = False

            use_wake_word = False

            speak(
                "Welcome back sir. "
                "Text mode activated."
            )

    else:

        speak(
            "Welcome back sir. "
            "Text mode activated."
        )

    last_command = ""

    last_topic = ""

    while True:

        try:

            if use_wake_word and mic:

                try:

                    mic.listen_for_wake_word()

                except Exception as e:

                    print(
                        f"[Wake Error]: {e}"
                    )

                    time.sleep(2)

                    mic = load_voice_service()

                    continue

                speak("Yes sir?")

                active_timeout = 20

                last_interaction = time.time()

                while True:

                    try:

                        user_input = mic.listen(
                            timeout=5
                        )

                    except Exception as e:

                        print(
                            f"[Mic Recover]: {e}"
                        )

                        time.sleep(2)

                        mic = load_voice_service()

                        break

                    if not user_input:

                        if (
                            time.time()
                            - last_interaction
                            < active_timeout
                        ):

                            continue

                        break

                    last_interaction = time.time()

                    user_input = (
                        user_input
                        .strip()
                        .lower()
                    )

                    if user_input in [
                        "quit",
                        "exit",
                        "bye jarvis",
                        "goodbye jarvis",
                        "shutdown jarvis"
                    ]:

                        speak("Goodbye sir.")

                        safe_stop_vision(vision)

                        sys.exit(0)

                    if user_input in [
                        "sleep",
                        "go to sleep",
                        "stop listening"
                    ]:

                        break

                    vision, last_command, last_topic = process_input(
                        user_input,
                        brain,
                        vision,
                        last_command,
                        last_topic
                    )

                continue

            if use_voice and mic:

                print("[JARVIS] Listening...")

                try:

                    user_input = mic.listen()

                except Exception as e:

                    print(
                        f"[Voice Recover]: {e}"
                    )

                    time.sleep(2)

                    mic = load_voice_service()

                    continue

                if not user_input:
                    continue

            else:

                user_input = input(
                    "You: "
                ).strip().lower()

            if not user_input:
                continue

            if user_input in [
                "quit",
                "exit",
                "bye jarvis",
                "goodbye jarvis"
            ]:

                speak(
                    "Goodbye sir. "
                    "Shutting down."
                )

                safe_stop_vision(vision)

                break

            if user_input == "switch mode":

                use_voice = not use_voice

                if use_voice and mic is None:

                    try:

                        mic = load_voice_service()

                    except Exception as e:

                        print(f"[Mic error]: {e}")

                        use_voice = False

                        speak(
                            "Could not start voice mode, sir."
                        )

                        continue

                speak(
                    "Switched to voice mode, sir."
                    if use_voice
                    else "Switched to text mode, sir."
                )

                continue

            vision, last_command, last_topic = process_input(
                user_input,
                brain,
                vision,
                last_command,
                last_topic
            )

        except KeyboardInterrupt:

            safe_stop_vision(vision)

            speak("Goodbye sir.")

            sys.exit(0)


if __name__ == "__main__":

    run()