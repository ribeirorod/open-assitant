"""
open-assistant CLI — manage your personal AI assistant stack.

AGENT USAGE
-----------
This CLI is designed to be used by humans and AI agents alike.
Every command supports --help.  Non-interactive flags are available on `setup`
so agents can drive the full setup flow without prompts.

QUICK START (human)
-------------------
  open-assistant init      # create docker-compose.yaml + .env.example in current dir
  open-assistant setup     # interactive wizard — configure credentials, write .env
  open-assistant start     # build images and start containers
  open-assistant status    # show running containers
  open-assistant logs      # stream logs
  open-assistant stop      # stop containers

QUICK START (agent / non-interactive)
--------------------------------------
  open-assistant init
  open-assistant setup \\
      --channels telegram \\
      --telegram-token "123456:ABC..." \\
      --claude-setup-token "tok_..." \\
      --groq-key "gsk_..."
  open-assistant start
"""

from __future__ import annotations

import importlib.resources
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from open_assistant._compose import find_project_dir, run_compose

app = typer.Typer(
    name="open-assistant",
    help=(
        "Personal AI assistant on Telegram / WhatsApp, powered by Claude and Google Workspace.\n\n"
        "Run 'open-assistant COMMAND --help' for detailed help on any command."
    ),
    no_args_is_help=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)

console = Console()

# ── Shared option ─────────────────────────────────────────────────────────────
_DIR_OPTION = typer.Option(
    None,
    "--project-dir", "-d",
    help="Path to the open-assistant project directory (default: current directory).",
    show_default=False,
)


# ─────────────────────────────────────────────────────────────────────────────
@app.command()
def init(
    project_dir: Optional[Path] = typer.Option(
        None,
        "--project-dir", "-d",
        help="Directory to initialise (default: current directory).",
        show_default=False,
    ),
    force: bool = typer.Option(
        False,
        "--force", "-f",
        help="Overwrite existing files.",
    ),
) -> None:
    """
    Initialise a new project directory with docker-compose.yaml and .env.example.

    Run this once after 'pip install open-assistant', then run 'open-assistant setup'.

    \b
    Example:
      mkdir ~/my-assistant && cd ~/my-assistant
      open-assistant init
      open-assistant setup
    """
    dest = project_dir or Path.cwd()
    dest.mkdir(parents=True, exist_ok=True)

    data_pkg = importlib.resources.files("open_assistant._data")
    files = ["docker-compose.yaml", ".env.example", "setup.sh"]

    for filename in files:
        target = dest / filename
        if target.exists() and not force:
            console.print(f"  [dim]skipping {filename} (already exists — use --force to overwrite)[/dim]")
            continue
        src_file = data_pkg / filename
        with importlib.resources.as_file(src_file) as src_path:
            shutil.copy2(src_path, target)
        if filename == "setup.sh":
            target.chmod(0o755)
        console.print(f"  [green]✔[/green]  {filename}")

    console.print(f"\n[bold]Project initialised at {dest}[/bold]")
    console.print("Next: [cyan]open-assistant setup[/cyan]")


