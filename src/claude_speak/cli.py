"""Top-level CLI for claude-speak."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from claude_speak import __version__

console = Console()


def _force_utf8_io() -> None:
    """Avoid cp1252 UnicodeEncodeError when printing window titles, transcribed
    text in non-English languages, or emoji. Affects stdout + stderr."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


@click.group(help="Add voice (TTS + STT) to Claude Code.")
@click.version_option(__version__)
def main() -> None:
    _force_utf8_io()


# ----------------------------------------------------------------------------
@main.command(help="Register the Stop hook in ~/.claude/settings.json.")
def install() -> None:
    from claude_speak.install import install_hooks

    path, added = install_hooks()
    msg = "[green]Installed[/green]" if added else "[yellow]Already installed[/yellow]"
    console.print(f"{msg} Stop hook in [bold]{path}[/bold]")


@main.command(help="Remove the Stop hook from ~/.claude/settings.json.")
def uninstall() -> None:
    from claude_speak.install import uninstall_hooks

    path, removed = uninstall_hooks()
    msg = "[green]Removed[/green]" if removed else "[yellow]No hook to remove[/yellow]"
    console.print(f"{msg} from [bold]{path}[/bold]")


# ----------------------------------------------------------------------------
@main.command(help="Stop any TTS speech currently playing.")
def stop() -> None:
    from claude_speak import pidfile

    pids = pidfile.read_all("playing")
    alive = [p for p in pids if pidfile.is_alive(p)]
    killed = sum(1 for p in alive if pidfile.kill(p))
    pidfile.clear("playing")
    if not alive:
        console.print("[yellow]Nothing playing.[/yellow]")
    else:
        console.print(f"[green]Stopped[/green] {killed}/{len(alive)} player(s).")


# ----------------------------------------------------------------------------
@main.command("voice-help",
              help="Print every claude-speak slash command with a description.")
def voice_help() -> None:
    from claude_speak.commands import _COMMANDS

    console.print("[bold]claude-speak slash commands[/bold]\n")
    for name, desc, _cmd in _COMMANDS:
        console.print(f"  [cyan]/{name:<22}[/cyan] {desc}")
    console.print(
        "\n[dim]Setting tweaks: claude-speak config show / set / reset[/dim]"
    )




@main.command(help="Toggle speak mode between end and narrate.")
def mode() -> None:
    from claude_speak import config as cfg

    current = str(cfg.get("speak_mode", "end")).lower().strip()
    if current in ("narrate", "interview"):
        cfg.set_value("speak_mode", "end")
        console.print("narrate: [yellow]off[/yellow]")
    else:
        cfg.set_value("speak_mode", "narrate")
        console.print("narrate: [green]on[/green]")





@main.command(help="One-line status output for Claude Code's status line.")
def statusline() -> None:
    """Short summary of voice state. ANSI-colored, ASCII-only labels so the
    cp1252 console can render it. Forced UTF-8 stdout for safety."""
    from claude_speak import config as cfg
    from claude_speak import pidfile

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    try:
        if not sys.stdin.isatty():
            sys.stdin.read()
    except Exception:
        pass

    speak_mode = str(cfg.get("speak_mode", "end")).lower()
    speaker_only = bool(cfg.get("speaker_only", False))
    is_playing = any(pidfile.is_alive(p) for p in pidfile.read_all("playing"))

    # Mode indicator — always visible
    if speak_mode in ("narrate", "interview"):
        mode_badge = "\x1b[33m[narrate: on]\x1b[0m"
    else:
        mode_badge = "\x1b[2m[narrate: off]\x1b[0m"

    # Speaker indicator — shown when TTS is active
    if is_playing:
        spk_badge = "\x1b[36m[speaking]\x1b[0m"
    elif speaker_only:
        spk_badge = "\x1b[2m[speaker-only]\x1b[0m"
    else:
        spk_badge = ""

    pieces = [mode_badge]
    if spk_badge:
        pieces.append(spk_badge)
    print(" ".join(pieces))


