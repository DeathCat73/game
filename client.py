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
    def __init__(self, name, position=(0,0), font=pg.font.Font(None,32), text_func=lambda : "Hello, world!", align="l", col=(255,255,255), bg_col=None):
        """
        usage of lambda re-evaluates text each draw()
        allowing variables in text and complex text with whole functions
        """

        self.name = name
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


class TextInput:
    def __init__(self, name: str, rect_graph: RectGraphic, text_disp: TextDisplay, default_text: str = "", default_type: str = "pre"):
        """
        default_types:
        'pre': field is pre-filled with default_text
        'info': field contains default_text if otherwise empty
        """

        self.name = name
        self.timer = 0
        self.text = ""
        self.selected = False

        self.default_text = default_text
        self.default_type = default_type
        self.r_g = rect_graph
        self.t_d = text_disp
        self.t_d.text_func = self.inner_text

        if self.default_type == "pre":
            self.text = self.default_text

    def inner_text(self):
        if self.text == "" and self.default_type == "info":
            return self.default_text
        else:
            text = self.text
            if self.timer % 60 < 30 and self.selected:
                text += "|"
            return text

    def input(self, event: pg.event.Event):
        if event.type != pg.KEYDOWN:
            return
        
        if event.key == pg.K_RETURN:
            pg.event.post(pg.event.Event(TEXT_ENTERED, {"field": self.name, "text": self.text}))
        elif event.key == pg.K_BACKSPACE:
            if self.text:
                self.text = self.text[:-1]
        else:
            self.text += event.unicode

    def draw(self, display: pg.Surface):
        if self.selected:
            self.timer += 1
        else:
            self.timer = -1
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


class UI:
    def __init__(self, texts: list[TextDisplay], buttons: list[Button], inputs: list[TextInput]):
        self.texts = texts
        self.buttons = buttons
        self.inputs = inputs
    
    def __getitem__(self, key):
        elements = self.texts + self.buttons + self.inputs
        for e in elements:
            if e.name == key:
                return e
        raise ValueError(f"No element named {name}.")
    
    def draw_all(self, display):
        for e in self.texts + self.buttons + self.inputs:
            e.draw(display)


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
    t = ExcPropagateThread(target=sock.send, args=[("\n" + json.dumps(data)).encode("utf-8")], daemon=True)
    t.start()

