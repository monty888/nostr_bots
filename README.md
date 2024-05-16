# about
Some simple bots for nostr in python.

# install

```sh
git clone https://github.com/monty888/bots.git  
cd bots  
python3 -m venv venv   
source venv/bin/activate      
pip install .
```

# echo bot
Replies with the same text that it receives.

```sh
python run_echo_bot.py
```

# ip bot
Replies with the external ip of where the ip is running.

```sh
python run_ip_bot.py
```

# bitcoin bot
Executes commands against a local bitcoin node and sends the replies over nostr.
```sh
python run_ip_bot.py
```

# todo

- [ ] relay needs to be parsed from command line at least plus other options
- [ ] min basic commands for the bitcoin bot + simple web interface?
