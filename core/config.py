"""Constants: languages and alert thresholds."""
LANGS = {"English": "en", "தமிழ்": "ta", "हिन्दी": "hi"}
LANG_NAMES = {"en": "English", "ta": "Tamil", "hi": "Hindi"}
TTS_CODES = {"en": "en", "ta": "ta", "hi": "hi"}

# Weather alert thresholds (see README section on the alert engine)
HEAVY_RAIN_MM = 20          # daily rain at or above this = heavy rain alert
HEAVY_RAIN_PROB = 70        # ... or probability >= this together with >= 10 mm
SPRAY_MAX_PROB = 20         # best spray day: rain probability <= this ...
SPRAY_MAX_WIND = 15         # ... and wind <= this (km/h)
HEAT_C = 38                 # max temperature at or above this = heat alert
COLD_C = 8                  # min temperature at or below this = cold alert
WIND_KMH = 30               # wind at or above this = strong wind alert
DRY_SPELL_MM = 2            # total rain over next 5 days below this = dry spell ...
DRY_SPELL_ET0 = 4.0         # ... when average evapotranspiration is at least this (mm/day)
HUMID_PCT = 85              # humidity at or above this with rain soon = fungal risk
