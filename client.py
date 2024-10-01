import socket
import threading
import time
import pygame as pg
import json
import colorsys
import numpy as np
import random
import argparse


class Player:
    def __init__(self, username, position):
        self.name = username
        self.pos = position
        self.cooldown = 0
        self.rate = 15
        self.powerups = {"rapid": 0,
                         "triple": 0,
                         "speed": 0}
        self.hp = 3
        self.iframes = 60
        self.shooting = False
        self.mouse_pos = [0,0]
        self.respawn_timer = 0
        self.killer = None
        self.kills = 0
        self.deaths = 0

    @property
    def rect(self):
        return pg.Rect(self.pos[0]-20, self.pos[1]-20, 40, 40)
    

class Particle:
    def __init__(self, position, speed=200):
        self.pos = np.array(position, np.float64)
        self.speed = speed
        self.age = 0
        theta = random.random() * np.pi * 2
        self.direction = np.array([np.cos(theta), np.sin(theta)]) * random.random()

    def tick(self):
        self.age += 1
        self.pos += self.direction * self.speed / 60 * 0.98 ** self.age
        return self.age >= 60
    
    def draw(self):
        pg.draw.rect(display, (min(255,255*(90-self.age)/60),0,0), [self.pos-5, [10,10]])


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
    

def send(data):
    if thread_exc:
        raise thread_exc
    
    t = ExcPropagateThread(target=sock.send, args=[("\n" + json.dumps(data)).encode("utf-8")], daemon=True)
    t.start()

def recieve():
    global recieved

    buffer = bytes()
    while True:
        data = sock.recv(4096)
        buffer += data
        items = buffer.split("\n".encode("utf-8"))
        overflow = len(data) == 4096
        if overflow:
            print("Can't keep up with the server")
            # discard partially sent message
            items = items[:-1]
        for item in items:
            if not item: continue
            msg = json.loads(item)
            recieved[msg[0]] = msg[1]
            if msg[0] in exit_types:
                return
        if overflow:
            buffer = buffer.split("\n".encode("utf-8"))[-1]
            # keep partial msg to be completed later
        else:
            buffer = bytes()


def username(name: str):
    i1 = name.index(":")
    i2 = name.index(":", i1+1)
    return name[i2+1:]


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--name", type=str, required=True)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=38491)
    config = parser.parse_args()

    exit_types = ["BANNED", "KICK", "SHUTDOWN", "VERSION"]

    plr = Player(config.name, [960, 540])

    sock = socket.create_connection((config.host, config.port))

    recieved = {"players": dict(), 
                "chat": [],
                "pwups": [],
                "projs": [],
                "plr": None,
                "death": ["", 0]}
    recv_t = threading.Thread(target=recieve, daemon=True)
    recv_t.start()
    thread_exc = None

    pg.init()
    w, h = 1920, 1080
    display = pg.display.set_mode((w, h), pg.HWACCEL | pg.NOFRAME)
    clock = pg.time.Clock()
    fonts = {size: pg.font.Font(None, size) for size in [32,48,64]}

    VERSION = 1.2
    fps = 60
    players = dict()
    chat = []
    pwups = []
    projs = []
    chatting = False
    msg = ""
    chat_timer = 180
    left = False
    frames = 0
    last_death = ["", 0]
    particles = []

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

        keys = pg.key.get_pressed()
        if not (chatting or plr.respawn_timer > 0 or frames % 3):
            plr_input = pg.mouse.get_pressed()[0] * 16 + keys[pg.K_w] * 8 + keys[pg.K_a] * 4 + keys[pg.K_s] * 2 + keys[pg.K_d]
            send(["INPUT", plr_input, pg.mouse.get_pos()])

        for exit_type, exit_msg in zip(exit_types, \
            ["You are banned from the server.", "You were kicked from the server.", "The server shut down.", "Version mismatch - client {} vs server {}."]):
            if exit_type in recieved.keys() and not left:
                left = True
                if exit_type != "BANNED":
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

        if recieved["plr"] is not None:
            # replacing whole dict would break at start if its even allowed
            for key, val in recieved["plr"].items():
                plr.__dict__[key] = val

        if recieved["death"] != last_death:
            last_death = recieved["death"]
            for _ in range(50):
                particles.append(Particle(dict(players)[last_death[0]]))

        for p in particles:
            if p.tick():
                particles.remove(p)

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
                display.blit(text, (w-text.get_width()-random.random()*5, h-text.get_height()*(i+1)-random.random()*5))
                i += 1

        for pw in pwups:
            pg.draw.rect(display, np.array([255]) * colorsys.hsv_to_rgb((t/2+pw[0]/2000)%1, 1, 1), [pw[0]-15,pw[1]-15,30,30])

        for i in range(plr.hp):
            pg.draw.rect(display, (255,128,128), [40*i+10, 10, 30, 30])

        if plr.respawn_timer > 0:
            text1 = fonts[64].render(f"Killed by {username(plr.killer)}", True, (255,0,0))
            text2 = fonts[48].render(f"Respawn in {plr.respawn_timer // 60 + 1}s", True, (255,255,255))
            display.blit(text1, (w/2 - text1.get_rect().centerx, h/2.5))
            display.blit(text2, (w/2 - text2.get_rect().centerx, h/2.5 + 35))
            plr.pos = [-1000, -1000]
        elif plr.respawn_timer == 0:
            plr.pos = [960, 540]

        k_d = plr.kills / max(plr.deaths, 1)
        text = fonts[32].render(f"K/D: {k_d:.2f}", True, (255,255,255))
        display.blit(text, (w-text.get_size()[0], 0))

        for p in players:
            name = p[0]
            pg.draw.rect(display, (255*(name!=plr.name),127*(name==plr.name)*(1+(plr.iframes<=0)),0), [p[1][0]-20, p[1][1]-20, 40, 40])
            text = fonts[32].render(username(name), True, (255,)*3)
            display.blit(text, (p[1][0]-text.get_rect().centerx, p[1][1]-50))

        for p in particles:
            p.draw()

        for pr in projs:
            pg.draw.rect(display, (255,)*3, [pr[0]-5,pr[1]-5,10,10])

        frames += 1

        pg.display.update()
        clock.tick(fps)