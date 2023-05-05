# Use a suitable base-image.
FROM node:20-alpine3.16
RUN apk add shadow
RUN userdel -r node
# Create a seperate user and chown new directories if necessary
RUN addgroup --system service
RUN adduser --system --ingroup service --uid 1000 service
RUN apk add npm
# Create our mapped data volume endpoint
RUN mkdir /data/

# Copy our entrypoint.sh and make it executable
COPY entrypoint.sh /
RUN chmod +x /entrypoint.sh

# Copy our service
COPY src/ /service/

# Change the working directory.
WORKDIR /service/

# Run the service
ENTRYPOINT ["/entrypoint.sh"]