@main.command(help="Wire claude-speak statusline into ~/.claude/settings.json.")
@click.option("--force", is_flag=True, help="Replace existing statusLine if any.")
def install_statusline(force: bool) -> None:
    from claude_speak.install import install_statusline as _install

    path, action = _install(force=force)
    color = {"installed": "green", "kept": "yellow", "replaced": "green"}[action]
    console.print(f"[{color}]{action}[/{color}] statusLine in [bold]{path}[/bold]")


@main.command(help="Install PreToolUse hook for interview mode (narrates while working). "
                   "Also sets speak_mode=interview in config.")
def install_interview() -> None:
    from claude_speak.install import install_interview_hooks
    from claude_speak import config as cfg

    path, added = install_interview_hooks()
    cfg.set_value("speak_mode", "narrate")
    msg = "[green]Installed[/green]" if added else "[yellow]Already installed[/yellow]"
    console.print(f"{msg} PreToolUse hook in [bold]{path}[/bold]")
    console.print("[green]speak_mode[/green] set to [bold]narrate[/bold]")


@main.command(help="Remove the PreToolUse hook and revert to end mode.")
def uninstall_interview() -> None:
    from claude_speak.install import uninstall_interview_hooks
    from claude_speak import config as cfg

    path, removed = uninstall_interview_hooks()
    cfg.set_value("speak_mode", "end")
    msg = "[green]Removed[/green]" if removed else "[yellow]No hook to remove[/yellow]"
    console.print(f"{msg} PreToolUse hook from [bold]{path}[/bold]")
    console.print("[green]speak_mode[/green] set to [bold]end[/bold]")


@main.command(help="Append the Speaker-line instruction to ~/.claude/CLAUDE.md "
                   "so Claude includes a TTS-friendly summary in every reply.")
def install_speaker() -> None:
    from claude_speak.install import install_speaker as _install

    path, action = _install()
    color = {"installed": "green", "updated": "green", "kept": "yellow"}.get(action, "green")
    console.print(f"[{color}]{action}[/{color}] Speaker-line instructions in [bold]{path}[/bold]")


@main.command(help="Remove the Speaker-line instruction from ~/.claude/CLAUDE.md.")
def uninstall_speaker() -> None:
    from claude_speak.install import uninstall_speaker as _uninstall

    path, removed = _uninstall()
    msg = "[green]Removed[/green]" if removed else "[yellow]Nothing to remove[/yellow]"
    console.print(f"{msg} from [bold]{path}[/bold]")


# ----------------------------------------------------------------------------
@main.command(help="Speak text using the configured TTS backend.")
@click.argument("text", nargs=-1, required=True)
def speak(text: tuple[str, ...]) -> None:
    from claude_speak import filters, tts

    body = " ".join(text)
    cleaned = filters.clean_for_speech(body)
    tts.speak(cleaned, blocking=True)


# ----------------------------------------------------------------------------
@main.command(help="List available Edge TTS voices.")
@click.option("--lang", "-l", default="en", show_default=True)
def voices(lang: str) -> None:
    from claude_speak.tts import list_edge_voices

    try:
        items = list_edge_voices(lang or None)
    except Exception as exc:
        console.print(f"[red]Failed to list voices:[/red] {exc}")
        sys.exit(1)
    if not items:
        console.print(f"[yellow]No voices match '{lang}'.[/yellow]")
        return
    console.print(f"[bold]{len(items)} voices[/bold] (set with claude_speak_VOICE):\n")
    for v in items:
        short = v.get("ShortName", "?")
        gender = v.get("Gender", "?")
        locale = v.get("Locale", "?")
        personalities = ", ".join(v.get("VoiceTag", {}).get("VoicePersonalities", []))
        console.print(
            f"  [cyan]{short:<32}[/cyan] {locale:<8} {gender:<7}"
            + (f" — {personalities}" if personalities else "")
        )


# ----------------------------------------------------------------------------
@main.command(help="Install /voice-* slash commands into ~/.claude/commands/.")
def commands_install() -> None:
    from claude_speak.commands import install_slash_commands

    paths = install_slash_commands()
    console.print(
        f"[green]Installed[/green] {len(paths)} slash commands in "
        f"[bold]{paths[0].parent}[/bold]:"
    )
    for p in paths:
        console.print(f"  /{p.stem}")


# ----------------------------------------------------------------------------
@main.group(help="Read or update settings in ~/.claude-speak/config.json. "
                 "Daemon picks up changes immediately — no restart needed.")
