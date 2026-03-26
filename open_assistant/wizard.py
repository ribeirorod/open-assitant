"""
Interactive setup wizard for open-assistant.

Replaces setup.sh — no bash or gum dependency.
Uses rich for display and questionary for prompts.
"""

from __future__ import annotations

import glob
import re
import subprocess
import sys
from dataclasses import dataclass, fields
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

console = Console()

# Module-level: detected docker compose command (set during prerequisites step)
_compose_cmd: list[str] = ["docker", "compose"]


# ─────────────────────────────────────────────────────────────────────────────
# State
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WizardState:
    channels: str = ""
    tg_token: str = ""
    tg_users: str = ""
    claude_auth_type: str = ""          # "setup-token" or "api-key"
    claude_setup_token: str = ""
    anthropic_api_key: str = ""
    groq_key: str = ""
    openai_key: str = ""
    deepgram_key: str = ""
    perplexity_key: str = ""


_STATE_KEY_MAP = {
    "CHANNELS": "channels",
    "TG_TOKEN": "tg_token",
    "TG_USERS": "tg_users",
    "CLAUDE_AUTH_TYPE": "claude_auth_type",
    "CLAUDE_SETUP_TOKEN": "claude_setup_token",
    "ANTHROPIC_API_KEY": "anthropic_api_key",
    "GROQ_KEY": "groq_key",
    "OPENAI_KEY": "openai_key",
    "DEEPGRAM_KEY": "deepgram_key",
    "PERPLEXITY_KEY": "perplexity_key",
}
_STATE_KEY_MAP_INV = {v: k for k, v in _STATE_KEY_MAP.items()}


def _mask(val: str) -> str:
    """Show first 4 chars + **** for secrets."""
    return f"{val[:4]}****" if val else "(not set)"


def _save_state(state: WizardState, path: Path) -> None:
    lines = []
    for field in fields(state):
        key = _STATE_KEY_MAP_INV.get(field.name, field.name.upper())
        val = getattr(state, field.name)
        lines.append(f"{key}={val}\n")
    path.write_text("".join(lines))


def _load_state(path: Path) -> WizardState:
    state = WizardState()
    if not path.exists():
        return state
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        attr = _STATE_KEY_MAP.get(key.strip())
        if attr:
            setattr(state, attr, val.strip())
    return state


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def run(project_dir: Path, prefill: dict[str, str]) -> None:
    """Run the interactive setup wizard."""
    import questionary

    state_path = project_dir / ".setup-state"
    state = _load_state(state_path)

    # Apply prefill values
    for key, val in prefill.items():
        if hasattr(state, key) and val:
            setattr(state, key, val)

    resuming = state_path.exists()

    # ── Step 1: Welcome ───────────────────────────────────────────────────────
    _step_welcome(resuming)

    # ── Step 2: Prerequisites ─────────────────────────────────────────────────
    _step_prerequisites(questionary)

    # ── Step 3: Channel selection ─────────────────────────────────────────────
    state.channels = _step_channels(questionary, state)
    _save_state(state, state_path)

    # ── Step 4: Telegram setup ────────────────────────────────────────────────
    if state.channels != "whatsapp":
        tg_token, tg_users = _step_telegram(questionary, state)
        state.tg_token = tg_token
        state.tg_users = tg_users
        _save_state(state, state_path)

    # ── Step 5: Google Workspace ──────────────────────────────────────────────
    _step_google_workspace(questionary)

    # ── Step 6: Claude authentication ─────────────────────────────────────────
    auth_type, setup_token, api_key = _step_claude_auth(questionary, state)
    state.claude_auth_type = auth_type
    state.claude_setup_token = setup_token
    state.anthropic_api_key = api_key
    _save_state(state, state_path)

    # ── Step 7: Optional keys ─────────────────────────────────────────────────
    groq, openai, deepgram, perplexity = _step_optional_keys(questionary, state)
    state.groq_key = groq
    state.openai_key = openai
    state.deepgram_key = deepgram
    state.perplexity_key = perplexity
    _save_state(state, state_path)

    # ── Step 8: Write .env ────────────────────────────────────────────────────
    _step_write_env(questionary, project_dir, state)

    # ── Step 9: WhatsApp QR ───────────────────────────────────────────────────
    if state.channels != "telegram":
        _step_whatsapp_qr(questionary, project_dir)

    # ── Step 10: Done ─────────────────────────────────────────────────────────
    _step_done(state, state_path)


