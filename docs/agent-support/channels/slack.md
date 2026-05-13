# Slack

**Status:** ✅ Supported (OpenClaw, Hermes)

**Mode:** Socket Mode (default) — outbound WebSocket, no public endpoint needed.

Slack channel allows your agent to operate as a bot in Slack workspaces, responding to mentions, DMs, and thread messages.

---

## Token Model

Socket Mode requires **two tokens**:

| Token | Prefix | Secret Name | Purpose |
|-------|--------|-------------|---------|
| **Bot Token** | `xoxb-` | `SLACK_BOT_TOKEN` | Authenticates bot actions (send messages, read channels) |
| **App Token** | `xapp-` | `SLACK_APP_TOKEN` | Authenticates the WebSocket connection to Slack |

Both tokens use SecretRef objects in config and fall back to environment variables.

### Env Fallback

For the default account, tokens resolve from environment if not in config:

```bash
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
```

---

## Setup

### Step 1: Create a Slack App

1. Go to **[https://api.slack.com/apps/new](https://api.slack.com/apps/new)**
2. Choose **From a manifest**
3. Select your workspace
4. Paste this manifest:

```json
{
  "display_information": {
    "name": "OpenClaw",
    "description": "Slack connector for OpenClaw"
  },
  "features": {
    "bot_user": {
      "display_name": "OpenClaw",
      "always_online": true
    },
    "app_home": {
      "messages_tab_enabled": true,
      "messages_tab_read_only_enabled": false
    }
  },
  "oauth_config": {
    "scopes": {
      "bot": [
        "app_mentions:read",
        "channels:history",
        "channels:read",
        "chat:write",
        "im:history",
        "im:read",
        "im:write",
        "mpim:history",
        "mpim:read",
        "mpim:write",
        "reactions:read",
        "reactions:write",
        "users:read",
        "pins:read"
      ]
    }
  },
  "settings": {
    "socket_mode_enabled": true,
    "event_subscriptions": {
      "bot_events": [
        "app_mention",
        "message.channels",
        "message.im",
        "message.mpim",
        "reaction_added",
        "member_joined_channel"
      ]
    }
  }
}
```

5. Click **Create**

### Step 2: Generate App-Level Token

This is the `xapp-` token required for Socket Mode.

1. Go to **Basic Information** (sidebar) > **App-Level Tokens**
2. Click **Generate Token and Scopes**
3. Name it: `socket-mode`
4. Add scope: **`connections:write`**
5. Click **Generate**
6. **Copy the token** — it starts with `xapp-`
7. Save this — you'll enter it as `SLACK_APP_TOKEN` during configuration

### Step 3: Install App to Workspace

1. Go to **OAuth & Permissions** (sidebar)
2. Click **Install to Workspace**
3. Authorize the app
4. **Copy the Bot User OAuth Token** — it starts with `xoxb-`
5. Save this — you'll enter it as `SLACK_BOT_TOKEN` during configuration

### Step 4: Invite Bot to a Channel

In Slack, go to the channel where you want the bot and type:

```
@OpenClaw
```

Slack will prompt you to invite the bot to the channel.

### Step 5: Get Your User ID

1. In Slack, click your profile picture (top right)
2. Click **⋯** (three dots) > **Copy Member ID**
3. The ID starts with `U` (e.g., `U01ABC2DEF`)
4. This goes in the `allowFrom` list during configuration

### Step 6: Configure in Clawrium

```bash
clm agent configure <agent-name>
# Select "slack" when prompted for channel
# Enter your Bot Token, App Token, and User ID
```

Or reconfigure just the channels stage:

```bash
clm agent configure <agent-name> --stage channels
```

---

## Configuration Structure

After setup, the Slack config in your agent's `openclaw.json` looks like:

```json
{
  "channels": {
    "slack": {
      "enabled": true,
      "mode": "socket",
      "botToken": {
        "source": "env",
        "provider": "default",
        "id": "SLACK_BOT_TOKEN"
      },
      "appToken": {
        "source": "env",
        "provider": "default",
        "id": "SLACK_APP_TOKEN"
      },
      "allowFrom": ["U01ABC2DEF"],
      "groupPolicy": "allowlist",
      "dmPolicy": "pairing"
    }
  }
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | `true` | Enable Slack channel |
| `mode` | string | `"socket"` | Connection mode (Socket Mode) |
| `botToken` | SecretRef | — | Bot token reference (`xoxb-...`) |
| `appToken` | SecretRef | — | App-level token reference (`xapp-...`) |
| `allowFrom` | string[] | `[]` | User IDs allowed to interact with the bot |
| `groupPolicy` | string | `"allowlist"` | Group access policy: `open`, `allowlist`, `disabled` |
| `dmPolicy` | string | `"pairing"` | DM access policy: `pairing`, `allowlist`, `open`, `disabled` |

### SecretRef Object

Tokens use SecretRef objects instead of plaintext values. The secret value is stored in Clawrium's encrypted secrets storage, not in config files.

```json
{
  "source": "env",
  "provider": "default",
  "id": "SLACK_BOT_TOKEN"
}
```

At runtime, OpenClaw resolves the token from the environment file written by Clawrium.

---

## Hermes Configuration

Hermes uses a simpler configuration model — env vars rendered directly into `~/.hermes/.env`. There are no SecretRef objects; tokens are written as plain values in the env file (mode 0600 on the agent host).

### Env vars rendered by clm

| Variable | Required | Description |
|----------|:--------:|-------------|
| `SLACK_BOT_TOKEN` | yes | Bot User OAuth Token (`xoxb-...`) |
| `SLACK_APP_TOKEN` | yes | App-Level Token for Socket Mode (`xapp-...`) |
| `SLACK_ALLOWED_USERS` | yes | Comma-separated Slack Member IDs (e.g., `U01ABC2DEF3,U04XYZ7GHI8`) |
| `SLACK_HOME_CHANNEL` | no | Channel ID for cron/scheduled messages (e.g., `C01234567890`) |
| `SLACK_HOME_CHANNEL_NAME` | no | Display name for the home channel |

### Required scopes (minimal set for Hermes)

| Scope | Purpose |
|-------|---------|
| `app_mentions:read` | Bot can see when @-mentioned in channels |
| `chat:write` | Bot can send messages |
| `channels:read` | Bot can list public channels |
| `groups:read` | Bot can list private channels it's a member of |
| `im:history` | Bot can read DM history |
| `im:read` | Bot can read DM metadata |
| `im:write` | Bot can open/write DMs |
| `users:read` | Bot can look up user info |

### Required event subscriptions

| Event | Purpose |
|-------|---------|
| `app_mention` | Fires when someone @-mentions the bot in a channel |
| `message.im` | Fires on direct messages to the bot |

### Access control differences from OpenClaw

| Aspect | OpenClaw | Hermes |
|--------|----------|--------|
| **Config location** | `openclaw.json` (SecretRef objects) | `~/.hermes/.env` (plain env vars) |
| **DM policy** | Configurable (`pairing`, `allowlist`, `open`, `disabled`) | `SLACK_ALLOWED_USERS` allowlist only |
| **Group policy** | Configurable (`open`, `allowlist`, `disabled`) | Channel membership controls access (invite-only) |
| **Token storage** | `secrets.json` → rendered to env at runtime | `secrets.json` → rendered to `.env` at configure time |

For the full Hermes Slack setup walkthrough, see [Hermes Support Matrix > Slack walkthrough](../hermes.md#slack-walkthrough).

---

## Access Control

### DM Policy (`dmPolicy`)

| Policy | Behavior |
|--------|----------|
| `pairing` (default) | New DM users must approve via `clm pairing approve slack <code>` |
| `allowlist` | Only users in `allowFrom` can DM |
| `open` | Anyone can DM (requires `allowFrom: ["*"]`) |
| `disabled` | No DMs allowed |

### Group Policy (`groupPolicy`)

| Policy | Behavior |
|--------|----------|
| `allowlist` (default) | Bot only responds in explicitly allowed channels |
| `open` | Bot responds in all channels it's invited to |
| `disabled` | No channel responses |

---

## Troubleshooting

### Bot not responding in channels

- Verify `groupPolicy` is not `disabled`
- Check bot is invited to the channel (`@OpenClaw` in channel)
- Verify `app_mentions:read` and `channels:history` scopes are enabled

### Bot not responding to DMs

- Check `dmPolicy` — default is `pairing`, new users must be approved first
- Run `clm pairing list slack` to see pending approvals

### Socket Mode not connecting

- Verify both `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN` are set
- Check that Socket Mode is enabled in Slack app settings
- Verify the App-Level Token has `connections:write` scope

### "Invalid bot token format" error

- Bot token must start with `xoxb-` and contain only alphanumeric characters and hyphens
- Copy the full token from **OAuth & Permissions** in Slack app settings

### "Invalid app token format" error

- App token must start with `xapp-1-` followed by alphanumeric and hex characters
- Copy the full token from **Basic Information > App-Level Tokens**

---

[Back to Channels](index.md)