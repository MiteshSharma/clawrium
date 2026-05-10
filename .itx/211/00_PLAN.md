# Implementation Plan: TUI Chat Feature (#211)

## Overview

Add a chat panel to the bottom half of the agent details page, allowing users to interact with OpenClaw agents directly. Chat is the default focus when entering the detail screen. Sessions persist only during TUI runtime; no disk persistence.

## Analysis

### Current Architecture

- **TUI Framework**: Textual (v3.x) - event-driven TUI with CSS-like styling
- **Agent Detail Screen**: `screens/detail.py` - shows agent info via `DetailCards` widget
- **Chat Client**: `core/chat.py` - async WebSocket client (`OpenClawChatClient`)
- **Threading Model**: `@work(thread=True)` decorator for blocking operations

### Current DetailScreen Layout
```
┌─────────────────────────────────────────┐
│ AGENT DETAIL — agent-name               │
├─────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐       │
│  │  IDENTITY   │  │ MODEL/COST  │       │
│  └─────────────┘  └─────────────┘       │
│  ┌─────────────┐  ┌─────────────┐       │
│  │   CONFIG    │  │   HEALTH    │       │
│  └─────────────┘  └─────────────┘       │
├─────────────────────────────────────────┤
│ [dim]Press 's' to stop, 'r' to restart  │
└─────────────────────────────────────────┘
```

### New Layout (50/50 Split)
```
┌─────────────────────────────────────────┐
│ AGENT DETAIL — wolf-i                   │
├─────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐       │  ← Top 50%
│  │  IDENTITY   │  │ MODEL/COST  │       │    Agent info
│  └─────────────┘  └─────────────┘       │    (DetailCards)
│  ┌─────────────┐  ┌─────────────┐       │
│  │   CONFIG    │  │   HEALTH    │       │
│  └─────────────┘  └─────────────┘       │
├─────────────────────────────────────────┤
│ ┌─ CHAT ──────────────────────────────┐ │  ← Bottom 50%
│ │ you> hello                          │ │    Chat panel
│ │ wolf-i> Hi! How can I help?         │ │    (ChatPanel widget)
│ │                                     │ │
│ ├─────────────────────────────────────┤ │
│ │ > type message here...          [⏎] │ │  ← Input (default focus)
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

## Files to Modify/Create

### New Files
| File | Purpose |
|------|---------|
| `src/clawrium/cli/tui/widgets/chat_panel.py` | ChatPanel widget with message display + input |
| `tests/test_tui/test_tui_chat.py` | Tests for chat panel |

### Modified Files
| File | Change |
|------|--------|
| `src/clawrium/cli/tui/screens/detail.py` | Add ChatPanel, restructure layout to 50/50 split |
| `src/clawrium/cli/tui/styles/app.tcss` | Styles for chat panel, vertical split layout |
| `src/clawrium/cli/tui/data.py` | Extend AgentViewModel with gateway config fields |

## Implementation Steps

### Phase 1: Data Layer Enhancement

1. **Extend AgentViewModel** in `data.py`:
   - Add `gateway_url: str | None`
   - Add `gateway_auth: str | None`
   - Add `gateway_device_id: str | None`
   - Add `gateway_device_key: str | None`
   - Extract from `agent_record['config']['gateway']` during data fetch
   - Reuse URL reconstruction logic from `cli/chat.py`

### Phase 2: Chat Panel Widget

2. **Create `widgets/chat_panel.py`**:
   ```python
   class ChatPanel(Widget):
       """Chat panel with message history and input field."""

       def __init__(self, agent: AgentViewModel, **kwargs):
           self._agent = agent
           self._messages: list[ChatMessage] = []
           self._client: OpenClawChatClient | None = None

       def compose(self) -> ComposeResult:
           yield Static("CHAT", classes="chat-title")
           yield RichLog(id="chat-log", wrap=True)  # Message history
           yield Input(placeholder="Type message...", id="chat-input")

       def on_mount(self) -> None:
           self.query_one("#chat-input").focus()  # Default focus

       @work(thread=True)
       def _send_message(self, message: str) -> None:
           asyncio.run(self._async_send(message))
   ```

3. **Message handling**:
   - `ChatMessage` dataclass: `role: Literal["user", "agent"]`, `content: str`, `timestamp: datetime`
   - Append to `_messages` list on send/receive
   - Render in `RichLog` with role-based styling
   - User messages: `you> {content}`
   - Agent messages: `{agent_name}> {content}` (e.g., `wolf-i> Hi!`)

4. **Streaming response display**:
   - Use `on_delta` callback to update `RichLog` incrementally
   - `call_from_thread()` for thread-safe UI updates

### Phase 3: DetailScreen Restructuring

5. **Modify `screens/detail.py`**:
   - Wrap existing content in `Vertical` container with `height: 50%`
   - Add `ChatPanel` widget in bottom half with `height: 50%`
   - Set focus to chat input on mount
   - Only show chat panel for OpenClaw agents (hide for others)

   ```python
   def compose(self) -> ComposeResult:
       yield Label(f"AGENT DETAIL — {escape(self._agent['agent_name'])}")
       with Vertical(id="detail-top"):
           yield DetailCards(agent=self._agent)
       if self._agent["agent_type"] == "openclaw":
           yield ChatPanel(agent=self._agent, id="chat-panel")
       yield Static("[dim]esc: back | s: stop | r: restart[/dim]")
   ```

### Phase 4: Styling

6. **Update `app.tcss`**:
   ```css
   #detail-top {
       height: 50%;
       overflow-y: auto;
   }

   ChatPanel {
       height: 50%;
       border: round $primary-darken-2;
   }

   #chat-log {
       height: 1fr;
       background: $surface;
   }

   #chat-input {
       dock: bottom;
       height: 3;
   }

   .chat-user { color: $success; }
   .chat-agent { color: $primary; }
   ```

### Phase 5: Testing

7. **Create `test_tui_chat.py`**:
   - Test ChatPanel mounting with valid OpenClaw agent
   - Test chat input has default focus
   - Test message sending (mocked WebSocket)
   - Test streaming display updates via RichLog
   - Test chat panel hidden for non-OpenClaw agents
   - Test session memory within TUI runtime

## Session Memory Model

```
DetailScreen (agent A - OpenClaw)
└── ChatPanel
    └── _messages: list[ChatMessage]  # In-memory, persists while screen exists

