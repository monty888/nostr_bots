let bot_helper = function(){
	let ticks = function(){
		return (Math.floor((new Date().getTime()/1000)));
	},
	get_bot = function(bot_pk, user_pub_k, pool, args){
	    args = args || {};
        let _bot_pk = bot_pk,
            _user_pub_k = user_pub_k,
            _pool = pool,
            _call_map = {},
            _use_kind = args['use_kind'] || 20888,
            _encrypt = args['encrypt'] || true;

        _pool.on('open', relay => {
            relay.subscribe("subid", {limit: 0, kinds:[_use_kind], authors: [_bot_pk]})
        });

        _pool.on('event', (relay, sub_id, evt) => {
            let tags = evt.tags,
                c_tag,
                link = null;

            for(var i=0;i<tags.length;i++){
                c_tag = tags[i];
                if(c_tag.length>1){
                    if((c_tag[0] === 'e')){
                        link = c_tag[1];
                        break;
                    }
                }
            }
            if(link!==null && link in _call_map){
                // if needed we'll decrypt the content before passing it on
                if(_encrypt){
                    window.nostr.nip04.decryptDm(evt).then((content) => {
                        evt['content'] = content;
                        _call_map[link]['complete'] && _call_map[link]['complete'](evt);
                    });
                }else{
                    _call_map[link]['complete'] && _call_map[link]['complete'](evt);
                }

            }

        });

        async function _make_event(content){
            // should be encrypted and probably wrapped
            if(_encrypt){
                content = await window.nostr.nip04.encrypt(_bot_pk, content);
            }

        	return {
                'pubkey': _user_pub_k,
                'created_at': ticks(),
                'kind': _use_kind,
                'tags': [[
                    'p', _bot_pk
                ]],
                'content': content
            }
        }

        async function _sign_event(evt){
            evt['id'] = await NOSTR.calculateId(evt);
            return await nostr.signEvent(evt);
        }


        function test(){
            alert('hello - '+_bot_pk)
        }

        function get_new_address(callback){
            _make_event('getnewaddress').then( (evt) => {
                _sign_event(evt).then((evt) => {
                    _call_map[evt.id] = {
                        'complete': function(evt){
                            try{
                                let parsed = JSON.parse(evt.content);
                                callback(parsed.result);
                            }catch(e){
                                console.log(e);
                            }

                        }
                    };
                    _pool.send(['EVENT',evt]);
                });
            });
        };

        function listtransactions(callback){
            _make_event('listtransactions').then( (evt) => {
                _sign_event(evt).then((evt) => {
                    _call_map[evt.id] = {
                        'complete': function(evt){
                            try{
                                let parsed = JSON.parse(evt.content);
                                callback(parsed.result);
                            }catch(e){
                                console.log(e);
                            }

                        }
                    };
                    _pool.send(['EVENT',evt]);
                });
            });
        };


        return {
            test: test,
            get_new_address: get_new_address,
            listtransactions: listtransactions
        }

	};

	return  {
		get_bot : get_bot

	};
}();

