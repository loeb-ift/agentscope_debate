#!/bin/sh
# Copy mounted settings to a temp location
cp /etc/searxng/settings.yml /tmp/settings.yml
if [ -f /etc/searxng/limiter.toml ]; then
    cp /etc/searxng/limiter.toml /tmp/limiter.toml
fi

# Replace secrets
# Use | as delimiter to avoid issues with / in keys
sed -i "s|__BRAVE_SEARCH_API_KEY__|${BRAVE_SEARCH_API_KEY}|g" /tmp/settings.yml
sed -i "s|__GOOGLE_SEARCH_API_KEY__|${GOOGLE_SEARCH_API_KEY}|g" /tmp/settings.yml
sed -i "s|__GOOGLE_CSE_ID__|${GOOGLE_CSE_ID}|g" /tmp/settings.yml

# Set SEARXNG_SETTINGS_PATH to the temp file
export SEARXNG_SETTINGS_PATH=/tmp/settings.yml

# Execute original entrypoint
exec /usr/local/searxng/entrypoint.sh