# ─────────────────────────────────────────────────────────────────────────────
# Steps
# ─────────────────────────────────────────────────────────────────────────────

def _step_welcome(resuming: bool) -> None:
    body = (
        "[bold]open-assistant[/bold]\n"
        "Personal AI assistant on Telegram / WhatsApp powered by Claude.\n\n"
        "[dim]Estimated time: ~10 minutes[/dim]"
    )
    if resuming:
        body += "\n\n[dim]Resuming previous session — saved values are pre-filled.[/dim]"
    console.print(Panel(body, border_style="cyan", padding=(1, 2)))


def _step_prerequisites(questionary) -> None:
    global _compose_cmd

    console.rule("[bold cyan]── Prerequisites ──[/bold cyan]")

    # Check docker installed
    result = subprocess.run(["docker", "--version"], capture_output=True)
    if result.returncode != 0:
        console.print("[red]✘[/red]  Docker not found.", err=True)
        console.print("[yellow]→[/yellow]  Install Docker Desktop: https://docs.docker.com/get-docker/")
        raise SystemExit(1)

    # Check docker daemon running
    result = subprocess.run(["docker", "info"], capture_output=True)
    if result.returncode != 0:
        console.print("[red]✘[/red]  Docker daemon is not running.", err=True)
        console.print("[yellow]→[/yellow]  Start Docker Desktop and try again.")
        raise SystemExit(1)

    console.print("[green]✔[/green]  Docker is running.")

    # Detect docker compose
    plugin_ok = subprocess.run(
        ["docker", "compose", "version"], capture_output=True
    ).returncode == 0
    standalone_ok = subprocess.run(
        ["docker-compose", "version"], capture_output=True
    ).returncode == 0

    if plugin_ok:
        _compose_cmd = ["docker", "compose"]
        console.print("[green]✔[/green]  docker compose plugin detected.")
    elif standalone_ok:
        _compose_cmd = ["docker-compose"]
        console.print("[green]✔[/green]  docker-compose standalone detected.")
    else:
        console.print("[red]✘[/red]  Docker Compose not found.", err=True)
        console.print(
            "[yellow]→[/yellow]  Install: https://docs.docker.com/compose/install/"
        )
        raise SystemExit(1)

    # Check npm
    npm_ok = subprocess.run(["npm", "--version"], capture_output=True).returncode == 0
    if not npm_ok:
        console.print("[red]✘[/red]  npm not found.", err=True)
        console.print("[yellow]→[/yellow]  Install Node.js: https://nodejs.org/")
        answer = questionary.confirm("Press Enter once Node.js is installed").ask()
        if answer:
            npm_ok = subprocess.run(["npm", "--version"], capture_output=True).returncode == 0
        if not npm_ok:
            console.print("[red]✘[/red]  npm still not found. Exiting.", err=True)
            raise SystemExit(1)

    console.print("[green]✔[/green]  npm is available.")

    # Check gws
    gws_ok = subprocess.run(["gws", "--version"], capture_output=True).returncode == 0
    if not gws_ok:
        with console.status("Installing gws CLI...", spinner="dots"):
            result = subprocess.run(
                ["npm", "install", "-g", "@googleworkspace/cli"],
                capture_output=True,
            )
        if result.returncode != 0:
            console.print("[red]✘[/red]  Failed to install gws CLI.", err=True)
            raise SystemExit(1)
        console.print("[green]✔[/green]  gws CLI installed.")
    else:
        console.print("[green]✔[/green]  gws CLI is available.")


