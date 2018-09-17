#!/usr/bin/env python3
import argparse
import asyncio
import os
import re
import socket

import async_timeout
import rrdtool
import sys

DEFAULT_TIMEOUT = 30
DEFAULT_INTERVAL = 300  # 5 minutes
RRD_FNAME_CACHE = {}
IP_CACHE = {}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", help="TCP port", type=int, required=True)
    parser.add_argument("--rrd", help="RRD Database path, default ./rrd", type=str, default="rrd")
    parser.add_argument(
        "--interval",
        help=f"Ping interval (default {DEFAULT_INTERVAL})",
        type=int,
        default=DEFAULT_INTERVAL
    )
    parser.add_argument(
        "--timeout",
        help=f"Timeout in seconds (default {DEFAULT_TIMEOUT})",
        type=int,
        default=DEFAULT_TIMEOUT
    )
    parser.add_argument("--input_file", help="Input file, default stdin", default='-')
    parser.add_argument("--verbose", help="Show progress messages", action='store_true')
    return parser.parse_args()


def host2filename(argv, host):
    global RRD_FNAME_CACHE

    if host in RRD_FNAME_CACHE:
        return RRD_FNAME_CACHE[host]
    parts = re.split(r"\W", IP_CACHE[host])
    parts[-1] +=  ".rrd"
    if not os.path.isdir(os.path.join(argv.rrd, *parts[:-1])):
        os.makedirs(os.path.join(argv.rrd, *parts[:-1]), exist_ok=True)
    rrd = os.path.join(argv.rrd, *parts)
    RRD_FNAME_CACHE[host] = rrd
    return rrd


def main():
    argv = parse_args()
    if argv.input_file == '-':
        hosts = [line.strip() for line in sys.stdin if line]
    else:
        with open(argv.input_file) as input_file:
            hosts = [line.strip() for line in input_file if line]

    if argv.verbose:
        print(f"Resolving {len(hosts)} names...")

    global IP_CACHE
    for i, host in enumerate(hosts):
        try:
            IP_CACHE[host] = socket.gethostbyname(host)
        except socket.gaierror:
            sys.stderr.write(f"Unable to resolve {host}, skipping...\n")
        if argv.verbose and i and i % 10 == 0:
            sys.stdout.write('.')
            sys.stdout.flush()
    else:
        if argv.verbose:
            print(" OK!")

    os.makedirs("rrd", exist_ok=True)
    for host in hosts:
        if host not in IP_CACHE:
            continue
        rrdtool.create(
            host2filename(argv, host),
            "--step", str(argv.interval),
            "--start", "0",
            f"DS:connect:GAUGE:{int(argv.interval + argv.timeout)}:0:U",
            f"DS:time:GAUGE:{int(argv.interval + argv.timeout)}:0:U",
            f"RRA:AVERAGE:0.5:1:1d",
            f"RRA:AVERAGE:0.5:5:5d",
            f"RRA:AVERAGE:0.5:60:120",
            f"RRA:AVERAGE:0.5:420:840",
        )
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run(argv, hosts, loop))


async def pingport(loop: asyncio.AbstractEventLoop, host: str, interval: int, argv):
    started = loop.time()
    elapsed = connected = 0
    if host != IP_CACHE[host]:
        hostname = f"{host}:{argv.port} ({IP_CACHE[host]})"
    else:
        hostname = f"{host}:{argv.port}"

    with async_timeout.timeout(argv.timeout + 1):
        try:
            conn = asyncio.open_connection(IP_CACHE[host], argv.port, loop=loop)
            reader, writer = await asyncio.wait_for(conn, timeout=argv.timeout)
        except KeyboardInterrupt:
            print("Ok, boss, lets call it a day.")
            sys.exit(0)
        except Exception as e:
            if argv.verbose:
                print(f"Ping {hostname} failed... ({e.__class__.__name__}: {str(e)!r})")
        else:
            if argv.verbose:
                print(f"Ping {hostname} OK...")
            conn.close()
            connected = argv.timeout
            elapsed = loop.time() - started

    db = host2filename(argv, host)
    # Check previous pings
    if not connected:
        last_update = rrdtool.lastupdate(db)
        if 'ds' in last_update and last_update['ds']['connect']:
            sys.stderr.write(f"{hostname} is flappy\n")
        else:
            last = rrdtool.fetch(db, "MIN", "--start", str(-argv.interval * 6))
            last_connections = [int(c) for c, t in last[2] if c is not None][-5:]
            if len(last_connections) == 5 and not any(last_connections):
                sys.stderr.write(f"{hostname} is down\n")

    # Record this attempt
    rrdtool.update(db, f"N:{int(connected)}:{elapsed}",)
    return await asyncio.sleep(interval)


async def run(argv, hosts, loop: asyncio.AbstractEventLoop):
    started = loop.time()
    drift = i = 0
    while True:
        i += 1
        interval = argv.interval - drift
        tasks = [pingport(loop, host, interval, argv) for host in hosts if host in IP_CACHE]
        await asyncio.gather(*tasks)
        drift = loop.time() - i * argv.interval - started


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)