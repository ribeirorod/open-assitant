#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# open-assistant setup.sh
# Guides a new user through first-time deployment, step by step.
# Safe to re-run — skips steps that are already complete.
# Requires: Docker, Node.js/npm, gum (installed automatically)
# Supported: macOS (Homebrew), Debian/Ubuntu (apt), Fedora/RHEL (dnf/yum), Linux (binary)
# ─────────────────────────────────────────────────────────────────────────────

# ── Minimal colors used before gum is available ──────────────────────────────
BOLD='\033[1m'
CYAN='\033[1;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
DIM='\033[2m'
RESET='\033[0m'

_plain_error() { echo -e "${RED}✘${RESET}  $1" >&2; }
_plain_info()  { echo -e "${DIM}→  $1${RESET}"; }

# ── gum helpers ──────────────────────────────────────────────────────────────
header()  { echo; gum style --bold --foreground 51 "── $1 ──"; echo; }
success() { gum style --foreground 2 "✔  $1"; }
info()    { gum style --foreground 3 "→  $1"; }
err()     { gum style --foreground 1 "✘  $1" >&2; }
dim()     { gum style --faint "   $1"; }
mask()    { local v="$1"; [[ -z "$v" ]] && echo "(not set)" || echo "${v:0:4}****"; }

# ── gum input wrappers ───────────────────────────────────────────────────────
# _ask PROMPT [CURRENT]          — plain text input; pre-fills if CURRENT given
# _ask_secret PROMPT [CURRENT]   — masked input; shows masked hint if CURRENT given
_ask() {
  local label="$1" current="${2:-}"
  if [[ -n "$current" ]]; then
    gum input --prompt "? " --placeholder "$label" --value "$current"
  else
    gum input --prompt "? " --placeholder "$label"
  fi
}

_ask_secret() {
  local label="$1" current="${2:-}"
  if [[ -n "$current" ]]; then
    gum input --password --prompt "? " --placeholder "$label  [current: $(mask "$current")]"
  else
    gum input --password --prompt "? " --placeholder "$label"
  fi
}

# ── State persistence ─────────────────────────────────────────────────────────
STATE_FILE="${PWD}/.setup-state"

_save_state() {
  {
    echo "CHANNELS=${CHANNELS}"
    echo "TG_TOKEN=${TG_TOKEN}"
    echo "TG_USERS=${TG_USERS}"
    echo "CLAUDE_AUTH_TYPE=${CLAUDE_AUTH_TYPE}"
    echo "CLAUDE_SETUP_TOKEN_VAL=${CLAUDE_SETUP_TOKEN_VAL}"
    echo "ANTHROPIC_API_KEY_VAL=${ANTHROPIC_API_KEY_VAL}"
    echo "GROQ_KEY=${GROQ_KEY}"
    echo "OPENAI_KEY=${OPENAI_KEY}"
    echo "DEEPGRAM_KEY=${DEEPGRAM_KEY}"
    echo "PERPLEXITY_KEY=${PERPLEXITY_KEY}"
  } > "${STATE_FILE}"
  chmod 600 "${STATE_FILE}"
}

_load_state() {
  [[ ! -f "${STATE_FILE}" ]] && return
  # shellcheck source=/dev/null
  source "${STATE_FILE}"
}

# ── Docker Compose command (plugin vs standalone) ─────────────────────────────
# Detected during step_prerequisites and used everywhere after that.
COMPOSE=""

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
_ensure_gum() {
  command -v gum &>/dev/null && return

  echo -e "${CYAN}${BOLD}Installing gum (interactive CLI toolkit)...${RESET}"

  if command -v brew &>/dev/null; then
    brew install gum

  elif command -v apt-get &>/dev/null; then
    # Debian / Ubuntu — Charm's official apt repo
    if command -v sudo &>/dev/null; then
      sudo mkdir -p /etc/apt/keyrings
      curl -fsSL https://repo.charm.sh/apt/gpg.key \
        | sudo gpg --dearmor -o /etc/apt/keyrings/charm.gpg
      echo "deb [signed-by=/etc/apt/keyrings/charm.gpg] https://repo.charm.sh/apt/ * *" \
        | sudo tee /etc/apt/sources.list.d/charm.list >/dev/null
      sudo apt-get update -qq && sudo apt-get install -y gum
    else
      _gum_install_binary
    fi

  elif command -v dnf &>/dev/null || command -v yum &>/dev/null; then
    # Fedora / RHEL / CentOS — Charm's official RPM repo
    if command -v sudo &>/dev/null; then
      local repo='[charm]
name=Charm
baseurl=https://repo.charm.sh/yum/
enabled=1
gpgcheck=1
gpgkey=https://repo.charm.sh/yum/gpg.key'
      echo "$repo" | sudo tee /etc/yum.repos.d/charm.repo >/dev/null
      if command -v dnf &>/dev/null; then
        sudo dnf install -y gum
      else
        sudo yum install -y gum
      fi
    else
      _gum_install_binary
    fi

  else
    _gum_install_binary
  fi

  if ! command -v gum &>/dev/null; then
    _plain_error "gum installation failed. Install it manually and re-run:"
    _plain_info  "  macOS/Linux:  brew install gum"
    _plain_info  "  Other:        https://github.com/charmbracelet/gum/releases"
    exit 1
  fi

  echo -e "${GREEN}✔${RESET}  gum installed"
}