def _step_channels(questionary, state: WizardState) -> str:
    console.rule("[bold cyan]── Channels ──[/bold cyan]")

    choices = ["Telegram only", "WhatsApp only", "Both Telegram and WhatsApp"]
    current_map = {
        "telegram": "Telegram only",
        "whatsapp": "WhatsApp only",
        "both": "Both Telegram and WhatsApp",
    }
    default = current_map.get(state.channels)

    answer = questionary.select(
        "Which messaging channels do you want to use?",
        choices=choices,
        default=default,
    ).ask()

    if answer is None:
        raise SystemExit(0)

    return {"Telegram only": "telegram", "WhatsApp only": "whatsapp", "Both Telegram and WhatsApp": "both"}[answer]


def _step_telegram(questionary, state: WizardState) -> tuple[str, str]:
    console.rule("[bold cyan]── Telegram ──[/bold cyan]")
    console.print("[yellow]→[/yellow]  Follow these steps to create a Telegram bot:")
    console.print("   1. Open Telegram → search [bold]@BotFather[/bold] or visit https://t.me/BotFather")
    console.print("   2. Send [bold]/newbot[/bold] and follow the prompts")
    console.print("   3. BotFather will give you a token like [dim]123456789:ABCDef...[/dim]")

    ready = questionary.confirm("I have my bot token ready").ask()
    if not ready:
        console.print("[yellow]→[/yellow]  Come back when you have your bot token. Exiting.")
        raise SystemExit(0)

    # Token input
    token_pattern = re.compile(r"^\d+:[A-Za-z0-9_-]{35,}$")
    while True:
        if state.tg_token:
            raw = questionary.password(
                f"Bot token [current: {_mask(state.tg_token)}] — leave blank to keep"
            ).ask()
            if raw is None:
                raise SystemExit(0)
            if raw.strip() == "":
                tg_token = state.tg_token
                break
            tg_token = raw.strip()
        else:
            raw = questionary.password("Paste your bot token").ask()
            if raw is None:
                raise SystemExit(0)
            tg_token = raw.strip()

        if token_pattern.match(tg_token):
            break
        console.print("[red]✘[/red]  Invalid token format. Expected: digits:35+ chars (e.g. 123456789:ABCDef...)")

    console.print("[green]✔[/green]  Bot token accepted.")

    # Users input
    users_default = state.tg_users or ""
    tg_users = questionary.text(
        'Allowed usernames (JSON array e.g. ["alice","bob"]) — leave blank to allow all',
        default=users_default,
    ).ask()
    if tg_users is None:
        raise SystemExit(0)

    return tg_token, tg_users.strip()


def _step_google_workspace(questionary) -> None:
    console.rule("[bold cyan]── Google Workspace ──[/bold cyan]")

    creds_dir = Path.home() / ".config" / "gws"
    client_secret = creds_dir / "client_secret.json"

    # Credentials
    if client_secret.exists():
        console.print("[green]✔[/green]  client_secret.json already exists — skipping auth setup.")
    else:
        console.print("[yellow]→[/yellow]  You need to set up Google Workspace credentials.")
        console.print("   Run: [bold]gws auth setup[/bold]")
        result = subprocess.run(["gws", "auth", "setup"])
        if result.returncode != 0:
            console.print("[red]✘[/red]  gws auth setup failed. Exiting.", err=True)
            raise SystemExit(1)

    # Auth tokens
    token_files = glob.glob(str(creds_dir / "credentials*.json"))
    if token_files:
        console.print("[green]✔[/green]  Google Workspace auth tokens found — skipping login.")
    else:
        console.print("[yellow]→[/yellow]  A browser window will open for Google Workspace login.")
        result = subprocess.run(["gws", "auth", "login"])
        if result.returncode != 0:
            console.print("[red]✘[/red]  gws auth login failed. Exiting.", err=True)
            raise SystemExit(1)
        console.print("[green]✔[/green]  Google Workspace authenticated.")


