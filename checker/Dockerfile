FROM python:3.9-buster
RUN apt-get update && apt-get update -y
RUN apt-get install libnss3 -y

# add checker user
RUN useradd -rms /bin/bash -u 1000 checker
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
RUN sh -c 'echo "deb https://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list'
RUN apt-get update
RUN apt-get -y install google-chrome-stable

WORKDIR /checker
COPY ./src .
RUN chown -R checker:checker /checker
COPY requirements.txt .
USER checker
RUN python3 -m pip install -r requirements.txt



ENTRYPOINT [ "/home/checker/.local/bin/gunicorn", "-c", "gunicorn.conf.py", "checker:app" ]