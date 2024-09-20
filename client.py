import socket
import threading
import time
import pygame as pg
import json
import colorsys
import numpy as np
import random


class Player:
    def __init__(self, username, position):
        self.name = username
        self.pos = position
        self.cooldown = 0
        self.rate = 15
        self.powerups = {"rapid": 0,
                         "triple": 0,
                         "speed": 0}
        self.shooting = False
        self.hp = 3
        self.iframes = 60

    @property
    def rect(self):
        return pg.Rect(self.pos[0]-20, self.pos[1]-20, 40, 40)
    
    def tick(self):
        if self.shooting and self.cooldown <= 0:
            send(["SHOOT", pg.mouse.get_pos(), self.powerups])
            self.cooldown = self.rate
            if self.powerups["rapid"] > 0:
                self.cooldown /= 2
        for pwrup in self.powerups.keys():
            self.powerups[pwrup] -= 1
        self.cooldown -= 1
        self.iframes -= 1


class ExcPropagateThread(threading.Thread):
    def run(self):
        global thread_exc
        self.exc = None
        try:
            self.ret = self._target(*self._args, **self._kwargs)
        except Exception as e:
            self.exc = e
        if self.exc:
            thread_exc = self.exc

    def join(self, timeout=None):
        super(ExcPropagateThread, self).join(timeout)
        if self.exc:
            raise self.exc
        return self.ret
    

def send(data: str):
    if thread_exc:
        raise thread_exc
    
    t = ExcPropagateThread(target=sock.send, args=[("\n" + json.dumps(data)).encode("utf-8")], daemon=True)
    t.start()

def recieve():
    global recieved

    partial_item = bytes()
    while True:
        data = sock.recv(4096)
        if len(data) == 4096:
            print("Can't keep up with the server")
        data = data.split("\n".encode("utf-8"))
        partial_item += data[0]
        for item in [partial_item] * bool(partial_item) + data[1:-1]:
            msg = json.loads(item)
            #print(msg[0])
            recieved[msg[0]] = msg[1]
            if msg[0] == "QUIT":
                print("recvd 2")
                return
        partial_item = data[-1]


def username(name: str):
    i1 = name.index(":")
    i2 = name.index(":", i1+1)
    return name[i2+1:]


