import asyncio
import secrets
import string
from collections import defaultdict

from aiohttp import web, WSMessage
import re


PAT_CMD = re.compile(r'^\u200b(.*)$')

channels = defaultdict(set)
sockets = defaultdict(str)
binary = defaultdict(bool)


async def send_or_binary(socket: web.WebSocketResponse, msg: str):
    if socket.closed:
        return  # don't send to closed sockets, it will raise an exception
    if isinstance(msg, str):
        if binary[socket]:
            if isinstance(msg, str):
                await socket.send_bytes(msg.encode('utf-8'))
        else:
            await socket.send_str(msg)
    elif isinstance(msg, bytes):
        await socket.send_bytes(msg)


async def join_ch(socket: web.WebSocketResponse, ch: str):
    if socket not in channels[ch]:
        for ch2 in channels:
            channels[ch2].discard(socket)
        for sock in channels[ch]:
            await send_or_binary(sock, '\u200bJOIND')
        channels[ch].add(socket)
        sockets[socket] = ch
        await send_or_binary(socket, '\u200bJOIN ' + ch)  # zwsp is also used as a signal to the client that a message came from the proxy server
    else:
        await send_or_binary(socket, '\u200bERR 11 already in this channel')


async def leave_ch(socket: web.WebSocketResponse):
    for ch2 in channels:
        channels[ch2].discard(socket)
    if socket in sockets:
        for sock in channels[sockets[socket]]:
            try:
                await send_or_binary(sock, '\u200bLEFTD')
            except Exception:
                pass
        del sockets[socket]
    await send_or_binary(socket, '\u200bLEFT')


async def current(socket: web.WebSocketResponse):
    if socket in sockets:
        await send_or_binary(socket, '\u200bCURRENT ' + sockets[socket])
    else:
        await send_or_binary(socket, '\u200bERR 10 not in a channel')


async def randomize(socket: web.WebSocketResponse):
    await leave_ch(socket)
    randomized = ''
    for _ in range(16):
        randomized += secrets.choice(string.ascii_lowercase + string.ascii_uppercase + string.digits)
    await join_ch(socket, randomized)
    await send_or_binary(socket, '\u200bRANDOMIZED ' + randomized)


async def pass_(*_):
    pass


async def binary_on(socket: web.WebSocketResponse):
    binary[socket] = True
    await send_or_binary(socket, '\u200bBINARY ON')


COMMANDS = {
    re.compile(r'join ([a-zA-Z_\-0-9]{1,32})'): join_ch,  # <control>join <channel>
    re.compile(r'leave'): leave_ch,  # <control>leave <channel>
    re.compile(r'where'): current,  # <control>where
    re.compile(r'random'): randomize,  # <control>random
    re.compile(r'pass'): pass_,  # <control>pass <anything...> -> do nothing
    re.compile(r'binary on'): binary_on,  # <control>binary -> enable binary mode
}

routing = web.RouteTableDef()


async def handleCommand(socket: web.WebSocketResponse, command: str):
    for pat, handler in COMMANDS.items():
        m = re.match(pat, command)
        if m:
            await handler(socket, *m.groups())
            break
    else:
        print('unknown command:', command)
        await send_or_binary(socket, '\u200bERR 19 unknown command')


@routing.get('/')
async def websocket(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    print('new connection')

    try:
        async for msg in ws:
            msg: WSMessage
            if msg.type in [web.WSMsgType.BINARY, web.WSMsgType.TEXT]:
                if msg.type == web.WSMsgType.BINARY:
                    data_decode = msg.data.decode('utf-8')
                else:
                    data_decode = msg.data
                matcher = PAT_CMD.match(data_decode)
                if matcher:
                    await handleCommand(ws, matcher.group(1))
                else:
                    if ws in sockets:
                        print(f'forwarding to {len(channels[sockets[ws]])} sockets')
                        for socket in channels[sockets[ws]]:
                            socket: web.WebSocketResponse
                            if socket != ws:
                                await send_or_binary(socket, msg.data)
                    else:
                        await send_or_binary(ws, '\u200bERR 10 not in a channel')
            elif msg.type == web.WSMsgType.ERROR:
                print('ws connection closed with exception %s' %
                      ws.exception())

    finally:
        if ws in sockets:
            for sock in channels[sockets[ws]].copy():
                if sock == ws:
                    channels[sockets[ws]].discard(sock)
                await send_or_binary(sock, '\u200bLEFTD')
            del sockets[ws]
        print('websocket connection closed')
        return ws

app = web.Application()
app.add_routes(routing)
web.run_app(app, port=8765)