# Binary download fallback — installs to /usr/local/bin or ~/.local/bin
_gum_install_binary() {
  local os arch version url tmp install_dir

  os="$(uname -s | tr '[:upper:]' '[:lower:]')"
  arch="$(uname -m)"
  [[ "$arch" == "x86_64" ]]             && arch="amd64"
  [[ "$arch" == "arm64" || "$arch" == "aarch64" ]] && arch="arm64"

  version=$(curl -sfL "https://api.github.com/repos/charmbracelet/gum/releases/latest" \
    | grep '"tag_name"' | head -1 | sed 's/.*"v\([^"]*\)".*/\1/')

  if [[ -z "$version" ]]; then
    _plain_error "Could not fetch gum release info (check internet connection)."
    return 1
  fi

  url="https://github.com/charmbracelet/gum/releases/download/v${version}/gum_${version}_${os}_${arch}.tar.gz"
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' RETURN

  curl -sfL "$url" | tar -xz -C "$tmp" gum 2>/dev/null \
    || { _plain_error "Failed to download gum binary."; return 1; }

  # Prefer /usr/local/bin; fall back to ~/.local/bin (no sudo needed)
  if [[ -w /usr/local/bin ]]; then
    install_dir="/usr/local/bin"
  elif command -v sudo &>/dev/null && sudo -n true 2>/dev/null; then
    sudo mv "$tmp/gum" /usr/local/bin/gum
    return 0
  else
    install_dir="${HOME}/.local/bin"
    mkdir -p "$install_dir"
    # Warn if not in PATH
    if [[ ":$PATH:" != *":${install_dir}:"* ]]; then
      _plain_info "Note: add ${install_dir} to your PATH (e.g. in ~/.bashrc or ~/.profile)"
    fi
  fi

  mv "$tmp/gum" "${install_dir}/gum"
  chmod +x "${install_dir}/gum"
}

# ─────────────────────────────────────────────────────────────────────────────
step_welcome() {
  clear 2>/dev/null || true
  echo
  gum style \
    --border rounded --border-foreground 51 \
    --padding "1 4" --margin "0 2" \
    --bold --foreground 51 \
    "open-assistant  setup" \
    "" \
    "Your personal AI on Telegram / WhatsApp"
  echo
  gum style --faint "  This script walks you through first-time setup (~10 minutes)."
  [[ -f "${STATE_FILE}" ]] && gum style --foreground 3 "  ↑ Resuming a previous session — your saved values will be pre-filled."
  echo
}

