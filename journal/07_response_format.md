# 07. Response Format

This document defines the user-facing format of conversion replies.

## 1. Goals

Replies must be:

- readable on mobile,
- compact in active chats,
- deterministic,
- consistent across Telegram and Discord.

## 2. Structural Rules

### 2.1 One event -> one bot message

If a message contains multiple time points for the same event, the bot should publish one combined reply rather than several separate replies.

### 2.1.1 Render modes

The formatter supports two user-facing layouts controlled by `bot.render_mode`:

- `vertical` - default vertical blocks with flags
- `compact_inline` - inline sentences without flags, e.g. `deadline | 10:00 Moscow, 09:00 Vienna`

### 2.2 Vertical layout

Each time point is formatted as a vertical block. Blocks are separated by a blank line.

### 2.3 Sender/source line first

For each point, the first line represents the source time and source city.

Example:

```text
14:00 Berlin 🇩🇪
08:00 New York 🇺🇸
22:00 Tokyo 🇯🇵
```

## 3. Grouping Rules

1. Group participants by timezone.
2. For each timezone group, render one line.
3. If `show_usernames=true`, append usernames for members in that timezone group.
4. Sort groups by UTC offset.

If multiple members share the same timezone, they should not create duplicate lines.

## 4. Day Offset Markers

When converted local date differs from the source local date:

- next day -> `⁺¹`
- previous day -> `⁻¹`

Example:

```text
14:00 Berlin 🇩🇪
08:00 New York 🇺🇸
22:00⁺¹ Tokyo 🇯🇵
```

## 5. Multi-Point Output

For multiple points in one event, format as:

```text
call
10:30 Sarajevo 🇧🇦
09:30 London 🇬🇧

deadline
15:00 Sarajevo 🇧🇦
14:00 London 🇬🇧
```

An optional sender prefix may wrap the whole body:

```text
Alice: call
10:30 Sarajevo 🇧🇦
09:30 London 🇬🇧
```

In `compact_inline` mode the same idea becomes:

```text
deadline | 10:00 Moscow, 09:00 Vienna
review | 15:00 Moscow, 14:00 Vienna
```

Optionally, `compact_inline` may be wrapped in a code block when
`bot.compact_inline_monospace=true` so event labels align reliably in chat UIs.

## 6. Display Limit

The formatter honors `bot.display_limit_per_chat`.

- `0` means "show all"
- otherwise only the first `N` non-sender members are shown
- if truncated, append:
  `... +X more`

## 7. Footer

The action layer may append a short footer when the tool call contains a user-facing comment.

This footer is emphasized and belongs to the reply body, not to a command footer like `/tb_help`.

## 8. Rebuild Notes

If the formatter is rebuilt:

1. keep output vertical,
2. keep timezone-group aggregation,
3. keep day-offset markers,
4. keep multi-point aggregation in a single message,
5. do not append command help text to normal conversion replies.
