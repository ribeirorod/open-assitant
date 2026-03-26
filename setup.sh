#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# open-assistant setup.sh
# Guides a new user through first-time deployment, step by step.
# Safe to re-run — skips steps that are already complete.
# ─────────────────────────────────────────────────────────────────────────────

# ── Colors ───────────────────────────────────────────────────────────────────
BOLD='\033[1m'
CYAN='\033[1;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
DIM='\033[2m'
RESET='\033[0m'

header()  { echo; echo -e "${CYAN}${BOLD}── $1 ──${RESET}"; echo; }
success() { echo -e "${GREEN}✔${RESET}  $1"; }
info()    { echo -e "${YELLOW}→${RESET}  $1"; }
prompt()  { echo -e "${BLUE}?${RESET}  $1"; }
dim()     { echo -e "${DIM}   $1${RESET}"; }
error()   { echo -e "${RED}✘${RESET}  $1" >&2; }
pause()   { echo; echo -e "${DIM}Press Enter when ready...${RESET}"; read -r _; }

# ── Collected values (written to .env at the end) ────────────────────────────
CHANNELS=""
TG_TOKEN=""
TG_USERS=""
CLAUDE_AUTH_TYPE=""
CLAUDE_SETUP_TOKEN_VAL=""
ANTHROPIC_API_KEY_VAL=""
GROQ_KEY=""
OPENAI_KEY=""
DEEPGRAM_KEY=""
PERPLEXITY_KEY=""

# ─────────────────────────────────────────────────────────────────────────────
step_welcome() {
  echo
  echo -e "${CYAN}${BOLD}"
  echo "  ╔═══════════════════════════════════════╗"
  echo "  ║       open-assistant  setup           ║"
  echo "  ║   Your personal AI on Telegram/WA     ║"
  echo "  ╚═══════════════════════════════════════╝"
  echo -e "${RESET}"
  echo "  This script will walk you through first-time setup."
  dim "Estimated time: ~10 minutes"
  echo
}

# ─────────────────────────────────────────────────────────────────────────────
step_prerequisites() {
  header "Prerequisites"

  # Docker
  if ! command -v docker &>/dev/null; then
    error "Docker is not installed."
    info "Install Docker Desktop: https://docs.docker.com/get-docker/"
    exit 1
  fi
  if ! docker compose version &>/dev/null; then
    error "Docker Compose plugin not found."
    info "Install Docker Desktop (includes Compose): https://docs.docker.com/get-docker/"
    exit 1
  fi
  success "Docker found"

  # Node / npm
  if ! command -v npm &>/dev/null; then
    error "npm is not installed."
    info "Install Node.js (includes npm): https://nodejs.org/en/download"
    echo
    prompt "Install Node.js, then press Enter to continue..."
    read -r _
    if ! command -v npm &>/dev/null; then
      error "npm still not found. Please install Node.js and re-run setup.sh."
      exit 1
    fi
  fi
  success "npm found ($(npm --version))"

  # gws CLI
  if ! command -v gws &>/dev/null; then
    info "Installing Google Workspace CLI..."
    npm install -g @googleworkspace/cli
  fi
  success "gws CLI found"
}

# ─────────────────────────────────────────────────────────────────────────────
step_channel_selection() {
  header "Channel Selection"

  echo "  Which messaging channels do you want to use?"
  echo
  echo "  [1] Telegram only"
  echo "  [2] WhatsApp only"
  echo "  [3] Both Telegram and WhatsApp"
  echo
  while true; do
    prompt "Enter 1, 2, or 3:"
    read -r choice
    case "$choice" in
      1) CHANNELS="telegram"; break ;;
      2) CHANNELS="whatsapp"; break ;;
      3) CHANNELS="both";     break ;;
      *) error "Please enter 1, 2, or 3." ;;
    esac
  done
  success "Channels: $CHANNELS"
}

