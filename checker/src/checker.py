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
)
from enochecker3.utils import FlagSearcher, assert_equals, assert_in

SERVICE_PORT = 3000
checker = Enochecker("asocialnetwork", SERVICE_PORT)
app = lambda: checker.app


def encode(message, recipient):
    return functools.reduce(lambda a, b: a+b, ([chr(ord(a) ^ ord(b)) for (a,b) in zip(message, recipient)]))


async def register(client, username, password, logger):
    logger.debug(f"Registering as {username}:{password}")
    r = await client.post(f"http://localhost:{SERVICE_PORT}/register", json={"username": username, "password": password, "confirmPassword": password})
    assert_equals(r.status_code, 302, "registering failed")
    return r.cookies


async def login(client, username, password, logger):
    logger.debug(f"Logging in as {username}:{password}")
    r = await client.post(f"http://localhost:{SERVICE_PORT}/login", json={"username": username, "password": password})
    assert_equals(r.status_code, 302, "login failed")
    return r.cookies


async def sendMessage(client, recipient, message, logger):
    username = secrets.token_hex(32)
    password = secrets.token_hex(32)
    encoded_message = encode(message, recipient * (len(message) // len(recipient) + 1))
    cookie = await register(client, username, password, logger)
    await client.post(f"http://localhost:{SERVICE_PORT}/messages/", json={"recipient": recipient, "message": encoded_message}, cookies=cookie)
    return username, password, cookie


async def retrieveMessage(client, recipient, logger, username, password):
    cookie = await login(client, username, password, logger)
    logger.debug(f"Retrieving Message for {username}:{password}")
    r = await client.get(f"http://localhost:{SERVICE_PORT}/messages/{recipient}", cookies=cookie)
    assert_equals(r.status_code, 200, "retrieving message failed")
    return r

@checker.putflag(0)
async def putflag0(task: PutflagCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB, logger: LoggerAdapter) -> None:
    flag = task.flag
    recipient = "a"
    username, password, cookie = await sendMessage(client, recipient, flag, logger)
    r = await retrieveMessage(client, recipient, logger, username, password)
    assert_in(flag, r.text, "flag missing from messages")
    await chain_db.set("userdata", (username, password, flag))


@checker.getflag(0)
async def getflag0(task: GetflagCheckerTaskMessage, client: AsyncClient, db: ChainDB, logger: LoggerAdapter) -> None:
    try:
        username, password, flag = await db.get("userdata")
    except KeyError:
        raise MumbleException("Missing database entry from putflag")
    r = await retrieveMessage(client, "a", logger, username, password)
    assert_in(task.flag, r.text, "flag missing from note")


@checker.putnoise(0)
async def putnoise0(task: PutnoiseCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB, logger: LoggerAdapter) -> None:
    noise = secrets.token_hex(32)
    recipient = "a"
    username, password, cookie = await sendMessage(client, recipient, noise, logger)
    await chain_db.set("noise", (username, password, noise))


@checker.getnoise(0)
async def getnoise0(task: GetnoiseCheckerTaskMessage, client: AsyncClient, db: ChainDB, logger: LoggerAdapter) -> None:
    try:
        username, password, noise = await db.get("noise")
    except KeyError:
        raise MumbleException("Missing database entry from putnoise")
    r = await retrieveMessage(client, "a", logger, username, password)
    assert_in(noise, r.text, "noise missing from note")


@checker.exploit(0)
async def exploit_test(searcher: FlagSearcher, client: AsyncClient) -> Optional[str]:
    r = await client.get(
        "/note/*",
    )
    assert not r.is_error

    if flag := searcher.search_flag(r.text):
        return flag


# def xss():
#     start = time.time()
#     options = webdriver.ChromeOptions()
#     options.add_argument('--headless=new')
#     driver = webdriver.Chrome(options=options)
#     driver.get("http://localhost:3000/messages/aa")
#     if not login(driver, "a", "a"):
#         driver.get("http://localhost:3000/messages/aa")
#     reloads = 0
#     while True:
#         if time.time() - start > 15:
#             break
#         # time.sleep(0.05)
#         driver.refresh()
#         reloads += 1
#     print(reloads)
#     driver.quit()


if __name__ == "__main__":
    checker.run()
