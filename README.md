# Coding Challenge

The assignment:

>Developers have been reporting flapping ports on various services in a cluster that you manage. Sometimes they see their services as up, and sometimes they’re down, with no clear reason as to why. They’ve asked you to diagnose the issue and given you a list of hosts to check. You’ve already vetted the network and don’t think it’s at fault.
>
>Write a script, in the language of your choice, that will take a list of hosts on STDIN, one per line, and a TCP port number as a command-line parameter. Your script will need to work for 100/1000/10000 hosts across multiple data centers and subnets.
>
>Your program should report on:
> * Hosts where the TCP port is up one minute and down another
> * Hosts that are down. A host is considered ‘down’ if it will not accept a TCP connection 5 times in a row
>
> Given the output of this script
> * How would you deploy this as a script/service/etc?
> * How would you work with developers to resolve any systems issues?
> * What, if any, would the impact be of your script on the production service?
> 
> Example call of this script:
>
>     $ python flappy-ports.py 8080 <<EOF
>     127.23.12.67
>     sync-124.nylas.net
>     sync-166.nylas.net
>     sync-224.nylas.net
>     EOF
>     127.23.12.67 is down
>     sync-124.nylas.net is flappy
>     sync-166.nylas.net is flappy
>     sync-224.nylas.net is reporting ok
> 
> Notes:
> * you can use the language of your choice for this problem
> * you can assume that the code is going to run in a Linux environment
> * it is up to you to judge the frequency window of how often ports should be checked
> * try not to spend more than a couple hours on this problem
> * again, don’t hesitate to let me know if you have any questions!

## My Solution

I'm using Python's `asyncio.open_connection` from 3.6 in order to have some sort of 
concurrency (but the script is doing host name resolution synchronously upfront so it
may take a while to start). I'm also using RRD to record ping results. If you omit the
`--input_file` argument it will read from standard input.

    $ python3 pingport.py --help
    
    usage: pingport.py [-h] --port PORT [--rrd RRD] [--interval INTERVAL]
                       [--timeout TIMEOUT] [--input_file INPUT_FILE] [--verbose]

    optional arguments:
      -h, --help            show this help message and exit
      --port PORT           TCP port
      --rrd RRD             RRD Database path, default ./rrd
      --interval INTERVAL   Ping interval (default 600)
      --timeout TIMEOUT     Timeout in seconds (default 300)
      --input_file INPUT_FILE
                            Input file, default stdin
      --verbose             Show progress messages
      
Example:

    $ python3 pingport.py --input_file=sample-data/random-1000-ips.txt --port 80 --verbose

Example output with `--verbose`:

    ...
    Ping 169.255.59.7:80 OK...
    Ping 183.81.166.108:80 OK...
    Ping 103.246.18.68:80 OK...
    Ping 199.59.242.151:80 OK...
    Ping 67.227.226.240:80 OK...
    Ping 114.200.196.96:80 OK...
    Ping 216.218.248.148:80 failed... (TimeoutError: '')
    Ping 110.45.157.131:80 failed... (TimeoutError: '')
    110.45.157.131:80 is flappy
    Ping 123.30.191.33:80 failed... (TimeoutError: '')
    Ping 187.4.152.44:80 failed... (TimeoutError: '')
    187.4.152.44:80 is down
    Ping 202.30.244.19:80 failed... (TimeoutError: '')
    Ping 187.29.147.44:80 failed... (TimeoutError: '')
    ...
  
Example output without `--verbose` (on stderr):

    ...
    110.45.157.131:80 is flappy
    187.4.152.44:80 is down
    ...

You may have to adjust `--interval` and `--timeout` according to your network speed and
the size of your host list - the defaults are pretty conservative with 5 minutes between
pings and 30 second timeouts. The sample domain names and ips in the `sample-data` folder
are taken from the [citzenlab/test-list](https://github.com/citizenlab/test-lists) repo.

## Install

This was tested in a Macbook using Python 3.6. You need rrdtool, Python headers and a 
working C compiler.
 
If you are using a Mac, do:

    $ brew install rrdtool
    
On Debian/Ubuntu do:

    $ sudo apt-get install librrd-dev libpython3-dev
    
On RHEL/CentOS:

    $ sudo yum install rrdtool-devel python34-devel
    
Clone this repo:

    $ git clone https://github.com/scardine/pingport.git
    $ cd pingport

After installing the dependencies you can fire `pip` (you probably want to create a [virtual
environment](https://docs.python.org/3/library/venv.html) but will not cover this step here):

    pip install --user -r requirements.txt
    
    
    
## Why Python

Well, Python is likely to be present on any Linux machine so it is a great tool for fast 
prototyping and making ad hoc scripts. Before Python, Perl used to be the swiss army knife of
choice for the network administrator - but Python is an order of magnitude easier to 
maintain (I kid you not, sometimes I had trouble understanding my own scripts a couple 
weeks after I wrote them).
   
## Why RRD?

I like to log results but don't like to deal with log rotation; for network monitoring
RRD databases fit the bill as they have deterministic size. Also, you can easily 
create nice charts from them later.

## The questions

1) **How would you deploy this as a script/service/etc?**  
Honestly, I would rather use a proper NMS for this (there are some F/OSS options). If I had to
distribute a Python application for Linux I would probably create deb and rpm packages.

2) **How would you work with developers to resolve any systems issues?**  
I depends. If this is disaster recover I would apply my 3D: **D**efuse (get the service back as
fast as possible), **D**ebrief (make a blameless postmortem to identify root causes), **D**efend (make
arrangements to avoid the problem in the future).
If it is one of that pesky intermittent bugs we are absolutely unable to reproduce on the staging 
environment I would help them diagnose the issue in production (and if they are not using a log
aggregator I would install a [sentry](https://sentry.io) instance for them).

3) **What, if any, would the impact be of your script on the production service?**  
If the ping interval is kept above 1 minute I don't think there will be any meaningful impact - maybe
an extra thousand entries / day in the logs but any application worth its salary should be able 
to handle that.
