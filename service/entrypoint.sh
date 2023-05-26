#!/bin/sh
set -e
set -x

# Chown the mounted data volume
chown -R service:service "/data/"
chown -R service:service "/service/"

# Install the dependencies
su -s /bin/sh -c 'npm install' service
# Run setup
exec su -s /bin/sh -c 'node /service/server.js' service
su -s /bin/sh -c 'node /service/setup.js' service
# Start the server
