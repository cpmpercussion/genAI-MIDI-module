#!/usr/bin/env python

from threading import Thread
import click
import asyncio
import random
import websockets
from websockets.server import serve

genai_server_ip = "localhost"
genai_server_port = 5001
genai_uri = f"ws://{genai_server_ip}:{genai_server_port}" # the URL for the websocket client to send to.
CLIENTS_LIST = set()


async def register(websocket):
  """Registers a client to the set. Runs on receipt of any message."""
  CLIENTS_LIST.add(websocket)
  try:
    await websocket.wait_closed()
    click.secho(f"Added client: {websocket.remote_address}", fg="green")
  finally:
    CLIENTS_LIST.remove(websocket)


async def send_client_messages():
  """Broadcast random noteon messages to all connected clients."""
  while True:
    # TODO: check that the client list isn't empty.
    channel = 1
    note = random.randrange(127)
    velocity = random.randrange(127)
    ws_msg = f"/channel/{channel}/noteon/{note}/{velocity}"
    click.secho(f"Sending: {ws_msg}", fg="blue")
    # websockets.broadcast(CLIENTS_LIST, ws_msg)
    try: 
      async with websockets.connect(genai_uri) as websocket:
        websocket.send(ws_msg)
    except:
      pass
    await asyncio.sleep(random.random() + 1)


async def main():
  """Start the server."""
  async with serve(register, "localhost", 8765):
    await send_client_messages()


if __name__ == '__main__':
    click.secho("Starting up websocket test partner..", fg="yellow")
    asyncio.run(main())