if __name__ == "__main__":

    try:
        config = json.load(open("config.json", "rt"))
    except FileNotFoundError:
        with open("config.json", "wt") as f:
            f.write('{\n    "HOST": "0.0.0.0",\n    "PORT": 38491,\n    "NAME": "Player"\n}')
        print("config.json created. Open it and enter a host, port and username.")
        pg.quit()
        quit()

    plr = Player(config["NAME"], [960, 540])

    sock = socket.create_connection((config["HOST"], config["PORT"]))

    recieved = {"players": dict(), 
                "chat": [],
                "pwups": [],
                "projs": [],
                "hits": [],
                "pw_hits": []}
    recv_t = threading.Thread(target=recieve, daemon=True)
    recv_t.start()
    thread_exc = None

    pg.init()
    w, h = 1920, 1080
    display = pg.display.set_mode((w, h), pg.HWACCEL | pg.NOFRAME)
    clock = pg.time.Clock()
    fonts = {size: pg.font.Font(None, size) for size in [32,48,64]}

    VERSION = 1.0
    fps = 60
    speed = 300
    players = dict()
    chat = []
    pwups = []
    projs = []
    chatting = False
    msg = ""
    chat_timer = 180
    respawn_timer = -1
    killer = None
    left = False

    send(["JOIN", plr.name, plr.pos, VERSION])

    while True:
        display.fill(0)
        t = time.perf_counter()

        send(["UPDATE"])

        for event in pg.event.get():
            if event.type == pg.QUIT:
                left = True
                send(["QUIT"])
                print("You left the server.")
                pg.quit()
                quit()
            elif event.type == pg.KEYDOWN:
                if chatting:
                    if event.key == pg.K_ESCAPE:
                        chatting = False
                        msg = ""
                    elif event.key == 13:
                        chatting = False
                        send(["CHAT", msg])
                        msg = ""
                    elif event.key == pg.K_BACKSPACE:
                        msg = msg[:-1]
                    else:
                        msg += event.unicode
                elif event.key == pg.K_t:
                    chatting = True
                elif event.key == pg.K_ESCAPE:
                    left = True
                    send(["QUIT"])
                    print("You left the server.")
                    pg.quit()
                    quit()
            elif event.type == pg.MOUSEBUTTONDOWN:
                plr.shooting = True
            elif event.type == pg.MOUSEBUTTONUP:
                plr.shooting = False

        keys = pg.key.get_pressed()
        if not (chatting or respawn_timer > 0):
            mult = 1 + (plr.powerups["speed"] > 0)
            if keys[pg.K_w]:
                plr.pos[1] -= speed / fps * mult
            if keys[pg.K_a]:
                plr.pos[0] -= speed / fps * mult
            if keys[pg.K_s]:
                plr.pos[1] += speed / fps * mult
            if keys[pg.K_d]:
                plr.pos[0] += speed / fps * mult

            plr.pos[0] = min(max(plr.pos[0], 20), w-20)
            plr.pos[1] = min(max(plr.pos[1], 20), h-20)

            send(["POS",plr.pos])

        for exit_type, exit_msg in zip(["BANNED", "KICK", "SHUTDOWN", "VERSION"], \
            ["You are banned from the server.", "You were kicked from the server.", "The server shut down.", "Version mismatch - client {} vs server {}."]):
            if exit_type in recieved.keys() and not left:
                left = True
                send(["QUIT"])
                if exit_type == "VERSION":
                    exit_msg = exit_msg.format(VERSION, recieved.get("VERSION", "unknown"))
                print(exit_msg)
                pg.quit()
                quit()
        
        players = recieved["players"]
        chat = recieved["chat"]
        pwups = recieved["pwups"]
        projs = recieved["projs"]

        for hit in recieved["hits"]:
            if username(hit[0]) == plr.name:
                send(["HIT"])
                if respawn_timer < 0 and plr.iframes <= 0:
                    plr.hp -= 1
                    plr.iframes = 6
                    if plr.hp <= 0:
                        send(["DIED", hit[1]])
                        plr.pos = [w/2, h/2]
                        plr.hp = 3
                        respawn_timer = 180
                        iframes = 240
                        killer = hit[1]
                        for pwrup in plr.powerups.keys():
                            plr.powerups[pwrup] = 0
                    break
        for hit in recieved["pw_hits"]:
            if username(hit[0]) == plr.name:
                plr.powerups[hit[1]] = 300
                send(["PW_HIT"])
                break

        if respawn_timer < 0:
            plr.tick()

        chat_timer = max(chat_timer-1, chatting*180)
        if chatting: pg.draw.rect(display, (16,16,16), [0, h-30, w, 30])
        text = fonts[32].render(msg, True, (min(chat_timer*2,255),)*3)
        display.blit(text, (10, h-25))
        for i, m in enumerate(chat):
            if i >= 3 and chat_timer == 0: break
            text = fonts[32].render(m, True, (255 if i < 3 else min(chat_timer*2,255),)*3)
            display.blit(text, (10, h-30*(i+2)))

        i = 0
        for pw, timer in plr.powerups.items():
            if timer > 0:
                text = fonts[48].render({"rapid":"RAPID FIRE","triple":"TRIPLE SHOT","speed":"2X SPEED"}[pw], True, (255,0,0))
                display.blit(text, (w-text.get_rect().width-random.random()*5, h-text.get_rect().height*(i+1)-random.random()*5))
                i += 1

        for p in players.items():
            name = username(p[0])
            pg.draw.rect(display, (255*(name!=plr.name),127*(name==plr.name)*(1+(plr.iframes<=0)),0), [p[1][0]-20, p[1][1]-20, 40, 40])
            text = fonts[32].render(name, True, (255,)*3)
            display.blit(text, (p[1][0]-text.get_rect().centerx, p[1][1]-50))

        for pw in pwups:
            pg.draw.rect(display, np.array([255]) * colorsys.hsv_to_rgb((t/2+pw[0]/2000)%1, 1, 1), [pw[0]-15,pw[1]-15,30,30])

        for pr in projs:
            pg.draw.rect(display, (255,)*3, [pr[0]-5,pr[1]-5,10,10])

        for i in range(plr.hp):
            pg.draw.rect(display, (255,128,128), [40*i+10, 10, 30, 30])

        if respawn_timer > 0:
            text1 = fonts[64].render(f"Killed by {username(killer)}", True, (255,0,0))
            text2 = fonts[48].render(f"Respawn in {respawn_timer // 60 + 1}s", True, (255,255,255))
            display.blit(text1, (w/2 - text1.get_rect().centerx, h/2.5))
            display.blit(text2, (w/2 - text2.get_rect().centerx, h/2.5 + 35))
            plr.pos = [-1000, -1000]
        elif respawn_timer == 0:
            plr.pos = [960, 540]

        respawn_timer -= 1

        pg.display.update()
        clock.tick(fps)