def _step_claude_auth(questionary, state: WizardState) -> tuple[str, str, str]:
    console.rule("[bold cyan]── Claude Authentication ──[/bold cyan]")

    choices = [
        "Setup-token (recommended — uses your Claude subscription)",
        "API key (Anthropic billing)",
    ]
    current_map = {
        "setup-token": choices[0],
        "api-key": choices[1],
    }
    default = current_map.get(state.claude_auth_type)

    answer = questionary.select(
        "How do you want to authenticate Claude?",
        choices=choices,
        default=default,
    ).ask()

    if answer is None:
        raise SystemExit(0)

    if answer == choices[0]:
        # Setup-token path
        auth_type = "setup-token"
        console.print("[yellow]→[/yellow]  On any machine with Claude Code installed and logged in, run:")
        console.print("   [bold]claude setup-token[/bold]")

        ready = questionary.confirm("I have my setup-token").ask()
        if not ready:
            console.print("[yellow]→[/yellow]  Come back when you have your setup-token. Exiting.")
            raise SystemExit(0)

        while True:
            if state.claude_setup_token:
                raw = questionary.password(
                    f"Setup token [current: {_mask(state.claude_setup_token)}] — leave blank to keep"
                ).ask()
                if raw is None:
                    raise SystemExit(0)
                if raw.strip() == "":
                    setup_token = state.claude_setup_token
                else:
                    setup_token = raw.strip()
            else:
                raw = questionary.password("Paste your setup-token").ask()
                if raw is None:
                    raise SystemExit(0)
                setup_token = raw.strip()

            if setup_token:
                break
            console.print("[red]✘[/red]  Setup token cannot be empty.")

        console.print("[green]✔[/green]  Setup token accepted.")
        return auth_type, setup_token, ""

    else:
        # API key path
        auth_type = "api-key"

        while True:
            if state.anthropic_api_key:
                raw = questionary.password(
                    f"Anthropic API key [current: {_mask(state.anthropic_api_key)}] — leave blank to keep"
                ).ask()
                if raw is None:
                    raise SystemExit(0)
                if raw.strip() == "":
                    api_key = state.anthropic_api_key
                else:
                    api_key = raw.strip()
            else:
                raw = questionary.password("Paste your Anthropic API key (sk-ant-...)").ask()
                if raw is None:
                    raise SystemExit(0)
                api_key = raw.strip()

            if api_key.startswith("sk-ant-"):
                break
            console.print("[red]✘[/red]  API key must start with 'sk-ant-'.")

        console.print("[green]✔[/green]  Anthropic API key accepted.")
        return auth_type, "", api_key


def _step_optional_keys(questionary, state: WizardState) -> tuple[str, str, str, str]:
    console.rule("[bold cyan]── Optional API Keys ──[/bold cyan]")
    console.print("[dim]   Leave blank to skip any key.[/dim]")

    def _ask_key(label: str, current: str) -> str:
        if current:
            raw = questionary.password(
                f"{label} [current: {_mask(current)}] — leave blank to keep"
            ).ask()
            if raw is None:
                return current
            return raw.strip() if raw.strip() else current
        else:
            raw = questionary.password(label).ask()
            if raw is None:
                return ""
            return raw.strip()

    groq = _ask_key("Groq API key (voice transcription — recommended):", state.groq_key)
    openai = _ask_key("OpenAI API key (voice transcription fallback):", state.openai_key)
    deepgram = _ask_key("Deepgram API key (voice transcription fallback):", state.deepgram_key)
    perplexity = _ask_key("Perplexity API key (enables web search):", state.perplexity_key)

    return groq, openai, deepgram, perplexity