# ─────────────────────────────────────────────────────────────────────────────
@app.command()
def setup(
    project_dir: Optional[Path] = _DIR_OPTION,
    # ── Non-interactive flags (for agents / scripted installs) ────────────────
    channels: Optional[str] = typer.Option(
        None,
        "--channels",
        help="Messaging channels to enable. One of: telegram, whatsapp, both.",
        metavar="CHANNEL",
    ),
    telegram_token: Optional[str] = typer.Option(
        None,
        "--telegram-token",
        help="Telegram bot token from @BotFather (format: 1234567890:ABCDef...).",
        envvar="OA_TELEGRAM_BOT_TOKEN",
    ),
    telegram_users: Optional[str] = typer.Option(
        None,
        "--telegram-users",
        help='Allowed Telegram usernames as a JSON array, e.g. \'["alice","bob"]\'. Leave unset to allow all.',
        envvar="OA_TELEGRAM_ALLOWED_USERS",
    ),
    claude_setup_token: Optional[str] = typer.Option(
        None,
        "--claude-setup-token",
        help=(
            "Claude setup-token for subscription auth. "
            "Generate with 'claude setup-token' on any authenticated machine."
        ),
        envvar="CLAUDE_SETUP_TOKEN",
    ),
    anthropic_api_key: Optional[str] = typer.Option(
        None,
        "--anthropic-api-key",
        help="Anthropic API key (sk-ant-...). Alternative to --claude-setup-token.",
        envvar="ANTHROPIC_API_KEY",
    ),
    groq_key: Optional[str] = typer.Option(
        None,
        "--groq-key",
        help="Groq API key for voice message transcription (recommended).",
        envvar="GROQ_API_KEY",
    ),
    openai_key: Optional[str] = typer.Option(
        None,
        "--openai-key",
        help="OpenAI API key for voice transcription (fallback).",
        envvar="OPENAI_API_KEY",
    ),
    deepgram_key: Optional[str] = typer.Option(
        None,
        "--deepgram-key",
        help="Deepgram API key for voice transcription (fallback).",
        envvar="DEEPGRAM_API_KEY",
    ),
    perplexity_key: Optional[str] = typer.Option(
        None,
        "--perplexity-key",
        help="Perplexity API key to enable web search in assistant responses.",
        envvar="PERPLEXITY_API_KEY",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive", "--yes", "-y",
        help=(
            "Skip interactive prompts. Write .env directly from the flags above. "
            "Exits with error if required values are missing."
        ),
    ),
) -> None:
    """
    Configure credentials and write .env.

    \b
    By default this runs an interactive CLI wizard that guides you through:
      • Creating a Telegram bot (via @BotFather)
      • Authenticating with Google Workspace (browser OAuth)
      • Claude authentication (subscription token or API key)
      • Optional API keys (voice transcription, web search)

    \b
    For scripted / agent use, pass all values as flags and add --non-interactive:

      open-assistant setup \\
          --channels telegram \\
          --telegram-token "1234567890:ABCDef..." \\
          --claude-setup-token "tok_..." \\
          --non-interactive

    \b
    Required for non-interactive mode:
      --channels            telegram | whatsapp | both
      --telegram-token      (if channels includes telegram)
      --claude-setup-token  OR --anthropic-api-key

    \b
    Environment variable equivalents:
      All flags can also be set as env vars (shown in --help for each flag).
      This allows passing secrets via CI/CD without exposing them in shell history.
    """
    d = find_project_dir(project_dir)

    if non_interactive:
        _write_env_non_interactive(
            project_dir=d,
            channels=channels,
            telegram_token=telegram_token,
            telegram_users=telegram_users,
            claude_setup_token=claude_setup_token,
            anthropic_api_key=anthropic_api_key,
            groq_key=groq_key,
            openai_key=openai_key,
            deepgram_key=deepgram_key,
            perplexity_key=perplexity_key,
        )
        return

    # Interactive: delegate to setup.sh
    setup_script = d / "setup.sh"
    if not setup_script.exists():
        console.print(
            "[red]✘[/red]  setup.sh not found. Run [cyan]open-assistant init[/cyan] first.",
            err=True,
        )
        raise typer.Exit(1)

    # Pass any pre-supplied flags as env vars so setup.sh can pre-fill them
    env = os.environ.copy()
    if channels:
        env["CHANNELS"] = channels
    if telegram_token:
        env["TG_TOKEN"] = telegram_token
    if telegram_users:
        env["TG_USERS"] = telegram_users
    if claude_setup_token:
        env["CLAUDE_SETUP_TOKEN_VAL"] = claude_setup_token
    if anthropic_api_key:
        env["ANTHROPIC_API_KEY_VAL"] = anthropic_api_key
    if groq_key:
        env["GROQ_KEY"] = groq_key
    if openai_key:
        env["OPENAI_KEY"] = openai_key
    if deepgram_key:
        env["DEEPGRAM_KEY"] = deepgram_key
    if perplexity_key:
        env["PERPLEXITY_KEY"] = perplexity_key

    result = subprocess.run(["bash", str(setup_script)], cwd=d, env=env)
    raise typer.Exit(result.returncode)