/*
    check if we have signing extension, if not set up a backup env that should look similar
    with a fullback privkey - currently passed in
    returns true/false if nip07 was found, maybe you only want to continue wuth ext

*/
function nip07setup(fullback_priv_k){
    let _has_nip07 = false,
        _fullback_priv_k = fullback_priv_k,
        // nos2x doesn't like running as file (no domain) - but if running locally you might try with a fullback privk
        _fullback = location.protocol==='file:';

    if(!window.nostr||_fullback){
        window.nostr = window.nostr || {};

        window.nostr.getPublicKey = async function(){
            return await NOSTR.getPublicKey(_fullback_priv_k);
        };
        window.nostr.signEvent = async function(evt){
            evt['sig'] = await NOSTR.signId(_fullback_priv_k, evt['id']);
            return evt;
        };
        // NOTE this func isn't required to exist as part of nip7,
        // hopefully it does when using nip7 else we can't encrypt the
        // messages as we don't have access to the priv_k
        // TODO: add some err code for this case just incase there are impls that don't...
        window.nostr.nip04.encrypt = async function(pubkey, plaintext){
            return NOSTR.encryptDM(_fullback_priv_k, pubkey, plaintext);
        };
        //
        window.nostr.nip04.decryptDm = async function(event){
            return await NOSTR.decryptDm(_fullback_priv_k, event);
        }

    }else{
        _has_nip07 = true;
        // so we can use the same method call and because the decryptDM isnt
        // easy to make compat with NIP07 nip04.decrypt
        //
        window.nostr.nip04.decryptDm = async function(event){

            // make tag methods common
            let tags = event.tags,
                c_tag,
                link = null;

            for(var i=0;i<tags.length;i++){
                c_tag = tags[i];
                if(c_tag.length>1){
                    if((c_tag[0] === 'p')){
                        link = c_tag[1];
                        break;
                    }
                }
            }

            return await window.nostr.nip04.decrypt(link , event.content);
        }
    }

    return _has_nip07;
}


// main code
function new_address(){

    setTimeout(function(){
        // this should be randomly generated and will only work where any pub_k is accepted
        const _fullback_priv_k = '11e1827635450ebb3c5a7d12c1f8e7b2b514439ac10a67eef3d9fd9c5c68e245',
        // connect to
            _relays = ['wss://localhost:8081'],
//            _relays = [' wss://nostr-pub.wellorder.net'],
        // actual con, repack and rename NOSTR to not confuse with nostr ext?!
            _pool = NOSTR.RelayPool(_relays),
            _bot_pk = '0345e50ed1e1ca36451c059288f3514769861fed4f3a7d3b00089cf222079566',
        // qr drawn here once we have address
            _qr_con = document.getElementById('address-qr');
        // and add as text
            _text_con = document.getElementById('address-text'),
        // sets up nip07 funcs that we need, nip07 is only true if the ext exists
        // so maybe you decide not to continue anyhow if not?
            _nip07 = nip07setup(_fullback_priv_k);
        // methods for talking to bitcoind bot via nostr
            let _my_bot;

        try{
            window.nostr.getPublicKey().then( (user_pub_k)=> {
            _my_bot = bot_helper.get_bot(_bot_pk, user_pub_k, _pool);
            _my_bot.get_new_address((address) =>{
                _text_con.textContent = address;
                new QRCode(_qr_con, address);
            });

            });
        }catch(e){
            alert('nip7 ext is required!!!...')
        }

	},1);


};

// main code
function list_transactions(){

    setTimeout(function(){
        // this should be randomly generated and will only work where any pub_k is accepted
        const _fullback_priv_k = '11e1827635450ebb3c5a7d12c1f8e7b2b514439ac10a67eef3d9fd9c5c68e245',
        // connect to
            _relays = ['wss://localhost:8081'],
//            _relays = [' wss://nostr-pub.wellorder.net'],
        // actual con, repack and rename NOSTR to not confuse with nostr ext?!
            _pool = NOSTR.RelayPool(_relays),
            _bot_pk = '0345e50ed1e1ca36451c059288f3514769861fed4f3a7d3b00089cf222079566',
        // whre we're going to list
            _list_con = document.getElementById('transactions_con');
        // sets up nip07 funcs that we need, nip07 is only true if the ext exists
        // so maybe you decide not to continue anyhow if not?
            _nip07 = nip07setup(_fullback_priv_k);
        // methods for talking to bitcoind bot via nostr
            let _my_bot;

        try{
            window.nostr.getPublicKey().then( (user_pub_k)=> {
            _my_bot = bot_helper.get_bot(_bot_pk, user_pub_k, _pool);
            _my_bot.listtransactions((txs) =>{
                _list_con.textContent = JSON.stringify(txs);
            });

            });
        }catch(e){
            alert('nip7 ext is required!!!...')
        }

	},1);


};