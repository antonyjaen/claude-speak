"""Global push-to-talk loop: hold a key, speak, release to type transcription."""
from __future__ import annotations

import os
import threading
import time
from typing import Optional

from pynput import keyboard

from claude_voice.audio import Recorder
from claude_voice import stt


def _hotkey_name() -> str:
    return os.environ.get("CLAUDE_VOICE_HOTKEY", "f9").lower()


def _resolve_hotkey(name: str):
    """Map a string like 'f9' or 'right_ctrl' to a pynput Key/KeyCode."""
    name = name.strip().lower().replace(" ", "_")
    if hasattr(keyboard.Key, name):
        return getattr(keyboard.Key, name)
    if len(name) == 1:
        return keyboard.KeyCode.from_char(name)
    raise ValueError(f"Unknown hotkey: {name!r}")


def _is_match(key, target) -> bool:
    if key == target:
        return True
    if hasattr(key, "vk") and hasattr(target, "vk") and key.vk and target.vk:
        return key.vk == target.vk
    return False


def _auto_submit() -> bool:
    return os.environ.get("CLAUDE_VOICE_AUTO_SUBMIT", "0") not in ("0", "", "false", "False")


class PushToTalk:
    def __init__(self) -> None:
        self.hotkey = _resolve_hotkey(_hotkey_name())
        self.recorder = Recorder()
        self.controller = keyboard.Controller()
        self._recording = False
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    def _on_press(self, key) -> None:
        if not _is_match(key, self.hotkey):
            return
        with self._lock:
            if self._recording:
                return
            self._recording = True
        try:
            self.recorder.start()
            self._info("Recording... (release to transcribe)")
        except Exception as exc:  # pragma: no cover
            self._error(f"Recorder failed to start: {exc}")
            with self._lock:
                self._recording = False

    def _on_release(self, key) -> None:
        if not _is_match(key, self.hotkey):
            return
        with self._lock:
            if not self._recording:
                return
            self._recording = False
        threading.Thread(target=self._finish_capture, daemon=True).start()

    def _finish_capture(self) -> None:
        try:
            audio = self.recorder.stop()
        except Exception as exc:  # pragma: no cover
            self._error(f"Recorder stop failed: {exc}")
            return

        duration = len(audio) / 16000.0
        if duration < 0.25:
            self._info(f"Skipped — too short ({duration:.2f}s)")
            return

        self._info(f"Transcribing {duration:.2f}s...")
        t0 = time.monotonic()
        try:
            text = stt.transcribe(audio).strip()
        except Exception as exc:
            self._error(f"Transcription failed: {exc}")
            return
        elapsed = time.monotonic() - t0

        if not text:
            self._info(f"(no speech detected, {elapsed:.2f}s)")
            return

        self._info(f'"{text}"  ({elapsed:.2f}s)')
        self._type(text)

    def _type(self, text: str) -> None:
        try:
            self.controller.type(text)
            if _auto_submit():
                self.controller.press(keyboard.Key.enter)
                self.controller.release(keyboard.Key.enter)
        except Exception as exc:  # pragma: no cover
            self._error(f"Could not type: {exc}")

    # ---- output ----
    def _info(self, msg: str) -> None:
        print(f"[claude-voice] {msg}", flush=True)

    def _error(self, msg: str) -> None:
        print(f"[claude-voice] ERROR: {msg}", flush=True)

    # ---- main loop ----
    def run(self) -> None:
        self._info(f"Listening (hotkey: {_hotkey_name()}). Ctrl+C to quit.")
        # Warm up the model in the background so the first transcription is snappy.
        threading.Thread(target=stt.warmup, daemon=True).start()

        with keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        ) as listener:
            try:
                while not self._stop_event.is_set():
                    self._stop_event.wait(0.5)
            except KeyboardInterrupt:
                self._info("Shutting down...")
            finally:
                listener.stop()