def _write_env_non_interactive(
    project_dir: Path,
    channels: Optional[str],
    telegram_token: Optional[str],
    telegram_users: Optional[str],
    claude_setup_token: Optional[str],
    anthropic_api_key: Optional[str],
    groq_key: Optional[str],
    openai_key: Optional[str],
    deepgram_key: Optional[str],
    perplexity_key: Optional[str],
) -> None:
    """Write .env without interactive prompts. Validates required fields."""
    errors: list[str] = []

    if not channels:
        errors.append("--channels is required (telegram | whatsapp | both)")
    elif channels not in ("telegram", "whatsapp", "both"):
        errors.append("--channels must be one of: telegram, whatsapp, both")

    needs_telegram = channels in ("telegram", "both") if channels else False
    if needs_telegram and not telegram_token:
        errors.append("--telegram-token is required when channels includes telegram")

    if not claude_setup_token and not anthropic_api_key:
        errors.append("--claude-setup-token or --anthropic-api-key is required")

    if errors:
        console.print("\n[red]✘  Missing required values:[/red]")
        for e in errors:
            console.print(f"  [red]•[/red] {e}")
        console.print("\nRun [cyan]open-assistant setup --help[/cyan] for usage.")
        raise typer.Exit(1)

    env_path = project_dir / ".env"
    lines = [f"# Written by open-assistant setup --non-interactive\n\n"]

    if claude_setup_token:
        lines.append(f"CLAUDE_SETUP_TOKEN={claude_setup_token}\n")
    if anthropic_api_key:
        lines.append(f"ANTHROPIC_API_KEY={anthropic_api_key}\n")
    lines.append("\n")
    if telegram_token:
        lines.append(f"OA_TELEGRAM_BOT_TOKEN={telegram_token}\n")
    if telegram_users:
        lines.append(f"OA_TELEGRAM_ALLOWED_USERS={telegram_users}\n")
    lines.append("\n")
    if groq_key:
        lines.append(f"GROQ_API_KEY={groq_key}\n")
    if openai_key:
        lines.append(f"OPENAI_API_KEY={openai_key}\n")
    if deepgram_key:
        lines.append(f"DEEPGRAM_API_KEY={deepgram_key}\n")
    if perplexity_key:
        lines.append(f"PERPLEXITY_API_KEY={perplexity_key}\n")

    env_path.write_text("".join(lines))
    env_path.chmod(0o600)
    console.print(f"[green]✔[/green]  .env written to {env_path}")


# ─────────────────────────────────────────────────────────────────────────────
@app.command()
def start(
    project_dir: Optional[Path] = _DIR_OPTION,
    build: bool = typer.Option(
        True,
        "--build/--no-build",
        help="Rebuild Docker images before starting (default: true).",
    ),
    detach: bool = typer.Option(
        True,
        "--detach/--no-detach", "-d",
        help="Run containers in the background (default: true).",
    ),
) -> None:
    """
    Build images and start the assistant stack.

    \b
    Runs 'docker compose up --build -d' by default.
    On first run this will take a few minutes to build the images.

    \b
    Examples:
      open-assistant start               # build + start in background
      open-assistant start --no-build    # start without rebuilding
      open-assistant start --no-detach   # stream logs to stdout (foreground)
    """
    d = find_project_dir(project_dir)
    args = ["up"]
    if build:
        args.append("--build")
    if detach:
        args.append("-d")
    code = run_compose(args, d)
    raise typer.Exit(code)


# ─────────────────────────────────────────────────────────────────────────────
@app.command()
def stop(
    project_dir: Optional[Path] = _DIR_OPTION,
    volumes: bool = typer.Option(
        False,
        "--volumes", "-v",
        help="Also remove named volumes (WARNING: deletes WhatsApp and Claude auth state).",
    ),
) -> None:
    """
    Stop the assistant stack.

    \b
    Runs 'docker compose down'.  Auth state (Claude, WhatsApp) is preserved
    in Docker volumes unless --volumes is passed.

    \b
    Examples:
      open-assistant stop              # stop containers, keep volumes
      open-assistant stop --volumes    # stop and delete all auth state (full reset)
    """
    d = find_project_dir(project_dir)
    args = ["down"]
    if volumes:
        args.append("-v")
    code = run_compose(args, d)
    raise typer.Exit(code)


