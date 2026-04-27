"""Top-level CLI for claude-voice."""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console

from claude_voice import __version__

console = Console()


@click.group(help="Add voice (TTS + STT) to Claude Code.")
@click.version_option(__version__)
def main() -> None:
    pass


@main.command(help="Register the Stop hook in ~/.claude/settings.json.")
def install() -> None:
    from claude_voice.install import install_hooks

    path, added = install_hooks()
    if added:
        console.print(f"[green]Installed[/green] Stop hook in [bold]{path}[/bold]")
    else:
        console.print(f"[yellow]Already installed[/yellow] in [bold]{path}[/bold]")


@main.command(help="Remove the Stop hook from ~/.claude/settings.json.")
def uninstall() -> None:
    from claude_voice.install import uninstall_hooks

    path, removed = uninstall_hooks()
    if removed:
        console.print(f"[green]Removed[/green] Stop hook from [bold]{path}[/bold]")
    else:
        console.print(f"[yellow]No hook to remove[/yellow] in [bold]{path}[/bold]")


@main.command(help="Run the push-to-talk daemon (foreground).")
def listen() -> None:
    from claude_voice.hotkey import PushToTalk

    PushToTalk().run()


@main.command(help="Speak text using the system TTS engine.")
@click.argument("text", nargs=-1, required=True)
def speak(text: tuple[str, ...]) -> None:
    from claude_voice import filters, tts

    body = " ".join(text)
    cleaned = filters.clean_for_speech(body)
    tts.speak(cleaned, blocking=True)


@main.command(help="Record 5 seconds and print the transcription. Useful for testing.")
@click.option("--seconds", "-s", default=5.0, show_default=True, help="Seconds to record.")
def transcribe(seconds: float) -> None:
    import time

    from claude_voice.audio import Recorder
    from claude_voice import stt

    rec = Recorder()
    console.print(f"Recording for [bold]{seconds:.1f}s[/bold]...")
    rec.start()
    time.sleep(seconds)
    audio = rec.stop()
    console.print("Transcribing...")
    text = stt.transcribe(audio)
    console.print(f"[green]{text or '(no speech detected)'}[/green]")


@main.group(help="Hook entry points called by Claude Code (internal).")
def hook() -> None:
    pass


@hook.command("stop", help="Stop-hook handler. Reads Claude Code payload from stdin.")
def hook_stop() -> None:
    from claude_voice.hooks import stop_hook

    sys.exit(stop_hook())


@main.command(help="Diagnose audio devices, model, hooks, and platform support.")
def doctor() -> None:
    import platform

    from claude_voice.audio import list_input_devices
    from claude_voice.install import HOOK_COMMAND, _settings_path

    console.rule("[bold]claude-voice doctor[/bold]")
    console.print(f"Python:   [bold]{sys.version.split()[0]}[/bold]")
    console.print(f"Platform: [bold]{platform.platform()}[/bold]")

    # Audio devices
    try:
        devices = list_input_devices()
        console.print(f"\nInput devices ({len(devices)}):")
        for d in devices[:5]:
            console.print(f"  - {d['name']}")
        if len(devices) > 5:
            console.print(f"  ... and {len(devices) - 5} more")
    except Exception as exc:
        console.print(f"[red]Audio error:[/red] {exc}")

    # Hook state
    settings = _settings_path()
    if settings.exists():
        text = settings.read_text(encoding="utf-8")
        installed = HOOK_COMMAND in text
        console.print(
            f"\nStop hook in {settings}: "
            + ("[green]registered[/green]" if installed else "[yellow]not registered[/yellow]")
        )
    else:
        console.print(f"\n[yellow]{settings} does not exist yet[/yellow]")

    # Whisper model directory hint
    cache = Path.home() / ".cache" / "huggingface"
    if cache.exists():
        console.print(f"\nWhisper cache: [bold]{cache}[/bold]")
    else:
        console.print(
            f"\nWhisper cache: not yet downloaded — first transcribe call will fetch ~150 MB."
        )


if __name__ == "__main__":
    main()
