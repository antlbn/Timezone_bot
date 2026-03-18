# Technical Spec: Response Format

## 1. Overview

Bot response format for time conversion.

---

## 2. Basic Format

**Default (without usernames):**
```
14:00 Berlin 🇩🇪
08:00 New York 🇺🇸
22:00 Tokyo 🇯🇵

/tb_help
```

**With usernames (optional):**
```
14:00 Berlin 🇩🇪 @john
08:00 New York 🇺🇸 @alice, @bob
22:00 Tokyo 🇯🇵 @yuki

/tb_help
```


---

## 3. Configuration

```yaml
bot:
  show_usernames: false  # default: disabled
```

---

## 4. Grouping Rules

- If multiple users in same location → **one entry**, names comma-separated
- No duplicates of timezone/city
- Sorting: by UTC offset (from smallest to largest)

**Grouping example:**
```
# 2 users in New York → one entry
08:00 New York 🇺🇸 @alice, @bob
```

---

## 5. Day Transition

If time transitions to another day:

```
14:00 Berlin 🇩🇪
08:00 New York 🇺🇸
22:00⁺¹ Tokyo 🇯🇵
```

| Marker | Meaning |
|--------|---------|
| `⁺¹` | Next day |
| `⁻¹` | Previous day |

---

## 6. Multiple Times

If a message contains multiple times, the bot aggregates them into a **single, multi-line result** with indentation to align with the sender's name.

**Example:**
```
Alice: 
10:30 Sarajevo 🇧🇦
09:30 London 🇬🇧

15:00 Sarajevo 🇧🇦
14:00 London 🇬🇧

/tb_help
```

This prevents chat clutter and keeps all relevant conversions in one atomic block.

---

## 7. Display Limit

From `configuration.yaml`:
```yaml
bot:
  display_limit_per_chat: 10
```

If more users than limit:
```
14:00 Berlin 🇩🇪
08:00 New York 🇺🇸
... +5 more
```

---

## 8. Empty State

If only the sender is in the chat:
```
14:00 Berlin 🇩🇪
```

---

## 9. Country Flags

Flags are determined by country from geocoding result.
Mapping country code → emoji flag.

