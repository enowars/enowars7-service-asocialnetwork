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
import time
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager

SERVICE_PORT = 3000
checker = Enochecker("asocialnetwork", SERVICE_PORT)
app = lambda: checker.app


def encode(message, recipient):
    return functools.reduce(lambda a, b: a+b, ([chr(ord(a) ^ ord(b)) for (a,b) in zip(message, recipient)]))


async def register(task, client, username, password, logger):
    logger.debug(f"Registering as {username}:{password}")
    r = await client.post(f"{task.address}/register", json={"username": username, "password": password, "confirmPassword": password})
    assert_equals(r.status_code, 302, "registering failed")
    return r.cookies


async def login(task, client, username, password, logger):
    logger.debug(f"Logging in as {username}:{password}")
    r = await client.post(f"{task.address}/login", json={"username": username, "password": password})
    assert_equals(r.status_code, 302, "login failed")
    return r.cookies


async def sendMessage(task, client, recipient, message, logger):
    username = secrets.token_hex(32)
    password = secrets.token_hex(32)
    encoded_message = encode(message, recipient * (len(message) // len(recipient) + 1))
    cookie = await register(task, client, username, password, logger)
    await client.post(f"{task.address}/messages/", json={"recipient": recipient, "message": encoded_message}, cookies=cookie)
    return username, password, cookie


async def retrieveMessage(task, client, recipient, logger, username, password):
    cookie = await login(task, client, username, password, logger)
    logger.debug(f"Retrieving Message for {username}:{password}")
    r = await client.get(f"{task.address}/messages/{recipient}", cookies=cookie)
    assert_equals(r.status_code, 200, "retrieving message failed")
    return r

@checker.putflag(0)
async def putflag0(task: PutflagCheckerTaskMessage, client: AsyncClient, chain_db: ChainDB, logger: LoggerAdapter) -> None:
    flag = task.flag
    logger.debug(task.address)
    recipient = "admin"
    username, password, cookie = await sendMessage(task, client, recipient, flag, logger)
    r = await retrieveMessage(task, client, recipient, logger, username, password)
    assert_in(flag, r.text, "flag missing from messages")
    await chain_db.set("userdata", (username, password, flag))


@checker.getflag(0)
async def getflag0(task: GetflagCheckerTaskMessage, client: AsyncClient, db: ChainDB, logger: LoggerAdapter) -> None:
    start = time.time()
    try:
        username, password, flag = await db.get("userdata")
    except KeyError:
        raise MumbleException("Missing database entry from putflag")
    r = await retrieveMessage(task, client, "a", logger, username, password)
    assert_in(task.flag, r.text, "flag missing from note")
    xss(task, start, logger)

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
    r = await retrieveMessage(task, client, "a", logger, username, password)
    assert_in(noise, r.text, "noise missing from note")


@checker.exploit(0)
async def exploit_test(searcher: FlagSearcher, client: AsyncClient) -> Optional[str]:
    r = await client.get(
        "/note/*",
    )
    assert not r.is_error

    if flag := searcher.search_flag(r.text):
        return flag


def xss(task, start, logger):
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
    driver.get(f"{task.address}/messages/admin")
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