# ─────────────────────────────────────────────────────────────────────────────
step_prerequisites() {
  header "Prerequisites"

  # Docker
  if ! command -v docker &>/dev/null; then
    err "Docker is not installed."
    info "Install Docker: https://docs.docker.com/get-docker/"
    exit 1
  fi

  # Prefer 'docker compose' plugin; fall back to standalone 'docker-compose'
  if docker compose version &>/dev/null 2>&1; then
    COMPOSE="docker compose"
  elif command -v docker-compose &>/dev/null; then
    COMPOSE="docker-compose"
  else
    err "Docker Compose not found (neither 'docker compose' plugin nor 'docker-compose')."
    info "Install Docker Desktop or 'docker compose' plugin: https://docs.docker.com/compose/install/"
    exit 1
  fi

  if ! docker info &>/dev/null 2>&1; then
    err "Docker daemon is not running. Please start Docker (or Docker Desktop) and try again."
    exit 1
  fi
  success "Docker OK  ($COMPOSE)"

  # Node / npm
  if ! command -v npm &>/dev/null; then
    err "npm is not installed."
    info "Install Node.js (includes npm): https://nodejs.org/en/download"
    echo
    gum confirm "Press Enter once Node.js is installed to continue..." --affirmative "Continue" --negative "Quit" || exit 0
    if ! command -v npm &>/dev/null; then
      err "npm still not found. Please install Node.js and re-run setup.sh."
      exit 1
    fi
  fi
  success "npm OK ($(npm --version))"

  # gws CLI
  if ! command -v gws &>/dev/null; then
    info "Installing Google Workspace CLI..."
    # On Linux, global npm installs may require sudo depending on npm prefix config.
    # Try without sudo first; fall back to user-local prefix if it fails.
    local npm_prefix
    npm_prefix=$(npm config get prefix 2>/dev/null || echo "")
    if gum spin --spinner dot --title "Installing @googleworkspace/cli..." -- \
        npm install -g @googleworkspace/cli 2>/dev/null; then
      : # success
    elif [[ -n "$npm_prefix" ]] && [[ -w "$npm_prefix" ]]; then
      err "npm global install failed. Your npm prefix ($npm_prefix) is writable but the install still failed."
      info "Try: npm install -g @googleworkspace/cli"
      exit 1
    else
      # Install to user-local prefix to avoid needing sudo
      local local_prefix="${HOME}/.npm-global"
      mkdir -p "$local_prefix"
      npm config set prefix "$local_prefix" 2>/dev/null || true
      export PATH="${local_prefix}/bin:${PATH}"
      gum spin --spinner dot --title "Installing @googleworkspace/cli (user prefix)..." -- \
        npm install -g @googleworkspace/cli || {
          err "npm install failed. Please install manually: npm install -g @googleworkspace/cli"
          exit 1
        }
      if [[ ":$PATH:" != *":${local_prefix}/bin:"* ]]; then
        info "Add ${local_prefix}/bin to your PATH for future sessions."
      fi
    fi
  fi
  if ! command -v gws &>/dev/null; then
    err "gws CLI not found after install. Check your PATH."
    exit 1
  fi
  success "gws CLI OK"
}

# ─────────────────────────────────────────────────────────────────────────────
step_channel_selection() {
  header "Messaging Channels"

  local choices=("Telegram only" "WhatsApp only" "Both Telegram and WhatsApp")
  local default_idx=0

  if [[ -n "$CHANNELS" ]]; then
    case "$CHANNELS" in
      telegram) default_idx=0 ;;
      whatsapp) default_idx=1 ;;
      both)     default_idx=2 ;;
    esac
  fi

  local chosen
  chosen=$(gum choose --selected="${choices[$default_idx]}" \
    "Telegram only" "WhatsApp only" "Both Telegram and WhatsApp")

  case "$chosen" in
    "Telegram only")              CHANNELS="telegram" ;;
    "WhatsApp only")              CHANNELS="whatsapp" ;;
    "Both Telegram and WhatsApp") CHANNELS="both" ;;
  esac

  success "Channels: $CHANNELS"
}

