# 06. Geo Resolving (City to Timezone)

- **How it works:** `GeoResolveStage` maps a city from the message or profile to an IANA timezone.
- **Flags:** Uses the `pycountry` package to get a country flag emoji.
- **Future Plan:** Basic implementation for MVP. May transition to external APIs (Google Maps/Mapbox) later.
