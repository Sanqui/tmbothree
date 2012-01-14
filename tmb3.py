import socket
import struct
import hashlib
import time
import zlib
import random
import urllib.request
import os.path
import threading
import re

# Setting up logs.
import logging
log = logging.getLogger()
log.setLevel(logging.INFO)

#fh = logging.FileHandler("log.txt")
sh = logging.StreamHandler()

formatter = logging.Formatter('[%(asctime)s] %(levelname)s: {%(funcName)s} %(message)s')
#fh.setFormatter(formatter)
sh.setFormatter(formatter)
#log.addHandler(fh)
log.addHandler(sh)

# I don't think this has ever worked.
def upload_avatar(filename, verification):
    log.info("Uploading avatar {}...".format(filename))
    conn = http.client.HTTPConnection("avatar.transformice.com")
    with open(filename, "rb") as f:
        d = f.read()
        data = b"""------------------------------712d3eb50c2d
Content-Disposition: form-data; name="Filename"

"""+filename.encode('utf-8')+b"""

------------------------------712d3eb50c2d
Content-Disposition: form-data; name="Filedata"; filename=\""""+filename.encode('utf-8')+b"""\"
Content-Type: application/octet-stream
"""+d+b"""
------------------------------712d3eb50c2d
Content-Disposition: form-data; name="Upload"


Submit Query
------------------------------712d3eb50c2d--"""
    headers = {"Host": "avatar.transformice.com",
    "User-Agent": "Shockwave Flash",
    "Accept": "Text/*",
    "Content-Length": str(len(data)),
    "Content-Type": "Content-Type: multipart/form-data; boundary=----------------------------712d3eb50c2d"}
    
    url = "/i.php?n={}".format(verification)
    
    try:
        conn.request('POST', url, data, headers)
        r = conn.getresponse()
        log.info("Uploaded avatar: {}".format(r.read()))
    except Exception as ex:
        log.error("Upload failed: ".format(ex))     

# This looks a bit ugly, but does its job.
packets = open('packets.csv', 'r')
cur = ''
P  = {}
PN = {}
PF = {}
for line in packets.readlines():
    line = tuple(line.rstrip('\n').split(';'))
    if len(line)==1:
        cur = line[0]
    elif cur == 'new':
        c, cc, name, inf, outf = line
        c, cc = int(c), int(cc)
        P[name] = (c, cc, cur)
        PN[(c, cc, cur)] = name
        PF[(c, cc, cur)] = (inf, outf)
    elif cur == 'old':
        c, cc, name = line
        c, cc = int(c), int(cc)
        P[name] = (c, cc, cur)
        PN[(c, cc, cur)] = name

#version = 0x13 #0xad
log.info("{} packets known.".format(len(P)))
#log.info("Protocol version {}.".format(version))

class PingThread(threading.Thread):
    def __init__ (self, callback, time=10):
        threading.Thread.__init__(self)
        self.callback = callback
        self.enabled = True
        self.time = 10
    def run(self):
        time.sleep(self.time)
        if self.enabled: self.callback()
        
class RepeatedPingThread(threading.Thread):
    def __init__ (self, callback, times=15):
        threading.Thread.__init__(self)
        self.callback = callback
        self.times = times
        self.enabled = True
        self.run_ = True
    def run(self):
        while True:
            time.sleep(self.times)
            if not self.run_:
                return
            if self.enabled:
                self.callback()

class DeadSocket(threading.Thread):
    def __init__(self, parent):
        threading.Thread.__init__(self)
        self.parent = parent
    
    def step(self):
        pass
    def reconnect(self):
        pass
    def disconnect(self):
        pass
    def run(self):
        pass