DetailScreen (agent B - OpenClaw)
└── ChatPanel
    └── _messages: list[ChatMessage]  # Separate session

DetailScreen (agent C - zeroclaw)
└── (No ChatPanel - not OpenClaw)
```

- Each ChatPanel maintains its own message history
- Messages persist while DetailScreen is in screen stack
- TUI exit clears all sessions (no disk persistence)

## Test Strategy

1. **Unit Tests**:
   - ChatPanel compose/mount
   - Default focus on input
   - Message rendering with role styling
   - Async bridge behavior (mocked client)

2. **Integration Tests**:
   - DetailScreen layout with ChatPanel
   - Input submission → message display flow
   - Streaming response updates
   - Error handling (connection failures)
   - Non-OpenClaw agents don't show chat

3. **Manual Testing**:
   - Real agent chat interaction
   - 50/50 layout rendering
   - Scrolling in chat log
   - Long messages / word wrap

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Layout complexity with 50/50 split | Use Textual's Vertical container with percentage heights |
| Input focus management | Set focus in `on_mount`, handle focus restoration after actions |
| RichLog performance with many messages | Limit visible history or implement virtual scrolling if needed |
| Gateway connection on screen load | Connect lazily on first message, not on mount |

## Complexity Assessment

**Medium complexity** - Widget integration with established patterns
- No subtasks needed
- Direct execution recommended

## Acceptance Criteria Mapping

| AC | Implementation |
|----|----------------|
| Agent details page includes chat interface | ChatPanel widget in bottom 50% of DetailScreen |
| User can send message from TUI | Input widget with enter-to-send |
| Agent responses visible in same view | RichLog widget with streaming updates |
| Conversation retained while TUI open | Message list on ChatPanel instance |
| No persistence after exit | In-memory storage only |
| Reopening TUI starts fresh | No disk I/O for chat state |

---

<details>
<summary>Prompt Log</summary>

**Stage**: planning
**Skill**: /itx:plan-create
**Timestamp**: 2026-05-04T08:50:00Z
**Model**: claude-opus-4-5-20251101

```prompt
/itx:plan-create 211

User revision: Don't create separate ChatScreen. Chat panel should be embedded
in agent detail page, taking bottom 50% of screen. Chat input should be default
focus when entering the screen.
```

</details>
