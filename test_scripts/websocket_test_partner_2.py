#!/usr/bin/env python
"""
Testing partner script: connects via websocket to the genai_midi_module, sends periodic messages and receives whatever is sent back.
"""

import click
import asyncio
import random
import websockets

genai_server_ip = "localhost"
genai_server_port = 5001
genai_uri = f"ws://{genai_server_ip}:{genai_server_port}" # the URL for the websocket client to send to/receive from.

async def send_client_messages(websocket):
  """Broadcast random noteon messages to all connected clients."""
  while True:
    channel = 11
    note = random.randrange(8) + 1
    velocity = random.randrange(127)
    # ws_msg = f"/channel/{channel}/noteon/{note}/{velocity}"
    ws_msg = f"/channel/{channel}/cc/{note}/{velocity}"
    click.secho(f"Sending: {ws_msg}", fg="blue")
    await websocket.send(ws_msg)
    await asyncio.sleep(random.random() + 1)


async def receive_client_messages(websocket):
  async for msg in websocket:
    click.secho(f"Received: {msg}", fg="yellow")


async def main():
  """Connect to the genAI_midi_module, send and receive messages."""
  async for websocket in websockets.connect(genai_uri):
    try:
        await asyncio.gather(send_client_messages(websocket), receive_client_messages(websocket))
    except websockets.ConnectionClosed:
        click.secho(f"Connection closed to {genai_uri}, will try to reconnect.", fg="red")
        continue
  # async with websockets.connect(genai_uri) as websocket:



if __name__ == '__main__':
    click.secho("Starting up websocket test partner..", fg="yellow")
    asyncio.run(main())
    print("closing")
