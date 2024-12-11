import socket
import threading
import time
import pygame as pg
import json
import colorsys
import numpy as np
import random
import argparse

pg.init()


class Player:
    def __init__(self, username: str, position: list[int|float]):
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
    

class TextDisplay:
    def __init__(self, position=(0,0), font=pg.font.Font(None,32), text_func=lambda : "Hello, world!", align="l", col=(255,255,255), bg_col=None):
        self.pos = np.array(position)
        self.align = align
        self.font = font
        self.text_func = text_func
        self.col = col
        self.bg_col = bg_col

    def draw(self, display: pg.Surface, offset: list[int|float] = [0,0]):
        surf = self.font.render(self.text_func(), True, self.col, self.bg_col)
        match self.align:
            case "l":
                pass
            case "r":
                offset[0] -= surf.get_width()
            case "c":
                offset[0] -= surf.get_rect().centerx
        display.blit(surf, self.pos + offset)
        match self.align:
            case "l":
                pass
            case "r":
                offset[0] += surf.get_width()
            case "c":
                offset[0] += surf.get_rect().centerx
        # mutability jank


class RectGraphic:
    def __init__(self, rect: pg.Rect, colours: list[tuple[int]], border: int):
        self.rect = rect
        self.colours = colours
        self.border = border

    def draw(self, display: pg.Surface):
        pg.draw.rect(display, self.colours[0], self.rect)
        pg.draw.rect(display, self.colours[1], self.rect, width=self.border)


class Button:
    def __init__(self, name: str, rect_graph: RectGraphic, text_disp: TextDisplay, hover_cols, click_cols):
        self.name = name

        self.r_g = rect_graph
        self.cols = [rect_graph.colours, hover_cols, click_cols]
        self.t_d = text_disp

        self.hovered = False
        self.clicked = False

    def update_input(self, buttons: list[int], pos: tuple[int]):
        self.hovered = self.r_g.rect.collidepoint(pos)
        if self.hovered and buttons[0] and not self.clicked:
            pg.event.post(pg.event.Event(BUTTON_PRESSED, {"button": self.name}))
        elif self.hovered and self.clicked and not buttons[0]:
            pg.event.post(pg.event.Event(BUTTON_RELEASED, {"button": self.name}))
        self.clicked = self.hovered and buttons[0]

    def draw(self, display: pg.Surface):
        self.r_g.colours = self.cols[self.hovered+self.clicked]
        self.r_g.draw(display)
        self.t_d.draw(display)
    

class Particle:
    def __init__(self, position: tuple[int|float], speed: int|float = 200):
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

    def join(self, timeout: int|float = None):
        super(ExcPropagateThread, self).join(timeout)
        if self.exc:
            raise self.exc
        return self.ret
    

def send(data):
    if thread_exc:
        raise thread_exc
    
    t = ExcPropagateThread(target=sock.send, args=[("\n" + json.dumps(data)).encode("utf-8")], daemon=True)
    t.start()