def recieve(output, stop_event: threading.Event):
    global error_msg, error_timer
    buffer = bytes()
    while True:
        if stop_event.is_set():
            return
        
        try:
            data = sock.recv(999999)
            error_timer = 0
        except TimeoutError:
            if stop_event.is_set():
                return
            error_msg = "Lost connection"
            error_timer = 180
            continue

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
                continue
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
    parser.add_argument("--name", type=str, default="Player")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=38491)
    config = parser.parse_args()

    exit_types = ["BANNED", "KICK", "SHUTDOWN", "VERSION"]
    error_msg = ""

    plr = Player(config.name, [960, 540])

    pg.init()
    w, h = 1920, 1080
    display = pg.display.set_mode((w, h), pg.NOFRAME | pg.SCALED)
    clock = pg.time.Clock()
    fonts = {size: pg.font.Font(None, size) for size in [32,48,64]}

    main_menu = UI([TextDisplay("title", (w/2,h/10), pg.font.Font(None, 128), lambda : "SOCKET TEST PROJECT", "c"),
                    TextDisplay("error", (w/2, h/2+100), fonts[48], lambda : f"{error_msg}", "c", (255,0,0)),
                    TextDisplay("username_label", (w/2-150, h/3+120), fonts[48], lambda : "Username:", "l"),
                    TextDisplay("host_label", (w/2-150, h/3+160), fonts[48], lambda : "Host:", "l"),
                    TextDisplay("port_label", (w/2-150, h/3+200), fonts[48], lambda : "Port:", "l", (128,128,128))],
                   [Button("play",
                            RectGraphic(pg.Rect(w/2-100,h/3,200,100),[(0,128,0),(0,255,0)],10),
                            TextDisplay("play_text", (w/2,h/3+20), pg.font.Font(None, 96), lambda : "PLAY", "c"),
                            [(0,64,0),(0,192,0)], [(0,192,0),(64,255,64)])],
                   [TextInput("username",
                              RectGraphic(pg.Rect(w/2+50,h/3+120,300,35),[(64,64,64),(0,0,0)],-1),
                              TextDisplay("username_text", (w/2+50, h/3+120), fonts[48], lambda : "", "l"),
                              f"{config.name}", "pre"),
                    TextInput("host",
                              RectGraphic(pg.Rect(w/2+50,h/3+160,300,35),[(64,64,64),(0,0,0)],-1),
                              TextDisplay("host_text", (w/2+50, h/3+160), fonts[48], lambda : "", "l"),
                              f"{config.host}", "pre"),
                    TextInput("port",
                              RectGraphic(pg.Rect(w/2+50,h/3+200,300,35),[(32,32,32),(0,0,0)],-1),
                              TextDisplay("port_text", (w/2+50, h/3+200), fonts[48], lambda : "", "l", (128,128,128)),
                              f"{config.port}", "pre"),])

    VERSION = 1.2
    BUTTON_PRESSED, BUTTON_RELEASED = pg.event.custom_type(), pg.event.custom_type()
    STATE_CHANGE = pg.event.custom_type()
    TEXT_ENTERED = pg.event.custom_type()

    fps = 60
    state = "menu"
    selected_input = None
    players = dict()
    chat = []
    pwups = []
    projs = []
    chatting = False
    msg = ""
    chat_timer = 180
    error_timer = 180
    left = threading.Event()
    last_death = ["", 0]
    particles = []

    game_ui = UI([TextDisplay("k/d", (w,0), fonts[32], lambda : f"K/D: {k_d:.2f}", "r"),
                  TextDisplay("killer", (w/2,h/2.5), fonts[64], lambda : f"Killed by {username(plr.killer)}", "c", (255,0,0)),
                  TextDisplay("respawn", (w/2,h/2.5+35), fonts[48], lambda : f"Respawn in {plr.respawn_timer // 60 + 1}s", "c"),
                  TextDisplay("rapid", (w,h-25), fonts[48], lambda : "RAPID FIRE", "r", (255,0,0)),
                  TextDisplay("triple", (w,h-55), fonts[48], lambda : "TRIPLE SHOT", "r", (255,0,0)),
                  TextDisplay("speed", (w,h-85), fonts[48], lambda : "2X SPEED", "r", (255,0,0)),
                  TextDisplay("error", (w/2,0), fonts[32], lambda : error_msg, "c", (255,0,0))],
                 [],
                 [TextInput("curr_chat_msg",
                            RectGraphic(pg.Rect(0,h-30,w,30), [(32,32,32),(0,0,0)], -1),
                            TextDisplay("curr_chat_text", (0,h-30), fonts[32], lambda : "", "l"))])

    while True:
        display.fill(0)

        match state:
            case "menu":
                for event in pg.event.get():
                    if event.type == pg.QUIT:
                        pg.quit()
                        quit()
                    elif event.type == pg.MOUSEBUTTONDOWN:
                        pos = pg.mouse.get_pos()
                        if event.button == 1:
                            if selected_input is not None:
                                selected_input.selected = False
                            for inp in main_menu.inputs:
                                if inp.r_g.rect.collidepoint(pos):
                                    inp.selected = True
                                    selected_input = inp
                                    break
                            else:
                                selected_input = None
                    elif event.type == pg.KEYDOWN:
                        if event.key == pg.K_ESCAPE:
                            pg.quit()
                            quit()
                        elif selected_input is not None:
                            selected_input.input(event)
                    elif event.type == BUTTON_RELEASED:
                        if event.button == "play":
                            try:
                                sock = socket.create_connection((config.host, config.port), timeout=2)
                            except (ConnectionRefusedError, TimeoutError, OSError, socket.gaierror):
                                error_msg = "Failed to connect."
                                error_timer = 120
                                continue

                            state = "game"
                            pg.event.post(pg.event.Event(STATE_CHANGE, {"old": "menu", "new": "game"}))

                            recieved = {"players": dict(), 
                                        "chat": [],
                                        "pwups": [],
                                        "projs": [],
                                        "plr": None,
                                        "death": ["", 0]}
                            
                            left.clear()
                            recv_t = ExcPropagateThread(target=recieve, args=[recieved, left], daemon=True)
                            recv_t.start()
                            thread_exc = None

                            send(["JOIN", plr.name, plr.pos, VERSION])
                    elif event.type == STATE_CHANGE:
                        error_timer = 120
                        plr.name = config.name

                config.name = main_menu["username"].text
                config.host = main_menu["host"].text
                try:
                    config.port = int(main_menu["port"].text)
                except ValueError:
                    error_msg = "Port should be an integer"
                    error_timer = 50
                
                main_menu["error"].col = (min(255, error_timer*4),0,0)

                mouse = pg.mouse.get_pressed()
                mpos = pg.mouse.get_pos()
                for button in main_menu.buttons:
                    button.update_input(mouse, mpos)

                main_menu.draw_all(display)

                error_timer = max(error_timer-1, 0)

            case "game":
                t = time.perf_counter()

                send(["UPDATE"])

                if thread_exc:
                    if type(thread_exc) in (ConnectionAbortedError, ConnectionResetError, OSError):
                        left.set()
                        error_msg = "You disconnected from the server."
                        state = "menu"
                        pg.event.post(pg.event.Event(STATE_CHANGE, {"old": "game", "new": "menu"}))
                    else:
                        raise thread_exc

                for event in pg.event.get():
                    if event.type == pg.QUIT:
                        left.set()
                        send(["QUIT"])
                        error_msg = "You left the server."
                        state = "menu"
                        pg.event.post(pg.event.Event(STATE_CHANGE, {"old": "game", "new": "menu"}))
                    elif event.type == pg.KEYDOWN:
                        if chatting:
                            if event.key == pg.K_ESCAPE:
                                chatting = False
                                game_ui["curr_chat_msg"].text = ""
                            else:
                                game_ui["curr_chat_msg"].input(event)
                        elif event.key == pg.K_t:
                            chatting = True
                        elif event.key == pg.K_ESCAPE:
                            left.set()
                            send(["QUIT"])
                            error_msg = "You left the server."
                            state = "menu"
                            pg.event.post(pg.event.Event(STATE_CHANGE, {"old": "game", "new": "menu"}))
                    elif event.type == TEXT_ENTERED:
                        if event.field == "curr_chat_msg":
                            chatting = False
                            send(["CHAT", game_ui["curr_chat_msg"].text])
                            game_ui["curr_chat_msg"].text = ""
                if state != "game": continue

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
                        error_msg = exit_msg
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
                error_timer = max(error_timer-1, 0)
                if chatting:
                    game_ui["curr_chat_msg"].draw(display)
                for i, m in enumerate(chat):
                    if i >= 3 and chat_timer == 0: break
                    TextDisplay((10, h-30*(i+2)), fonts[32], lambda : m, "l", (255 if i < 3 else min(chat_timer*2,255),)*3).draw(display)

                for (pw, timer), text in zip(plr.powerups.items(), [game_ui[x] for x in ["rapid", "triple", "speed"]]):
                    if timer > 0:
                        text.draw(display, [-random.random()*5, -random.random()*5])

                for pw in pwups:
                    pg.draw.rect(display, np.array([255]) * colorsys.hsv_to_rgb((t/2+pw[0]/2000)%1, 1, 1), [pw[0]-15,pw[1]-15,30,30])

                for i in range(plr.hp):
                    pg.draw.rect(display, (255,128,128), [40*i+10, 10, 30, 30])

                if plr.respawn_timer > 0:
                    game_ui["killer"].draw(display)
                    game_ui["respawn"].draw(display)
                    pass

                k_d = plr.kills / max(plr.deaths, 1)
                game_ui["k/d"].draw(display)

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

                game_ui["error"].col = (min(error_timer*4, 255), 0, 0)
                game_ui["error"].draw(display)

        pg.display.update()
        clock.tick(fps)