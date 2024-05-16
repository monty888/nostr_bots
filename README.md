# about
Some simple bots for nostr in python.

# install

from github
```sh
git clone https://github.com/monty888/nostr_bots.git  
cd nostr_bots  
python3 -m venv venv   
source venv/bin/activate      
pip install .
```

using pip
```sh
pip install nostr_bots
```

> [!Note]  
Won't work with current pip of monstr get current version from https://github.com/monty888/monstr
until updated    

> [!Note]
when install via pip to run use python -m nostr_bots.__name__ e.g python -m nostr_bots.run_echo_bot 


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

- [ ] get the inbox code working
- [ ] add support for nip44 encryption and not just nip4
- [ ] relay needs to be parsed from command line at least plus other options
- [ ] min basic commands for the bitcoin bot + simple web interface?