def recieve(output, stop_event: threading.Event):

    buffer = bytes()
    while True:
        if stop_event.is_set():
            return
        data = sock.recv(999999)
        buffer += data
        items = buffer.split("\n".encode("utf-8"))
        overflow = len(data) == 999999 or items[-1] and chr(items[-1][-1]) not in "]}"
        if overflow: #if this ever runs...
            print("Can't keep up with the server")
            # discard partially sent message
            items = items[:-1]
        
        for item in items:
            if not item: continue
            try:
                msg = json.loads(item)
            except json.decoder.JSONDecodeError:
                print("A message from the server couldn't be decoded:")
                print(item)
            output[msg[0]] = msg[1]
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
    last_exit_msg = ""

    plr = Player(config.name, [960, 540])

    pg.init()
    w, h = 1920, 1080
    display = pg.display.set_mode((w, h), pg.HWACCEL | pg.NOFRAME)
    clock = pg.time.Clock()
    fonts = {size: pg.font.Font(None, size) for size in [32,48,64]}

    main_menu = [[Button("play",
                         RectGraphic(pg.Rect(w/2 - 100, h/3, 200, 100), [(0,128,0),(0,255,0)], 10),
                         TextDisplay((w/2,h/3+20), pg.font.Font(None, 96), lambda : "PLAY", "c"),
                         [(0,64,0),(0,192,0)],
                         [(0,192,0),(64,255,64)])],
                 [TextDisplay((w/2,h/10), pg.font.Font(None, 128), lambda : "SOCKET TEST PROJECT", "c"),
                  TextDisplay((w/2, h/3+120), fonts[48], lambda : f"Username: {config.name}", "c"),
                  TextDisplay((w/2, h/3+160), fonts[48], lambda : f"Host: {config.host}", "c"),
                  TextDisplay((w/2, h/3+200), fonts[48], lambda : f"Port: {config.port}", "c", (128,128,128)),
                  TextDisplay((w/2, h/2+100), fonts[48], lambda : f"{last_exit_msg}", "c", (255,0,0))]]

    VERSION = 1.2
    BUTTON_PRESSED, BUTTON_RELEASED = pg.event.custom_type(), pg.event.custom_type()
    STATE_CHANGE = pg.event.custom_type()

    fps = 60
    state = "menu"
    players = dict()
    chat = []
    pwups = []
    projs = []
    chatting = False
    msg = ""
    chat_timer = 180
    left = threading.Event()
    last_death = ["", 0]
    particles = []

    curr_chat_text = TextDisplay((10,h-25), fonts[32], lambda : msg, "l", (min(chat_timer*2,255),)*3)
    kd_text = TextDisplay((w,0), fonts[32], lambda : f"K/D: {k_d:.2f}", "r")
    killer_text = TextDisplay((w/2,h/2.5), fonts[64], lambda : f"Killed by {username(plr.killer)}", "c", (255,0,0))
    respawn_text = TextDisplay((w/2,h/2.5+35), fonts[48], lambda : f"Respawn in {plr.respawn_timer // 60 + 1}s", "c")
    pw_rapid_text = TextDisplay((w,h-25), fonts[48], lambda : "RAPID FIRE", "r", (255,0,0))
    pw_triple_text = TextDisplay((w,h-55), fonts[48], lambda : "TRIPLE SHOT", "r", (255,0,0))
    pw_speed_text = TextDisplay((w,h-85), fonts[48], lambda : "2X SPEED", "r", (255,0,0))


    while True:
        display.fill(0)

        match state:
            case "menu":
                for event in pg.event.get():
                    if event.type == pg.QUIT:
                        pg.quit()
                        quit()
                    elif event.type == pg.KEYDOWN:
                        if event.key == pg.K_ESCAPE:
                            pg.quit()
                            quit()
                    elif event.type == BUTTON_RELEASED:
                        if event.button == "play":
                            state = "game"
                            pg.event.post(pg.event.Event(STATE_CHANGE, {"old": "menu", "new": "game"}))

                            sock = socket.create_connection((config.host, config.port))
                            recieved = {"players": dict(), 
                                        "chat": [],
                                        "pwups": [],
                                        "projs": [],
                                        "plr": None,
                                        "death": ["", 0]}
                            
                            recv_t = threading.Thread(target=recieve, args=[recieved, left], daemon=True)
                            recv_t.start()
                            thread_exc = None

                            send(["JOIN", plr.name, plr.pos, VERSION])
                    elif event.type == STATE_CHANGE:
                        chat_timer = 120
                        plr.name = config.name
                
                main_menu[1][4].col = (min(255, chat_timer*4),0,0)

                mouse = pg.mouse.get_pressed()
                mpos = pg.mouse.get_pos()

                for button in main_menu[0]:
                    button.update_input(mouse, mpos)
                    button.draw(display)
                for text in main_menu[1]:
                    text.draw(display)

                chat_timer = max(chat_timer-1, 0)

            case "game":
                t = time.perf_counter()

                send(["UPDATE"])

                for event in pg.event.get():
                    if event.type == pg.QUIT:
                        left.set()
                        send(["QUIT"])
                        last_exit_msg = "You left the server."
                        state = "menu"
                        pg.event.post(pg.event.Event(STATE_CHANGE, {"old": "game", "new": "menu"}))
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
                            left.set()
                            send(["QUIT"])
                            last_exit_msg = "You left the server."
                            state = "menu"
                            pg.event.post(pg.event.Event(STATE_CHANGE, {"old": "game", "new": "menu"}))
                if state != "game":
                    left.clear()
                    continue

                keys = pg.key.get_pressed()
                if not (chatting or plr.respawn_timer > 0):
                    plr_input = pg.mouse.get_pressed()[0] * 16 + keys[pg.K_w] * 8 + keys[pg.K_a] * 4 + keys[pg.K_s] * 2 + keys[pg.K_d]
                else:
                    plr_input = 0
                send(["INPUT", plr_input, pg.mouse.get_pos()])

                for exit_type, exit_msg in zip(exit_types, \
                    ["You are banned from the server.", "You were kicked from the server.", "The server shut down.", "Version mismatch - client {} vs server {}."]):
                    if exit_type in recieved.keys() and not left.is_set():
                        left.set()
                        if exit_type != "BANNED":
                            send(["QUIT"])
                        if exit_type == "VERSION":
                            exit_msg = exit_msg.format(VERSION, recieved.get("VERSION", "unknown"))
                        last_exit_msg = exit_msg
                        state = "menu"
                        pg.event.post(pg.event.Event(STATE_CHANGE, {"old": "game", "new": "menu"}))
                if state != "game": continue
                
                players = recieved["players"]
                chat = recieved["chat"]
                pwups = recieved["pwups"]
                projs = recieved["projs"]

                if recieved["plr"] is not None:
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
                if chatting:
                    pg.draw.rect(display, (16,16,16), [0, h-30, w, 30])
                    curr_chat_text.draw(display)
                for i, m in enumerate(chat):
                    if i >= 3 and chat_timer == 0: break
                    TextDisplay((10, h-30*(i+2)), fonts[32], lambda : m, "l", (255 if i < 3 else min(chat_timer*2,255),)*3).draw(display)

                for (pw, timer), text in zip(plr.powerups.items(), [pw_rapid_text, pw_triple_text, pw_speed_text]):
                    if timer > 0:
                        text.draw(display, [-random.random()*5, -random.random()*5])

                for pw in pwups:
                    pg.draw.rect(display, np.array([255]) * colorsys.hsv_to_rgb((t/2+pw[0]/2000)%1, 1, 1), [pw[0]-15,pw[1]-15,30,30])

                for i in range(plr.hp):
                    pg.draw.rect(display, (255,128,128), [40*i+10, 10, 30, 30])

                if plr.respawn_timer > 0:
                    killer_text.draw(display)
                    respawn_text.draw(display)
                    pass

                k_d = plr.kills / max(plr.deaths, 1)
                kd_text.draw(display)

                for p in players:
                    name = p[0]
                    col = (255,0,0)
                    if name == plr.name:
                        col = (0,127*(1+(plr.iframes<=0)),0)
                        p[1] = plr.pos
                    pg.draw.rect(display, col, [p[1][0]-20, p[1][1]-20, 40, 40])
                    TextDisplay((p[1][0], p[1][1]-50), fonts[32], lambda: username(name), "c").draw(display)

                for p in particles:
                    p.draw()

                for pr in projs:
                    pg.draw.rect(display, (255,)*3, [pr[0]-5,pr[1]-5,10,10])

        pg.display.update()
        clock.tick(fps)