class TransformiceSocket(threading.Thread): 
    def __init__(self, parent, server="46.105.104.210",  username="", password=""): #46.105.102.209
        threading.Thread.__init__(self)
        self.parent = parent
        
        self.username = username
        self.password = password
        
        self.server = server
        self.port = 44444
        self.conn = socket.socket()

        self.CMDTEC = 0
        self.MDT = [0]*10
        
        self.packet_len = None
        self.packet = b""
        
        self.ping = PingThread(self.send_ping)
        self.dummy = RepeatedPingThread(self.send_dummy)
        self.dummy.enabled = False
        self.dummy.start()
        
        self.positionnum = 0
        
        self.round_num = 0
        
        self._end = False 
        
    def connect(self):
        log.info("Connecting.")
        #self.dummy.enabled = False
        self.ping.enabled = False
        while True:
            try:
                self.conn = socket.socket()
                self.conn.connect((self.server,self.port))
            except socket.error:
                log.error("Can't connect, retrying..")
                time.sleep(11.25)
            else:
                break
    
    def connect_main(self):
        self.server_type = 0
        self.parent.server_room = DeadSocket(self.parent)
        self.connect()
        with open("/home/http/kikoo.formice.com/data.txt", 'r') as data:
            ts, version, key = tuple(data.readlines()[0].replace("\n", '').split(" "))
        log.info("Protocol version {}, key {} (reterived {} secs ago)".format(int(version), key, time.time()-float(ts)))
        self.send_packet(P['VERSION'], int(version), key, 0x17ed)
        #self.dummy = RepeatedPingThread(self.send_dummy)
        self.dummy.enabled = True
        #self.dummy.start()
        
    def connect_room(self, code):
        self.server_type = 1
        self.connect()
        self.send_packet(P['BULLE'], code)
        #self.dummy = RepeatedPingThread(self.send_dummy)
        #self.dummy.start()
        self.dummy.enabled = True
        time.sleep(0.5)
        self.start()

    def reconnect(self):
        self.ping.enabled = False
        self.dummy.enabled = False
        time.sleep(4)
        if self.server_type == 0: 
            log.error(" [{}] Disconnected; reconnecting..".format(self.server_type))
            self.connect_main()
        elif self.server_type==1:
            #self.connect_room()
            log.error(" [{}] Disconnected.  I'll tell main to rejoin room".format(self.server_type))
            
            self.disconnect()
            self.parent.change_room(self.parent.room)
            #self.parent.server_room = DeadSocket(self)
    
    def disconnect(self):
        self.ping.enabled = False
        self.dummy.run_ = False
        self.conn.close()
        self._end = True
    
    def send_packet(self, ccc, *args):
        log.debug (" [{}]>>> {}: {}".format(self.server_type, PN[ccc], args))
        if ccc in PF:
            packet = struct.pack(">BB", *ccc[0:2])
            format = PF[ccc][1]
            assert len(format) == len(args)
            if format == '*':
                packet += args[0]
            else:
                for char, arg in zip(format, args):
                    if char == 'S':
                        arg = arg.encode('utf-8', 'replace')
                        packet += struct.pack(">H", len(arg))+arg
                    else:
                        packet += struct.pack(">"+char, arg)
        else:
            if len(args) > 0:
                args = b"\x01"+b"\x01".join(str(arg).encode('utf-8', 'replace') for arg in args)
            else:
                args = b""
            packet = struct.pack(">BBHBB", 1, 1, len(args)+2, *ccc[0:2])+args
        self.send(packet)

    def begin_fingerprint(self, pMDT, CMDTEC):
        MDT = list((int(num) if num != "0" else 10) for num in pMDT)
        self.CMDTEC = int(CMDTEC)
        self.MDT = MDT
        log.debug("MDT {}, CMDTEC {}".format(MDT, CMDTEC))

    def generate_fingerprint(self):
        loc3 = self.CMDTEC % 9000 + 1000
        fingerprint = b""
        fingerprint += struct.pack(">B", self.MDT[int(loc3 / 1000)])
        fingerprint += struct.pack(">B", self.MDT[int(loc3 / 100) % 10])
        fingerprint += struct.pack(">B", self.MDT[int(loc3 / 10) % 10])
        fingerprint += struct.pack(">B", self.MDT[loc3 % 10])
        self.CMDTEC += 1
        return fingerprint

    def send(self, packet):
        packet = struct.pack(">I", len(packet)+8)+self.generate_fingerprint()+packet
        try:
            self.conn.send(packet)
            log.debug(packet)
        except socket.error:
            self.reconnect()

    def recv(self):
        if self.packet_len is None:
            try:
                packet_len = self.conn.recv(4)
            except socket.error:
                return
            else:
                if packet_len == b"":
                    self.reconnect()
                else:
                    self.packet_len = struct.unpack(">I", packet_len)[0]-4
        else:
            try:
                add = self.conn.recv(self.packet_len-len(self.packet))
                self.packet += add
            except socket.error: return
            else:
                if add == b"":
                    self.reconnect()
                elif len(self.packet)<self.packet_len:
                    return
                else:
                    #print(self.packet_len)
                    #print(len(packet))
                    self.packet_len = None
                    self.parse_packet(self.packet)
                    self.packet = b""
        
    def parse_packet(self, packet):
        try:
            ccc = list(struct.unpack(">BB", packet[0:2]))
            ccc.append('new')
            ccc = tuple(ccc)
            packet = packet[2:]
            if ccc == P['OLD_PROTOCOL']:
                len_args, c, cc = struct.unpack(">HBB", packet[:4])
                #args = list(tuple(subarg.decode('utf-8')) for subarg in (arg.split('\x02') for arg in (packet[5:].rstrip(b'\x00').split(b'\x01'))))
                args = list(arg.decode('utf-8') for arg in (packet[5:].rstrip(b'\x00').split(b'\x01')))
                ccc = (c, cc, 'old')
                if ccc in PN:
                    name = PN[ccc]
                else:
                    name = str(ccc)
            else:
                if ccc in PF:
                    format = PF[ccc][0]
                    offset = 0
                    args = []
                    name = PN[ccc]
                    if format == '*':
                        args = [packet]
                    else:
                        for char in format:
                            if char == 'S':
                                slen, = struct.unpack(">H", packet[offset:offset+2])
                                args.append(packet[offset+2:offset+2+slen].decode('utf-8').replace("&lt;", "<"))
                                clen = 2+slen
                            else:
                                clen = struct.calcsize(">"+char)
                                args.append(struct.unpack(">"+char, packet[offset:offset+clen])[0])
                            offset += clen
                else:
                    args = [packet]
                    name = str(ccc)
            args = tuple(args)
            logmsg = " [{}]<<< {}: {}".format(self.server_type, name, args)
        except Exception as ex:
            emsg = "Failed at parsing packet: [{}]<<< {}: {}".format(self.server_type, ccc, packet)
            log.error(emsg)
            self.parent.send_tribe_message("[ERROR] "+emsg)
            raise
        else:
            if ccc in PF or ccc in PN:
                log.debug (logmsg)
            else:
                log.warn (logmsg)
        
            if ccc == P['FINGERPRINT']:
                self.begin_fingerprint(args[1], args[2])
            #elif ccc == P['AFTERLOGIN']:
                '''flash, = args
                header = flash[:8]
                flash = zlib.decompress(flash[8:])
                verify = []
                for byte in flash[0x24f:0x254]:
                    assert byte < 0x10
                    verify.append(byte+1)
                
                print(flash, verify)'''
                
                self.send_packet(P['COMMUNITY'], self.parent.community)
                self.send_packet(P['CLIENT_INFO'], 'en', 'Linux 2.6.35-29-generic-pae', 'LNX 10,2,159,1')#'tmb3.py', 'n/a')
                #self.send_packet(P['VERIFY'], *verify)
                #self.send_packet(P['LOG_IN'], 'Thisisatest', '', 1)
                self.send_packet(P['LOG_IN'], self.parent.username, self.parent.password, 'fdsafdsa fdsafdas fsafdsa')
                #self.dummy.start()
            elif ccc == P['PING']:
                #self.ping_t = time.time()+10
                self.ping.enabled = False
                self.ping = PingThread(self.send_ping)
                self.ping.start()
            elif ccc == P['LOGGED_IN']:
                log.info("Logged in.")
                self.parent.on_login()
            elif ccc == P['BULLE']:
                code, ip = args
                #if self.ranom_roomed == False:
                #    self.random_roomed = True
                #else:
                log.info("{} change room server: {}".format("Going to" if self.parent.follow_BULLE else "Got asked to", ip))
                if self.parent.follow_BULLE == True:
                    self.parent.server_room.disconnect()
                    self.parent.server_room = TransformiceSocket(self.parent, ip)
                    self.parent.server_room.connect_room(code)
            elif ccc == P['ROOM_NAME']:
                self.parent.room, = args
                self.parent.on_room_change()
            elif ccc == P['TRIBE_MESSAGE']:
                message, name = args
                self.parent.on_tribe_message(name, message)
            elif ccc == P['TRIBE_ACTION']:
                if len(args) == 2:
                    action, name = args
                else:
                    action, mode, name = args
                if action == "1": 
                    self.parent.on_tribe_connect(name)
                elif action == "2":
                    self.parent.on_tribe_disconnect(name)
                elif action == "6":
                    self.parent.on_tribe_join(mode)
                elif action == "11":
                    self.parent.on_tribe_leave(name)
                elif action == "12":
                    log.info("Rank change, forgot what means: {}".format(args))
                    self.parent.on_tribe_rank_change(mode, name) # actually name, mode
                elif action == "13":
                    if mode == "0":
                        self.parent.on_tribe_chat_disable(name)
                    elif mode == "1":
                        self.parent.on_tribe_chat_enable(name)
            elif ccc == P['MESSAGE']:
                mouse_id, name, message = args
                self.parent.on_room_message(name, message)
            elif ccc == P['PRIVATE_MESSAGE']:
                msgtype, name, community, message = args
                if msgtype == 1: self.parent.on_private_message(name, message)
            elif ccc == P['TRIBE_INFO']:
                tribe_id, tribe_name, byte, tribe_message, tribe_rights, tribe_stuff = args
                log.info("Tribe: {}".format(tribe_name))
                log.info("Tribe message: {}".format(tribe_message))
            elif ccc == P['FRIEND_ONLINE']:
                name, = args
                log.info("{} is now online.".format(name))
            elif ccc == P['FRIEND_LIST']:
                num, fields = args
            elif ccc == P['MUSIC']:
                url, = args
                log.info("Playing music: {}".format(args))
                self.parent.on_music(url)
            #elif ccc == P['POSITION']:
            #    self.positionnum, = args
            elif ccc == P['NEW_FINGERPRINT']:
                self.begin_fingerprint(*args)
            elif ccc == P['NEW_MAP']:
                if len(args) == 4:
                    atnum, unk1, round_num, unk2 = args
                    self.round_num = int(round_num)
                    self.parent.on_new_map(atnum)
                else:
                    atnum, unk1, round_num, unk2, xml = args
                    self.round_num = int(round_num)
                    self.parent.on_new_map(atnum, xml)
                
            elif ccc == P['MOVEMENT']:
                round_num, run, y, x, hfriction, vfriction, jump, casting, mouse_id = args
                self.parent.on_mouse_movement(*args)
            elif ccc == P['EMOTION']:
                mouse_id, emotion = args
                self.parent.on_mouse_emotion(int(mouse_id), int(emotion))
            elif ccc == P['CROUCH']:
                if len(args)==2:
                    mouse_id, crouching = args
                    crouching = True
                else: 
                    mouse_id, = args
                    crouching = False
                self.parent.on_mouse_crouch(int(mouse_id), crouching)
            elif ccc == P['ROOM_NEW_PLAYER']:
                name, mouse_id, unk1, unk2, unk3, unk4, unk5, unk6, unk7, unk8, unk9 = tuple(args[0].split("#"))
                self.parent.room_mice[name] = int(mouse_id)
            elif ccc == P['ROOM_PLAYERS']:
                self.parent.room_mice = {}
                for mouse in args:
                    name, mouse_id, unk1, unk2, unk3, unk4, unk5, unk6, unk7, unk8, unk9 = tuple(mouse.split("#"))
                    self.parent.room_mice[name] = int(mouse_id)
            elif ccc == P['ROOM_PLAYER_LEAVE']:
                mouse_id, name = args
                if name in self.parent.room_mice:
                    del self.parent.room_mice[name]
            elif ccc == P['GLOBAL']:
                byte, name, message = args
                log.info("[{}] [{}] {}".format("GLOBAL" if byte else "ROOM", name, message))
                self.parent.on_moderation(byte, name, message)
            elif ccc == P['SERVER_RESTART']:
                restime, = args
                log.info("[SERVER_RESTART] {}".format(restime))
            elif ccc == P['GET_CHEESE']:
                mouse_id, = args
                mouse_id = int(mouse_id)
                self.parent.on_mouse_cheese(mouse_id)
            elif ccc == P['MOUSE_ENTER_HOLE']:
                mouse_id, players_left, points, position, secs = args
                #log.info("enthole, "+str(args))
                self.parent.on_mouse_enter_hole(int(mouse_id), int(secs), int(position), int(players_left))
                #[2011-09-26 20:46:43] WARNING:  [1]<<< (8, 6, 'old'): ('5202891', '2', '44', '6', '805')
            elif ccc == P['SHAMAN_SAVES']:
                name, saves = args
                self.parent.shaman = None
                self.parent.on_end_shaman_turn(name, saves)
            elif ccc == P['TIME']:
                round_time, = args
            elif ccc == P['SHAMAN']:
                s1 = args[0]
                if len(s1)>0:
                    self.parent.on_start_shaman_turn(self.parent.get_name_from_id(int(s1)))
                    self.parent.shaman = s1
                else:
                    self.parent.shaman = None
            elif ccc == P['SYNC']:
                s1 = int(args[0])
                self.parent.on_sync(self.parent.get_name_from_id(s1))
            elif ccc == P['AVATAR']:
                verification, = args
                self.parent.on_avatar_verified(verification)
            elif ccc == P['SPAWN_ITEM']:
                item_id, y, x, u1, u2, ghost = args
                self.parent.on_item_spawn(*args)
                #b'\x00\x00\x01\x00\x01\x00\x00\x00\x00\x00\x01
            elif ccc == P['DEATH']:
                mouse_id, = args
                self.parent.on_mouse_death(int(mouse_id))
            elif ccc == P['SNOWING']:
                self.parent.on_snow()
            elif ccc == P['SHOP']:
                money, items, unk1, unk2 = args
                self.parent.on_shop_opened(money, items)
            elif ccc == P['TITLES']:
                titles = []
                for title in args:
                    titles.append(int(title))
                self.parent.titles = titles
                #self.parent.on_titles(titles)
            elif ccc == P['HEART_COUNT']:
                self.parent.hearts, = args
            elif ccc == P['COUNTDOWN']:
                if args[0] == "":
                    self.parent.on_countdown_end()
                else:
                    self.parent.on_countdown_start()
            elif ccc == P['BAN']:
                name, unk1, reason = args #unk1 is prolly time
            
    def send_ping(self):
        self.send_packet(P['PING'], self.server_type)
        self.send_packet(P['OLDPING'], self.server_type)
        
    def send_dummy(self): 
        self.send_packet(P['DUMMY'])

    def step(self):
        self.recv()
        
    def run(self):
        #log.info("LOOK AT ME I'M {} AND I'M STARTED".format(self.server_type))
        while True:
            try:
                self.step()
            except Exception as ex:
                self.parent.send_tribe_message("!!! FATAL ERROR: {}".format(ex))
                self.disconnect()
                raise
            #expcet KeyboardInterrupt as ex:
            #    self.parent.send
            if self._end:
                return