# ─────────────────────────────────────────────────────────────────────────────
step_telegram_setup() {
  [[ "$CHANNELS" == "whatsapp" ]] && return

  header "Telegram Bot"

  gum style --bold "You need a bot token from @BotFather."
  echo
  dim "1. Open Telegram → search for @BotFather  (or visit https://t.me/BotFather)"
  dim "2. Send:  /newbot"
  dim "3. Follow the prompts — choose a name and username for your bot"
  dim "4. BotFather replies with a token like:  123456789:ABCDef..."
  echo
  gum confirm "Open BotFather and get your token, then press Enter to continue" \
    --affirmative "I have my token" --negative "Quit" || exit 0

  while true; do
    TG_TOKEN=$(_ask_secret "Paste your bot token" "$TG_TOKEN")
    if [[ "$TG_TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]{35,}$ ]]; then
      break
    else
      err "That doesn't look like a valid bot token — expected format: 1234567890:ABCDef..."
      TG_TOKEN=""
    fi
  done

  echo
  gum style "Restrict access to specific Telegram usernames?"
  dim "Format: JSON array — e.g.  [\"alice\",\"bob\"]   Leave blank to allow all users."
  TG_USERS=$(_ask 'e.g. ["alice","bob"] or leave blank to allow all' "$TG_USERS")

  success "Telegram configured"
}

# ─────────────────────────────────────────────────────────────────────────────
step_gws_setup() {
  header "Google Workspace"

  # ── OAuth credentials ─────────────────────────────────────────────────────
  if [[ -f "${HOME}/.config/gws/client_secret.json" ]]; then
    success "Google Cloud credentials already configured"
  else
    info "Setting up Google Cloud project and OAuth credentials."
    dim "gws will open your browser and guide you through creating the project."
    echo
    if ! gws auth setup; then
      err "gws auth setup failed."
      info "Try running manually: gws auth setup"
      info "Then re-run setup.sh"
      exit 1
    fi
    success "Google Cloud credentials configured"
  fi

  # ── Auth tokens ────────────────────────────────────────────────────────────
  if [[ -d "${HOME}/.config/gws" ]] && ls "${HOME}/.config/gws/credentials"*.json &>/dev/null 2>&1; then
    success "Google Workspace already authenticated"
  else
    info "Authenticating — a browser window will open."
    dim "Sign in with the Google account the assistant should access."
    echo
    if ! gws auth login; then
      err "gws auth login failed."
      info "Try: gws auth login"
      info "Then re-run setup.sh"
      exit 1
    fi
    success "Google Workspace authenticated"
  fi
}

# ─────────────────────────────────────────────────────────────────────────────
step_claude_auth() {
  header "Claude Authentication"

  local chosen
  chosen=$(gum choose \
    --selected="$([ "$CLAUDE_AUTH_TYPE" = 'api-key' ] && echo 'API key (Anthropic billing)' || echo 'Setup-token (recommended — uses your Claude subscription)')" \
    "Setup-token (recommended — uses your Claude subscription)" \
    "API key (Anthropic billing)")

  case "$chosen" in
    Setup-token*) CLAUDE_AUTH_TYPE="setup-token" ;;
    "API key"*)   CLAUDE_AUTH_TYPE="api-key" ;;
  esac

  if [[ "$CLAUDE_AUTH_TYPE" == "setup-token" ]]; then
    echo
    gum style --bold "Generate a setup-token on any machine where Claude Code is installed and logged in:"
    echo
    dim "  claude setup-token"
    echo
    gum confirm "Run that command, copy the token, then continue" \
      --affirmative "I have my token" --negative "Quit" || exit 0

    while true; do
      CLAUDE_SETUP_TOKEN_VAL=$(_ask_secret "Paste your setup-token" "$CLAUDE_SETUP_TOKEN_VAL")
      [[ -n "$CLAUDE_SETUP_TOKEN_VAL" ]] && break
      err "Token cannot be empty."
    done
  else
    echo
    while true; do
      ANTHROPIC_API_KEY_VAL=$(_ask_secret "Paste your Anthropic API key (starts with sk-ant-...)" "$ANTHROPIC_API_KEY_VAL")
      if [[ "$ANTHROPIC_API_KEY_VAL" =~ ^sk-ant- ]]; then
        break
      else
        err "That doesn't look like an Anthropic API key (expected: sk-ant-...)."
        ANTHROPIC_API_KEY_VAL=""
      fi
    done
  fi

  success "Claude auth configured"
}

# ─────────────────────────────────────────────────────────────────────────────
step_optional_keys() {
  header "Optional Features"

  gum style "Press Enter to skip any key you don't have."
  echo

  gum style --bold "Voice transcription (for voice messages in Telegram/WhatsApp):"
  GROQ_KEY=$(_ask_secret "Groq API key  (recommended)" "$GROQ_KEY")
  OPENAI_KEY=$(_ask_secret "OpenAI API key  (fallback)" "$OPENAI_KEY")
  DEEPGRAM_KEY=$(_ask_secret "Deepgram API key  (fallback)" "$DEEPGRAM_KEY")

  echo
  gum style --bold "Web search:"
  PERPLEXITY_KEY=$(_ask_secret "Perplexity API key  (enables web search in the assistant)" "$PERPLEXITY_KEY")

  success "Optional features saved"
}

# ─────────────────────────────────────────────────────────────────────────────
_update_env() {
  local pair key val
  local pairs=(
    "CLAUDE_SETUP_TOKEN=${CLAUDE_SETUP_TOKEN_VAL}"
    "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY_VAL}"
    "OA_TELEGRAM_BOT_TOKEN=${TG_TOKEN}"
    "OA_TELEGRAM_ALLOWED_USERS=${TG_USERS}"
    "GROQ_API_KEY=${GROQ_KEY}"
    "OPENAI_API_KEY=${OPENAI_KEY}"
    "DEEPGRAM_API_KEY=${DEEPGRAM_KEY}"
    "PERPLEXITY_API_KEY=${PERPLEXITY_KEY}"
  )
  for pair in "${pairs[@]}"; do
    key="${pair%%=*}"
    val="${pair#*=}"
    [[ -z "$val" ]] && continue
    if ! grep -q "^${key}=" .env; then
      echo "${key}=${val}" >> .env
    fi
  done
}