# ─────────────────────────────────────────────────────────────────────────────
@app.command()
def logs(
    project_dir: Optional[Path] = _DIR_OPTION,
    service: str = typer.Option(
        "assistant",
        "--service", "-s",
        help="Which service to stream logs from. One of: assistant, baileys.",
    ),
    follow: bool = typer.Option(
        True,
        "--follow/--no-follow", "-f",
        help="Stream logs in real time (default: true).",
    ),
    tail: int = typer.Option(
        50,
        "--tail", "-n",
        help="Number of recent lines to show before streaming.",
    ),
) -> None:
    """
    Stream logs from the assistant or WhatsApp bridge container.

    \b
    Examples:
      open-assistant logs                          # tail assistant logs (default)
      open-assistant logs --service baileys        # tail WhatsApp bridge logs
      open-assistant logs --no-follow --tail 100   # last 100 lines, then exit
    """
    if service not in ("assistant", "baileys"):
        console.print("[red]✘[/red]  --service must be one of: assistant, baileys", err=True)
        raise typer.Exit(1)

    d = find_project_dir(project_dir)
    args = ["logs", f"--tail={tail}"]
    if follow:
        args.append("-f")
    args.append(service)
    code = run_compose(args, d)
    raise typer.Exit(code)


# ─────────────────────────────────────────────────────────────────────────────
@app.command()
def status(
    project_dir: Optional[Path] = _DIR_OPTION,
) -> None:
    """
    Show the running status of all containers.

    \b
    Example:
      open-assistant status
    """
    d = find_project_dir(project_dir)
    code = run_compose(["ps"], d)
    raise typer.Exit(code)


# ─────────────────────────────────────────────────────────────────────────────
@app.command()
def update(
    project_dir: Optional[Path] = _DIR_OPTION,
) -> None:
    """
    Pull the latest images and restart the stack.

    \b
    Equivalent to:
      docker compose pull
      docker compose up -d --build

    \b
    Example:
      open-assistant update
    """
    d = find_project_dir(project_dir)
    console.print("[cyan]→[/cyan]  Pulling latest images...")
    run_compose(["pull"], d)
    console.print("[cyan]→[/cyan]  Restarting stack...")
    code = run_compose(["up", "-d", "--build"], d)
    if code == 0:
        console.print("[green]✔[/green]  Stack updated and running.")
    raise typer.Exit(code)


# ─────────────────────────────────────────────────────────────────────────────
@app.command()
def chat(
    message: Optional[str] = typer.Argument(
        None,
        help="Message to send. If omitted, enters an interactive REPL.",
    ),
) -> None:
    """
    Chat with the assistant directly from the terminal.

    \b
    Requires the assistant container to be running ('open-assistant start').
    Uses a persistent session named 'cli-session'.

    \b
    Examples:
      open-assistant chat                            # interactive REPL
      open-assistant chat "what do I have today?"   # one-shot query
    """
    try:
        import asyncio
        from src.agent.core import ask_agent, reset_agent
    except ImportError:
        console.print(
            "[red]✘[/red]  The 'chat' command requires running from the open-assistant source directory.",
            err=True,
        )
        raise typer.Exit(1)

    chat_id = "cli-session"

    async def _run() -> None:
        if message:
            response = await ask_agent(message, chat_id)
            console.print(f"[bold]Assistant:[/bold] {response}")
            return

        console.print("[bold]open-assistant chat[/bold]  (type 'exit' to quit, '/reset' to clear session)")
        console.rule()
        while True:
            try:
                user_input = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\nBye!")
                break
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                console.print("Bye!")
                break
            if user_input == "/reset":
                await reset_agent(chat_id)
                console.print("[dim]Session reset.[/dim]")
                continue
            response = await ask_agent(user_input, chat_id)
            console.print(f"\n[bold]Assistant:[/bold] {response}")

    import asyncio
    asyncio.run(_run())


# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    app()


if __name__ == "__main__":
    main()