class TransformiceProtocol():
    def __init__(self, username, password, community, prefix="[???]"):
        self.username = username
        self.password = hashlib.sha256(password.encode('utf-8')).hexdigest() if len(password) else ""
        self.prefix = prefix
        
        self.community = community
        
        self.server_main = TransformiceSocket(self)
        self.server_room = DeadSocket(self)
        
        # Clean this up?  Pretty please?
        
        self.room = None
        self.room_mice = {}
        self.oldroom = None
        
        self.on_init()
        
        self.x = 450
        self.y = 450
        
        self.atnum = ""
        self.played_map = ""
        self.map_type = None
        self.hearts = 0
        self.titles = []
        self.follow_BULLE = False
        
        self.shaman = None
        
    def connect(self):
        self.server_main.connect_main()
        self.server_main.start()
        
    def step(self):
        pass
        #self.server_main.step()
        #self.server_room.step()
        #time.sleep(0.005)
           
    def get_name_from_id(self, mouse_id):
        for mouse, mid in self.room_mice.items():
           if mid == mouse_id:
               return mouse
        return None
    # Shortcuts
    def change_room(self, room):
        self.server_main.send_packet(P['COMMAND'], "room {}".format(room))
        self.follow_BULLE = True
    def play_map(self, map_num, map_type = None):
        self.server_main.send_packet(P['COMMAND'], "np {}".format(map_num))
        self.map_type = map_type
        self.played_map = map_num
    def send_tribe_message(self, message):
        self.server_main.send_packet(P['TRIBE_MESSAGE'], message.replace("<", "&lt;"))
    def send_room_message(self, message):
        self.server_main.send_packet(P['MESSAGE'], message.replace("<", "&lt;"))
    def send_private_message(self, to, message):
        self.server_main.send_packet(P['PRIVATE_MESSAGE'], to, message.replace("<", "&lt;"))
    def emote(self, emotion): self.server_room.send_packet(P['EMOTION'], emotion)
    def dance(self): self.emote(0)
    def laugh(self): self.emote(1)
    def cry(self): self.emote(2)
    def kiss(self): self.emote(3)
    def mad(self): self.emote(4)
    def clap(self): self.emote(5)
    def sleep(self): self.emote(6)
    def facepalm(self): self.emote(7)
    def sit(self): self.emote(8)
    def hidden(self): self.emote(9)
    def crouch(self): self.server_room.send_packet(P['CROUCH'], 1)
    def stand(self): self.server_room.send_packet(P['CROUCH'], 0)

    def die(self):
        self.server_room.send_packet(P['DEATH'], self.server_room.round_num)
        
    def jump(self, power=500):
        self.move(0, self.y, self.x, 0, power, 264)
        
    def move(self, run, y, x, hfriction, vfriction, jump, casting=0):
        #print(run, y, x, hfriction, vfriction, jump)
        self.x, self.y = x, y
        self.server_room.send_packet(P['MOVEMENT'], self.server_room.round_num, run, y, x, hfriction, vfriction, jump, 0, casting)
    
    def get_cheese(self):
        self.server_room.send_packet(P['GET_CHEESE'], self.server_room.round_num)
        
    def enter_hole(self):
        log.info("Entering hole!")
        self.server_room.send_packet(P['ENTER_HOLE'], 0, self.server_room.round_num)
    
    def verify_avatar(self):
        self.server_main.send_packet(P['AVATAR'])
    
    def enter_tribe_house(self):
        self.server_main.send_packet(P['ENTER_TRIBE_HOUSE'])
        self.follow_BULLE = True
    
    def play_music(self, url):
        self.server_main.send_packet(P['COMMAND'], "musique "+url)
        
    def spawn_item(self, item_id, y, x, u1, u2, ghost):
        self.server_room.send_packet(P['SPAWN_ITEM'], item_id, int(y//3.3325), int(x//3.3325), u1, u2, ghost)
    
    def spawn_item_under_self(self, item_id, ghost=1):
        self.spawn_item(item_id, self.y, self.x+20, 0, 0, ghost)
        
    def open_shop(self):
        self.server_main.send_packet(P['SHOP'])
    
    def list_titles(self):
        self.server_main.send_packet(P['COMMAND'], 'title')
    
    def set_title(self, title):
        self.server_main.send_packet(P['COMMAND'], 'title {}'.format(title))
    
    def cycle_room(self):
        logging.info("Cycling current room...")
        self.server_main.send_packet(P['COMMAND'], 'room temp fjdlkafjasflk sajf')
        self.oldroom = self.room
        if self.oldroom.startswith('en-'):
            self.oldroom = self.oldroom[3:]
        # XXX THIS IS UGLY AND THE SECOND HALF MUST BE IN on_room_change
    # Hooks
    
    def on_init(self): pass
    def on_login(self): pass
    def on_room_change(self): pass
    def on_room_message(self, name, message): pass
    def on_new_map(self, atnum, xml=""): pass    
    def on_countdown_start(self): pass
    def on_countdown_end(self): pass
    def on_mouse_movement(self, round_num, run, y, x, hfriction, vfriction, jump, casting, mouse_id): pass
    def on_mouse_cheese(self, mouse_id): pass
    def on_mouse_enter_hole(self, mouse_id, secs, position, players_left): pass
    def on_mouse_death(self, mouse_id): pass
    def on_mouse_emotion(self, mouse_id, emotion): pass
    def on_mouse_crouch(self, mouse_id, crouching): pass
    def on_start_shaman_turn(self, shaman): pass
    def on_sync(self, sync): pass
    def on_end_shaman_turn(self, name, saves): pass
    def on_item_spawn(self, item_id, y, x, u1, u2, ghost): pass
    def on_snow(self): pass
    def on_music(self,url): pass
    def on_private_message(self, name, message): pass
    def on_moderation(self, mode, name, message): pass
    def on_tribe_message(self, name, message): pass
    def on_tribe_connect(self,name): pass
    def on_tribe_disconnect(self,name): pass
    def on_tribe_join(self,name): pass
    def on_tribe_leave(self,name): pass
    def on_tribe_rank_change(self,name, rank): pass
    def on_tribe_chat_disable(self,name): pass
    def on_tribe_chat_enable(self,name): pass
    def on_avatar_verified(self, verification): pass
    def on_shop_opened(self, money, items): pass
    #def on_titles(self, titles): pass
    

