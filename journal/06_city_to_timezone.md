# 06. City to Timezone Resolution

This document specifies the geo-resolution layer that maps user input to an IANA timezone.

## 1. Purpose

The resolver handles two kinds of input:

- city text such as `Berlin` or `Paris, France`,
- fallback manual time such as `14:30`.

Its output is a normalized location record:

- `city`
- `timezone`
- `flag`
- optional metadata such as `country_code`

## 2. Current Runtime Design

The implementation uses:

- `geopy.Nominatim` for geocoding,
- `timezonefinder` for coordinates -> IANA timezone,
- async wrappers that move blocking geocoding off the main event loop,
- in-process cache for repeated city lookups,
- a small offset-to-timezone map for manual-time fallback.

## 3. Resolution Order

`resolve_timezone_from_input(...)` follows this order:

1. try to parse the input as a time,
2. if successful, derive a rough UTC offset and map it to a representative timezone,
3. otherwise treat the input as a city and geocode it.

This ordering avoids false city matches for inputs like `19:53`.

## 4. City Resolution Contract

`get_timezone_by_city(city_name)` should:

1. geocode the city name,
2. extract coordinates,
3. resolve an IANA timezone from coordinates,
4. derive country flag from the country code,
5. return a normalized record.

If no location is found, return `None`.

If the external geocoder is unavailable, return an error-shaped result that can be logged and handled gracefully by callers.

## 5. Current Limitations

### 5.1 First-result policy

If the geocoder returns multiple valid places, the current system uses the first match.

This is acceptable for MVP, but it is not a strong disambiguation strategy.

### 5.2 Manual-time fallback is approximate

Manual time fallback maps an offset to one representative timezone. It is a recovery mechanism, not a precise geographic identity model.

### 5.3 External dependency still on cache-miss path

Blocking geocoding is now isolated from the event loop, but a cache miss still depends on an external provider in the runtime path.

That means provider slowness no longer freezes the whole async loop, but it can still delay the specific operation that needs geo resolution.

## 6. Performance and Reliability Requirements

For a stronger production version, preserve the same functional contract but improve execution strategy:

1. keep blocking geocoding off the main async event loop,
2. add local caching for repeated city lookups,
3. respect external provider rate limits,
4. keep timeouts explicit,
5. make failure visible in logs.

## 7. Rebuild Notes

If the geo layer is rebuilt:

1. preserve the two-mode input contract: city or manual time,
2. preserve IANA timezone output,
3. preserve regex-first handling for manual time,
4. do not silently collapse all failures into one guessed timezone.
