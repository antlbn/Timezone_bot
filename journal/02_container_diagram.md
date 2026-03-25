# 02. Container Diagram (C4 Model - Level 2)

This document provides a detailed view of the functional "containers" within the **Timezone Bot** system and their interactions with external systems and components.

## Container Diagram

```mermaid
graph TD
    User([Chat Participant])
    
    subgraph Platforms [Messaging Platforms]
        TG_API[[Telegram App]]
        DC_API[[Discord App]]
    end

    subgraph BotApp [Timezone Bot Application]
        TG_Adp["Telegram Adapter"]
        DC_Adp["Discord Adapter"]
        
        Core["Agentic Core (LangGraph)"]
        Geo["Geo Resolver"]
    end

    subgraph DBs [Persistent Storage]
        DB1[("bot.db (Core Data)")]
        DB2[("checkpoints.db (Agent State)")]
    end

    subgraph Ext [External Services]
        LLM[[LLM Provider]]
        Nom[[Nominatim Geocoding]]
    end

    User --> TG_API
    User --> DC_API
    
    TG_API <--> TG_Adp
    DC_API <--> DC_Adp
    
    TG_Adp <-->|Invoke / Execute Tool| Core
    DC_Adp <-->|Invoke / Execute Tool| Core
    
    TG_Adp --> Geo
    DC_Adp --> Geo
    
    Core <-->|Prompt / Tool Call| LLM
    Core <-->|Save/Load State| DB2
    Core -->|Lookup Users| DB1
    
    Geo --> Nom

    %% Styling
    style User fill:#08427b,color:#fff
    style TG_Adp fill:#28a745,color:#fff
    style DC_Adp fill:#28a745,color:#fff
    style Core fill:#28a745,color:#fff
    style BotApp fill:none,stroke:#28a745,stroke-dasharray: 5 5
```

## Description of Containers

| Container | Technology | Responsibility |
|-----------|------------|----------------|
| **Telegram Bot Process** | Python 3.12, `aiogram` | Handles Telegram messages, callback queries, and deep links. Orchestrates the onboarding flow. |
| **Discord Bot Process** | Python 3.12, `discord.py` | Handles Discord events, slash commands, and modals. Coordinates Discord-specific UI elements. |
| **Event Detection Pipeline** | LangGraph, LangChain | Orchestrates the agentic flow: detection, extraction, and tool-calling decisions. |
| **bot.db** | SQLite, `aiosqlite` | Stores persistent data: user settings, city/timezone, and chat memberships. |
| **graph_checkpoints.db** | SQLite, `langgraph` | Specialized database for agent state persistence, message history, and checkpointing. |
| **Geo/TZ Resolver** | `geopy`, `timezonefinder` | Local processing of city names into coordinates and timezones, complemented by Nominatim for external geocoding. |
| **In-Memory Cache** | `OrderedDict` (LRU) | Caches user snapshots and recent historical context to minimize database lookups and token usage. |