# ─────────────────────────────────────────────────────────────────────────────
step_telegram_setup() {
  [[ "$CHANNELS" == "whatsapp" ]] && return

  header "Telegram Bot Setup"

  info "You need a Telegram bot token from @BotFather."
  echo
  echo "  Steps:"
  echo "  1. Open Telegram and search for @BotFather"
  dim "     or open: https://t.me/BotFather"
  echo "  2. Send the message:  /newbot"
  echo "  3. Follow the prompts — choose a name and username for your bot"
  echo "  4. BotFather will reply with a token like:"
  dim "     123456789:ABCDefGhIJKlmNoPQRsTUVwxyZ-abc123"
  echo
  pause

  while true; do
    prompt "Paste your bot token:"
    read -r TG_TOKEN
    if [[ "$TG_TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]{35,}$ ]]; then
      break
    else
      error "That doesn't look like a valid bot token. Please try again."
    fi
  done

  echo
  prompt "Restrict access to specific Telegram usernames? (JSON array e.g. [\"alice\",\"bob\"])"
  prompt "Press Enter to allow all users:"
  read -r TG_USERS

  success "Telegram configured"
}

# ─────────────────────────────────────────────────────────────────────────────
step_gws_setup() {
  header "Google Workspace Setup"

  # ── gws-creds.json ──────────────────────────────────────────────────────
  if [[ -f "${PWD}/gws-creds.json" ]]; then
    success "gws-creds.json already present — skipping"
  else
    info "You need an OAuth 2.0 client credentials file from Google Cloud."
    echo
    echo "  Steps:"
    echo "  1. Go to: https://console.cloud.google.com"
    echo "  2. Create a project (or select an existing one)"
    echo "  3. Go to: APIs & Services → Library"
    echo "     Enable these APIs:"
    dim "     Gmail API, Google Calendar API, Google Drive API,"
    dim "     Google Tasks API, Google Docs API, Google Sheets API"
    echo "  4. Go to: APIs & Services → Credentials"
    echo "  5. Click: Create Credentials → OAuth 2.0 Client ID"
    echo "  6. Application type: Desktop app — give it any name"
    echo "  7. Click Download JSON"
    echo "  8. Rename the downloaded file to:  gws-creds.json"
    echo "     and move it into this directory: ${PWD}"
    echo

    while true; do
      pause
      if [[ -f "${PWD}/gws-creds.json" ]]; then
        break
      else
        error "gws-creds.json not found in ${PWD}. Please move the file and press Enter."
      fi
    done
    success "gws-creds.json found"
  fi

  # ── gws auth login ────────────────────────────────────────────────────────
  if [[ -d "${HOME}/.config/gws" ]] && ls "${HOME}/.config/gws"/*.json &>/dev/null 2>&1; then
    success "Google Workspace already authenticated — skipping"
  else
    info "Authenticating with Google Workspace — a browser window will open."
    dim "Sign in with the Google account you want the assistant to access."
    echo
    if ! gws auth login; then
      error "gws auth login failed."
      info "Try running manually: gws auth login"
      info "Then re-run setup.sh"
      exit 1
    fi
    success "Google Workspace authenticated"
  fi
}

# ─────────────────────────────────────────────────────────────────────────────
step_claude_auth() {
  header "Claude Authentication"

  echo "  How do you want to authenticate Claude?"
  echo
  echo "  [1] Setup-token  (recommended — uses your Claude subscription)"
  echo "  [2] API key      (Anthropic API billing)"
  echo
  while true; do
    prompt "Enter 1 or 2:"
    read -r choice
    case "$choice" in
      1) CLAUDE_AUTH_TYPE="setup-token"; break ;;
      2) CLAUDE_AUTH_TYPE="api-key";     break ;;
      *) error "Please enter 1 or 2." ;;
    esac
  done

  if [[ "$CLAUDE_AUTH_TYPE" == "setup-token" ]]; then
    echo
    info "You need to generate a setup-token from Claude Code."
    echo
    echo "  Steps:"
    echo "  1. On any machine where Claude Code is installed and you are logged in, run:"
    dim "     claude setup-token"
    echo "  2. Copy the token it prints"
    echo
    pause
    while true; do
      prompt "Paste your setup-token:"
      read -r CLAUDE_SETUP_TOKEN_VAL
      if [[ -n "$CLAUDE_SETUP_TOKEN_VAL" ]]; then
        break
      else
        error "Token cannot be empty. Please paste the token."
      fi
    done
  else
    echo
    while true; do
      prompt "Paste your Anthropic API key (starts with sk-ant-...):"
      read -r ANTHROPIC_API_KEY_VAL
      if [[ "$ANTHROPIC_API_KEY_VAL" =~ ^sk-ant- ]]; then
        break
      else
        error "That doesn't look like an Anthropic API key. It should start with sk-ant-"
      fi
    done
  fi

  success "Claude auth configured"
}

# ─────────────────────────────────────────────────────────────────────────────
step_optional_keys() {
  header "Optional Features"

  info "Press Enter to skip any key you don't have."
  echo

  prompt "Groq API key (voice transcription — recommended if you send voice messages):"
  read -r GROQ_KEY

  prompt "OpenAI API key (voice transcription fallback):"
  read -r OPENAI_KEY

  prompt "Deepgram API key (voice transcription fallback):"
  read -r DEEPGRAM_KEY

  prompt "Perplexity API key (enables web search in the assistant):"
  read -r PERPLEXITY_KEY

  success "Optional keys saved"
}

# ─────────────────────────────────────────────────────────────────────────────
# Append any new non-empty values from this run to an existing .env,
# without touching lines already present.
_update_env() {
  local key val
  declare -A new_vals=(
    [CLAUDE_SETUP_TOKEN]="${CLAUDE_SETUP_TOKEN_VAL}"
    [ANTHROPIC_API_KEY]="${ANTHROPIC_API_KEY_VAL}"
    [OA_TELEGRAM_BOT_TOKEN]="${TG_TOKEN}"
    [OA_TELEGRAM_ALLOWED_USERS]="${TG_USERS}"
    [GROQ_API_KEY]="${GROQ_KEY}"
    [OPENAI_API_KEY]="${OPENAI_KEY}"
    [DEEPGRAM_API_KEY]="${DEEPGRAM_KEY}"
    [PERPLEXITY_API_KEY]="${PERPLEXITY_KEY}"
  )
  for key in "${!new_vals[@]}"; do
    val="${new_vals[$key]}"
    [[ -z "$val" ]] && continue
    if grep -q "^${key}=" .env; then
      :
    else
      echo "${key}=${val}" >> .env
    fi
  done
}

# ─────────────────────────────────────────────────────────────────────────────
step_write_env() {
  header "Writing .env"

  if [[ -f ".env" ]]; then
    echo
    echo "  An existing .env file was found."
    echo "  [O] Overwrite — replace entirely with values from this run"
    echo "  [U] Update    — keep existing file, append any new non-empty values"
    echo "  [S] Skip      — keep existing file unchanged"
    echo
    while true; do
      prompt "Enter O, U, or S:"
      read -r choice
      case "${choice^^}" in
        O) break ;;
        U) _update_env; success ".env updated"; return ;;
        S) success ".env unchanged (skipped)"; return ;;
        *) error "Please enter O, U, or S." ;;
      esac
    done
  fi

  {
    echo "# Generated by setup.sh on $(date)"
    echo

    if [[ "$CLAUDE_AUTH_TYPE" == "setup-token" ]]; then
      echo "CLAUDE_SETUP_TOKEN=${CLAUDE_SETUP_TOKEN_VAL}"
      echo "# ANTHROPIC_API_KEY="
    else
      echo "# CLAUDE_SETUP_TOKEN="
      echo "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY_VAL}"
    fi
    echo

    echo "OA_TELEGRAM_BOT_TOKEN=${TG_TOKEN}"
    echo "OA_TELEGRAM_ALLOWED_USERS=${TG_USERS}"
    echo

    [[ -n "$GROQ_KEY" ]]       && echo "GROQ_API_KEY=${GROQ_KEY}"
    [[ -n "$OPENAI_KEY" ]]     && echo "OPENAI_API_KEY=${OPENAI_KEY}"
    [[ -n "$DEEPGRAM_KEY" ]]   && echo "DEEPGRAM_API_KEY=${DEEPGRAM_KEY}"
    [[ -n "$PERPLEXITY_KEY" ]] && echo "PERPLEXITY_API_KEY=${PERPLEXITY_KEY}"
  } > .env

  success ".env written"
}

# ─────────────────────────────────────────────────────────────────────────────
step_launch() {
  header "Launching open-assistant"

  # Ensure the data directory exists with correct ownership before Docker creates it as root
  mkdir -p "${HOME}/.open-assistant"

  info "Building and starting containers (this may take a few minutes on first run)..."
  echo

  if ! docker compose up -d --build; then
    error "docker compose up failed."
    info "Check the logs with:  docker compose logs"
    exit 1
  fi

  # Wait for the assistant health endpoint
  info "Waiting for assistant to be ready..."
  local port="${OA_WEBHOOK_PORT:-8080}"
  local attempts=0
  while ! curl -sf "http://localhost:${port}/health" &>/dev/null; do
    sleep 2
    attempts=$((attempts + 1))
    if [[ $attempts -ge 30 ]]; then
      error "Assistant didn't become healthy after 60s."
      info "Check logs:  docker compose logs assistant"
      exit 1
    fi
  done

  success "open-assistant is running"
}

# ─────────────────────────────────────────────────────────────────────────────
step_claude_token_exchange() {
  [[ "$CLAUDE_AUTH_TYPE" != "setup-token" ]] && return

  header "Activating Claude Auth"

  info "Exchanging setup-token inside the container..."
  if ! docker exec assistant claude setup-token "${CLAUDE_SETUP_TOKEN_VAL}"; then
    error "Token exchange failed."
    info "You can retry manually:"
    dim "  docker exec -it assistant claude setup-token <your-token>"
    info "Or authenticate interactively:"
    dim "  docker exec -it assistant claude login"
  else
    success "Claude authenticated"
  fi
}

# ─────────────────────────────────────────────────────────────────────────────
step_whatsapp_qr() {
  [[ "$CHANNELS" == "telegram" ]] && return

  header "WhatsApp Linking"

  info "Ready to link your WhatsApp account."
  echo
  echo "  Steps:"
  echo "  1. Open WhatsApp on your phone"
  echo "  2. Go to: Settings → Linked Devices → Link a Device"
  echo "  3. Point your camera at the QR code that appears below"
  echo
  info "Streaming Baileys logs (Ctrl-C to abort)..."
  dim "The QR code will appear below. Scan it, then wait for the success message."
  echo

  # Stream baileys logs directly — qrcode-terminal renders the QR in-terminal.
  # We watch for "connection open" to know linking is done.
  # No timeout: the user can Ctrl-C if something goes wrong.
  while IFS= read -r line; do
    echo "  $line"
    if echo "$line" | grep -qi "connection open\|open connection\|linked\|ready"; then
      echo
      success "WhatsApp linked!"
      return
    fi
  done < <(docker compose logs -f baileys 2>&1)

  # Only reached if the log stream ends without a success line
  echo
  error "Log stream ended before WhatsApp was linked."
  info "Check container status:  docker compose ps baileys"
  info "Retry log stream:        docker compose logs -f baileys"
}

# ─────────────────────────────────────────────────────────────────────────────
step_done() {
  echo
  echo -e "${GREEN}${BOLD}"
  echo "  ╔═══════════════════════════════════════╗"
  echo "  ║         Setup complete!               ║"
  echo "  ╚═══════════════════════════════════════╝"
  echo -e "${RESET}"

  echo "  What's configured:"
  [[ "$CHANNELS" != "whatsapp" ]] && dim "  ✔ Telegram bot"
  [[ "$CHANNELS" != "telegram" ]] && dim "  ✔ WhatsApp (Baileys)"
  dim "  ✔ Google Workspace"
  dim "  ✔ Claude AI"
  echo

  info "To add scheduled tasks, create:"
  dim "  ~/.open-assistant/schedules.yaml"
  dim "  See README.md for the format."
  echo
  info "To view logs:"
  dim "  docker compose logs -f assistant"
  echo
  info "To stop:"
  dim "  docker compose down"
  echo
}

# ─────────────────────────────────────────────────────────────────────────────
main() {
  step_welcome
  step_prerequisites
  step_channel_selection
  step_telegram_setup
  step_gws_setup
  step_claude_auth
  step_optional_keys
  step_write_env
  step_launch
  step_claude_token_exchange
  step_whatsapp_qr
  step_done
}

main "$@"