def config() -> None:
    pass


@config.command("show", help="Print every setting with its current effective value and source.")
def config_show() -> None:
    from claude_speak import config as cfg

    eff = cfg.effective()
    console.print(f"[dim]{cfg.CONFIG_PATH}[/dim]\n")
    for key, info in eff.items():
        src = info["source"]
        color = {"config": "green", "default": "dim"}.get(src, "yellow")
        val = info["value"]
        console.print(f"  [bold]{key:<14}[/bold] = [{color}]{val!r}[/{color}]  [dim]({src})[/dim]")


@config.command("get", help="Print the current effective value for one key.")
@click.argument("key")
def config_get(key: str) -> None:
    from claude_speak import config as cfg

    val = cfg.get(key)
    console.print(f"{key} = {val!r}")


@config.command("set", help="Set a value. Pass no value to store an explicit "
                              "empty string (overrides any env var).")
@click.argument("key")
@click.argument("value", nargs=-1)
def config_set(key: str, value: tuple[str, ...]) -> None:
    from claude_speak import config as cfg

    joined = " ".join(value) if value else ""
    cfg.set_value(key, joined)
    console.print(f"[green]set[/green] {key} = {cfg.get(key)!r}")


@config.command("reset", help="Remove a key (or all keys when called with no argument).")
@click.argument("key", required=False)
def config_reset(key: Optional[str] = None) -> None:
    from claude_speak import config as cfg

    cfg.reset(key)
    console.print("[green]reset[/green] " + (key or "(all keys)"))


@main.group(help="Hook entry points called by Claude Code (internal).")
def hook() -> None:
    pass


@hook.command("stop", help="Stop-hook handler. Reads Claude Code payload from stdin.")
def hook_stop() -> None:
    from claude_speak.hooks import stop_hook
    sys.exit(stop_hook())


@hook.command("pre-tool", help="PreToolUse hook handler (interview mode). Reads Claude Code payload from stdin.")
def hook_pre_tool() -> None:
    from claude_speak.hooks import pre_tool_hook
    sys.exit(pre_tool_hook())


@hook.command("post-tool", help="PostToolUse hook handler. Reads Claude Code payload from stdin.")
def hook_post_tool() -> None:
    from claude_speak.hooks import post_tool_hook
    sys.exit(post_tool_hook())


# ----------------------------------------------------------------------------
@main.command(help="Diagnose TTS backend, hooks, and platform support.")
def doctor() -> None:
    import platform
    from claude_speak import pidfile
    from claude_speak.install import HOOK_COMMAND, _settings_path

    console.rule("[bold]claude-speak doctor[/bold]")
    console.print(f"Python:   [bold]{sys.version.split()[0]}[/bold]")
    console.print(f"Platform: [bold]{platform.platform()}[/bold]")
    console.print(f"Backend:  [bold]{os.environ.get('claude_speak_BACKEND', 'edge')}[/bold]")
    explicit_voice = os.environ.get("claude_speak_VOICE")
    if explicit_voice:
        console.print(f"Voice:    [bold]{explicit_voice}[/bold] (forced — language detection disabled)")
    else:
        en = os.environ.get("claude_speak_VOICE_EN", "en-US-AriaNeural")
        es = os.environ.get("claude_speak_VOICE_ES", "es-MX-DaliaNeural")
        console.print(f"Voice EN: [bold]{en}[/bold]")
        console.print(f"Voice ES: [bold]{es}[/bold]")

    settings = _settings_path()
    if settings.exists():
        text = settings.read_text(encoding="utf-8")
        installed = HOOK_COMMAND in text
        msg = "[green]registered[/green]" if installed else "[yellow]not registered[/yellow]"
        console.print(f"\nStop hook in {settings}: {msg}")
    else:
        console.print(f"\n[yellow]{settings} does not exist yet[/yellow]")

    play_pids = [p for p in pidfile.read_all("playing") if pidfile.is_alive(p)]
    console.print(
        f"\nPlaying : "
        + (f"[green]{len(play_pids)} active[/green]" if play_pids else "[dim]idle[/dim]")
    )


if __name__ == "__main__":
    main()