# ─────────────────────────────────────────────────────────────────────────────
step_write_env() {
  header "Write .env"

  if [[ -f ".env" ]]; then
    echo
    info "An existing .env was found."
    local action
    action=$(gum choose "Update — keep existing, add any new non-empty values" \
                        "Overwrite — replace entirely with values from this run" \
                        "Skip — leave .env unchanged")
    case "$action" in
      Update*)    _update_env; success ".env updated"; return ;;
      Skip*)      success ".env unchanged"; return ;;
      Overwrite*) ;;  # fall through to write below
    esac
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
  header "Launch open-assistant"

  mkdir -p "${HOME}/.open-assistant"

  gum spin --spinner dot --title "Building and starting containers (first build may take a few minutes)..." -- \
    $COMPOSE up -d --build || {
      err "$COMPOSE up failed."
      info "Check logs with:  $COMPOSE logs"
      exit 1
    }

  info "Waiting for assistant to be healthy..."
  local port="${OA_WEBHOOK_PORT:-8080}"
  local attempts=0
  while ! curl -sf "http://localhost:${port}/health" &>/dev/null; do
    sleep 2
    attempts=$((attempts + 1))
    if [[ $attempts -ge 30 ]]; then
      err "Assistant didn't become healthy after 60s."
      info "Check logs:  $COMPOSE logs assistant"
      exit 1
    fi
  done

  success "open-assistant is running"
}

# ─────────────────────────────────────────────────────────────────────────────
step_claude_token_exchange() {
  [[ "$CLAUDE_AUTH_TYPE" != "setup-token" ]] && return

  header "Activate Claude Auth"

  gum spin --spinner dot --title "Exchanging setup-token inside the container..." -- \
    docker exec assistant claude setup-token "${CLAUDE_SETUP_TOKEN_VAL}" || {
      err "Token exchange failed."
      info "Retry manually:"
      dim "  docker exec -it assistant claude setup-token <your-token>"
      info "Or authenticate interactively:"
      dim "  docker exec -it assistant claude login"
      return
    }

  success "Claude authenticated"
}

# ─────────────────────────────────────────────────────────────────────────────
step_whatsapp_qr() {
  [[ "$CHANNELS" == "telegram" ]] && return

  header "Link WhatsApp"

  gum style --bold "Scan the QR code with your phone to link WhatsApp."
  echo
  dim "1. Open WhatsApp on your phone"
  dim "2. Go to: Settings → Linked Devices → Link a Device"
  dim "3. Point your camera at the QR code that appears below"
  echo
  gum confirm "Ready to show the QR code" \
    --affirmative "Show QR code" --negative "Skip for now" || return 0

  info "Streaming Baileys logs (Ctrl-C to abort)..."
  echo

  while IFS= read -r line; do
    echo "  $line"
    if echo "$line" | grep -qi "connection open\|open connection\|linked\|ready"; then
      echo
      success "WhatsApp linked!"
      return
    fi
  done < <($COMPOSE logs -f baileys 2>&1)

  echo
  err "Log stream ended before WhatsApp was linked."
  info "Check container:  $COMPOSE ps baileys"
  info "Retry:            $COMPOSE logs -f baileys"
}

# ─────────────────────────────────────────────────────────────────────────────
step_done() {
  echo
  gum style \
    --border rounded --border-foreground 2 \
    --padding "1 4" --margin "0 2" \
    --bold --foreground 2 \
    "Setup complete!"
  echo

  gum style --bold "What's configured:"
  [[ "$CHANNELS" != "whatsapp" ]] && dim "✔ Telegram bot"
  [[ "$CHANNELS" != "telegram" ]] && dim "✔ WhatsApp (Baileys)"
  dim "✔ Google Workspace"
  dim "✔ Claude AI"
  echo

  gum style --bold "Next steps:"
  dim "Launch:         $COMPOSE up -d --build"
  dim "View logs:      $COMPOSE logs -f assistant"
  dim "Stop:           $COMPOSE down"
  dim "Schedules:      ~/.open-assistant/schedules.yaml  (see README.md)"
  echo
  dim "(setup state saved at .setup-state — delete it to start fresh)"
}

# ─────────────────────────────────────────────────────────────────────────────
main() {
  if [[ ! -f "docker-compose.yaml" ]]; then
    _plain_error "Please run setup.sh from the open-assistant project directory."
    exit 1
  fi

  _ensure_gum
  _load_state
  step_welcome
  step_prerequisites
  step_channel_selection
  step_telegram_setup
  _save_state
  step_gws_setup
  step_claude_auth
  _save_state
  step_optional_keys
  _save_state
  step_write_env
  # step_launch                   # run manually: $COMPOSE up -d --build
  # step_claude_token_exchange    # run after launch: docker exec assistant claude setup-token <token>
  step_whatsapp_qr
  step_done
}

main "$@"
