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
# Install nginx
RUN apk add openssl curl ca-certificates
RUN printf "%s%s%s\n" \
"http://nginx.org/packages/alpine/v" \
`egrep -o '^[0-9]+\.[0-9]+' /etc/alpine-release` \
"/main" | tee -a /etc/apk/repositories
RUN curl -o /tmp/nginx_signing.rsa.pub https://nginx.org/keys/nginx_signing.rsa.pub
RUN openssl rsa -pubin -in /tmp/nginx_signing.rsa.pub -text -noout
RUN mv /tmp/nginx_signing.rsa.pub /etc/apk/keys/
RUN apk update && apk add nginx openrc
COPY src/nginx.conf /etc/nginx/nginx.conf
RUN chown service:service /etc
RUN chown -R service:service /etc/init.d/
# Copy our entrypoint.sh and make it executable
COPY entrypoint.sh /
RUN chmod +x /entrypoint.sh

# Copy our service
COPY src/ /service/

# Change the working directory.
WORKDIR /service/

# Run the service
ENTRYPOINT ["/entrypoint.sh"]