def _step_write_env(questionary, project_dir: Path, state: WizardState) -> None:
    console.rule("[bold cyan]── Writing .env ──[/bold cyan]")

    env_path = project_dir / ".env"
    action = "overwrite"

    if env_path.exists():
        answer = questionary.select(
            "An existing .env was found.",
            choices=["Update — add new values", "Overwrite — replace entirely", "Skip"],
        ).ask()
        if answer is None or answer == "Skip":
            console.print("[dim]   Skipping .env write.[/dim]")
            return
        action = "update" if answer.startswith("Update") else "overwrite"

    if action == "update":
        # Read existing values
        existing: dict[str, str] = {}
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                existing[k.strip()] = v.strip()
    else:
        existing = {}

    # Build new content
    lines: list[str] = ["# Written by open-assistant setup\n\n"]

    def _put(env_key: str, val: str) -> None:
        if val:
            lines.append(f"{env_key}={val}\n")
        elif action == "update" and env_key in existing:
            lines.append(f"{env_key}={existing[env_key]}\n")

    if state.claude_auth_type == "setup-token":
        _put("CLAUDE_SETUP_TOKEN", state.claude_setup_token)
    else:
        _put("ANTHROPIC_API_KEY", state.anthropic_api_key)

    lines.append("\n")
    _put("OA_TELEGRAM_BOT_TOKEN", state.tg_token)
    _put("OA_TELEGRAM_ALLOWED_USERS", state.tg_users)

    lines.append("\n")
    _put("GROQ_API_KEY", state.groq_key)
    _put("OPENAI_API_KEY", state.openai_key)
    _put("DEEPGRAM_API_KEY", state.deepgram_key)
    _put("PERPLEXITY_API_KEY", state.perplexity_key)

    env_path.write_text("".join(lines))
    env_path.chmod(0o600)
    console.print(f"[green]✔[/green]  .env written to {env_path}")


def _step_whatsapp_qr(questionary, project_dir: Path) -> None:
    console.rule("[bold cyan]── WhatsApp Linking ──[/bold cyan]")
    console.print("[yellow]→[/yellow]  To link WhatsApp:")
    console.print("   1. Open WhatsApp on your phone")
    console.print("   2. Go to Settings → Linked Devices")
    console.print("   3. Tap Link a Device")

    show_qr = questionary.confirm("Show QR code", default=True).ask()
    if not show_qr:
        console.print("[dim]   Skipping QR code display. You can link manually later.[/dim]")
        return

    console.print("[yellow]→[/yellow]  Streaming baileys logs — waiting for QR code and connection...")
    cmd = _compose_cmd + ["logs", "-f", "baileys"]

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        linked = False
        for line in proc.stdout:
            console.print(line, end="")
            if re.search(r"connection open|linked|ready", line, re.IGNORECASE):
                linked = True
                proc.terminate()
                break

        if linked:
            console.print("[green]✔[/green]  WhatsApp linked!")
        else:
            console.print(
                "[red]✘[/red]  Stream ended without confirming link.",
                err=True,
            )
            compose_str = " ".join(_compose_cmd)
            console.print(
                f"[yellow]→[/yellow]  Retry manually: [bold]{compose_str} logs -f baileys[/bold]"
            )
    except Exception as exc:
        console.print(f"[red]✘[/red]  Failed to stream logs: {exc}", err=True)


def _step_done(state: WizardState, state_path: Path) -> None:
    configured: list[str] = []

    if state.channels:
        configured.append(f"Channels: {state.channels}")
    if state.tg_token:
        configured.append("Telegram bot")
    if state.claude_setup_token or state.anthropic_api_key:
        configured.append(f"Claude auth ({state.claude_auth_type})")
    if state.groq_key:
        configured.append("Groq (voice transcription)")
    if state.openai_key:
        configured.append("OpenAI (voice transcription fallback)")
    if state.deepgram_key:
        configured.append("Deepgram (voice transcription fallback)")
    if state.perplexity_key:
        configured.append("Perplexity (web search)")

    configured_lines = "\n".join(f"  • {item}" for item in configured)

    body = (
        "[bold green]Setup complete![/bold green]\n\n"
        f"Configured:\n{configured_lines}\n\n"
        "[bold]Next steps:[/bold]\n"
        "  Launch:     docker compose up -d --build\n"
        "  View logs:  docker compose logs -f assistant\n"
        "  Stop:       docker compose down\n"
        "  Schedules:  ~/.open-assistant/schedules.yaml (see README)\n\n"
        f"[dim](setup state saved at {state_path} — delete it to start fresh)[/dim]"
    )
    console.print(Panel(body, border_style="green", padding=(1, 2)))
