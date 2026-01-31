import socket
import threading
import random
import json
import pygame as pg
import math
import numpy as np
import time
import argparse
from concurrent.futures import ThreadPoolExecutor


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
        self.mvmt = 0
        self.respawn_timer = 0
        self.killer = None
        self.kills = 0
        self.deaths = 0

    @property
    def rect(self):
        return pg.Rect(self.pos[0]-20, self.pos[1]-20, 40, 40)
    
    @property
    def data_encoded_pos(self):
        #odd x -> iframes, odd y -> dead
        return [self.pos[0] // 2 * 2 + (self.iframes > 0),
                self.pos[1] // 2 * 2 + (self.respawn_timer > 0)]
    
    def tick(self):
        self.respawn_timer -= 1
        if self.respawn_timer < 0:
            mult = 1 + (self.powerups["speed"] > 0)
            if self.mvmt >= 8:
                self.pos[1] -= 5 * mult
            if self.mvmt % 8 >= 4:
                self.pos[0] -= 5 * mult
            if self.mvmt % 4 >= 2:
                self.pos[1] += 5 * mult
            if self.mvmt % 2:
                self.pos[0] += 5 * mult

            self.pos[0] = min(max(self.pos[0], 20), 1900)
            self.pos[1] = min(max(self.pos[1], 20), 1060)

            for pwrup in self.powerups.keys():
                self.powerups[pwrup] -= 1
            self.cooldown -= 1
            self.iframes -= 1
            if self.shooting and self.cooldown <= 0:
                self.cooldown = self.rate
                if self.powerups["rapid"] > 0:
                    self.cooldown /= 2
                return True
            return False
        elif self.respawn_timer == 0:
            self.pos = [960,540]


class Powerup:
    def __init__(self):
        self.type = random.choice(["rapid", "triple", "speed"])
        self.pos = [random.random() * 1890 + 15, random.random() * 1050 + 15]
        self.rect = pg.Rect(self.pos[0]-15, self.pos[1]-15, 30, 30)


class Projectile:
    def __init__(self, position, shooter, offset, speed=1000):
        self.pos = np.array(position, np.float64)
        self.velocity = np.array(offset) / math.dist((0,0), offset) * speed
        self.shooter = shooter

    @property
    def rect(self):
        return pg.Rect(self.pos[0]-5, self.pos[1]-5, 10, 10)

    def tick(self, players):
        self.pos += self.velocity / 60
        if not self.rect.colliderect([0,0,1920,1080]):
            return False
        for name, plr in players:
            if name == self.shooter:
                continue
            rect = pg.Rect(plr.pos[0]-20, plr.pos[1]-20, 40, 40)
            if self.rect.colliderect(rect):
                return name, self.shooter
            

def username(name: str):
    i1 = name.index(":")
    i2 = name.index(":", i1+1)
    return name[i2+1:]


def send(conn, msgs, executor):
    data = ""
    for m in msgs:
        data += "\n"+json.dumps(m)
    executor.submit(conn.sendall, data.encode("utf-8"))
    


class GameServer:
    def __init__(self, name="server", port=38491):
        self.VERSION = 1.32
        self.allowed_versions = [1.31, 1.3]
        self.name = name
        self.threads = []
        self.sock = socket.create_server(("", port))
        self.executor = ThreadPoolExecutor()
        self.players = dict()
        self.projectiles = []
        self.powerups = []
        self.send_queue = []
        self.tps = 0

    def process_command(self, command, sender, share_output=False):
        match command[0].lower():
            case "tps":
                if share_output:
                    self.chat(str(self.tps), sender)
                else:
                    self.send_queue.append([sender, ["EVENT", "CHAT", str(self.tps)]])
            case "kick":
                target = command[1]
                kick_all = len(command) >= 3 and command[2].lower() == "all"
                targets = [p for p in self.players.keys() if username(p) == target]
                print(*[p for p in self.players.keys()])
                if targets:
                    if share_output: self.chat(f"{target} was kicked.")
                    self.send_queue.append([targets[0], ["EXIT", "KICK", 1]])
                    if kick_all:
                        for t in targets[1:]:
                            if share_output: self.chat(f"{target} was kicked.")
                            self.send_queue.append([t, ["EXIT", "KICK", 1]])
            case "ban":
                target = command[1]
                ban_all = len(command) >= 3 and command[2].lower() == "all"
                targets = [p for p in self.players.keys() if username(p) == target]
                if targets:
                    if share_output: self.chat(f"{target} was banned.")
                    self.send_queue.append([targets[0], ["EXIT", "KICK", 1]])
                    config["banned"].append(targets[0][:targets[0].find(":")])
                    if ban_all:
                        for t in targets[1:]:
                            if share_output: self.chat(f"{target} was banned.")
                            self.send_queue.append([t, ["EXIT", "KICK", 1]])
                            config["banned"].append(t[:t.find(":")])
            case "stop":
                pg.event.post(pg.event.Event(pg.QUIT))
            case "save":
                with open("config.json", "wt") as f:
                    json.dump(config, f, indent=4)


    def chat(self, msg, sender=None):
        global config

        print(f"{sender if sender is not None else ''}: {msg}")

        if sender is not None:
            if sender[:sender.find(":")] in config["admins"]:
                if msg[0] == "\\":
                    for p in self.players:
                        self.send_queue.append([p, ["EVENT", "CHAT", f"{username(sender)}:: {msg}"]])
                if msg[0] in "/\\":
                    self.process_command(msg[1:].split(" "), sender, msg[0] == "\\")
                    return

        for p in self.players:
            self.send_queue.append([p, ["EVENT", "CHAT", f"{(username(sender) + ': ') if sender is not None else ''}{msg}"]])

    def run_game(self, gui=False):
        pg.init()
        if gui:
            display = pg.display.set_mode((800, 400))
            font = pg.font.Font(None, 32)
        timer = time.perf_counter()
        ticks = 0
        clock = pg.time.Clock()
        t = 0
        print("game started")
        while True:
            if gui: display.fill(0)

            for event in pg.event.get():
                if event.type == pg.QUIT:
                    self.chat("! STOPPING !")
                    pg.quit()
                    time.sleep(1)
                    for plr in self.players:
                        self.send_queue.append([plr, ["EXIT", "SHUTDOWN", 1]])
                    self.process_command(["save"], "Server")
                    print("game stopped")
                    return
                elif event.type == pg.MOUSEBUTTONDOWN and gui:
                    pos = pg.mouse.get_pos()
                    try:
                        if pos[0] < 400 and pos[1] >= 50:
                            plr = list(self.players.keys())[pos[1]//25-2]
                            if event.button == 1:
                                self.chat(f"{username(plr)} was kicked.")
                                self.send_queue.append([plr, ["EXIT", "KICK", 1]])
                        else:
                            [self.projectiles, self.powerups, self.send_queue][pos[1]//25].clear()
                    except IndexError:
                        pass

            for pw in self.powerups:
                for name, plr in self.players.items():
                    if pw.rect.colliderect([plr.pos[0]-20, plr.pos[1]-20, 40, 40]):
                        self.players[name].powerups[pw.type] = 300
                        self.powerups.remove(pw)
                        break
            if random.random() < 0.001 and len(self.powerups) < config["max_pwups"]:
                self.powerups.append(Powerup())
            for pr in self.projectiles:
                hit = pr.tick(self.players.items())
                if hit is not None:
                    self.projectiles.remove(pr)
                    if hit:
                        p = self.players[hit[0]]
                        if p.iframes > 0:
                            continue
                        p.hp -= 1
                        if p.hp <= 0:
                            self.chat(f"{username(hit[0])} was killed by {username(hit[1])}")
                            p.killer = hit[1]
                            p.deaths += 1
                            self.players[hit[1]].kills += 1
                            p.hp = 3
                            p.respawn_timer = 180
                            p.iframes = 60
                            for pwup in p.powerups.keys():
                                p.powerups[pwup] = 0

                            for plr in self.players:
                                self.send_queue.append([plr,["EVENT", "DEATH", p.name]])

            for name, p in self.players.items():
                if p.tick():
                    self.projectiles.append(Projectile(p.pos, name, np.array(p.mouse_pos) - p.pos))
                    if p.powerups["triple"] > 0:
                        self.projectiles.append(Projectile(p.pos, name, np.array(p.mouse_pos) + [random.random()*100, random.random()*100] - p.pos - (50,50)))
                        self.projectiles.append(Projectile(p.pos, name, np.array(p.mouse_pos) + [random.random()*100, random.random()*100] - p.pos - (50,50)))
                    
            if ticks == 30:
                ticks = 0
                self.tps = 30 / (time.perf_counter() - timer)
                timer = time.perf_counter()
                if not t%600:
                    self.process_command(["save"], "Server")

            if gui:
                text = font.render(f"{self.name}: {round(self.tps, 2)} TPS", True, (255,255*(self.tps>59),255*(self.tps>59)))
                display.blit(text, (0,0))

                pg.draw.line(display, (128,128,128), (395, 0), (395, 400), 5)

                for i, p in enumerate(self.players.keys()):
                    text = font.render(p, True, (255,255,255))
                    display.blit(text, (0, (i+2)*25))
                for i, (item, text) in enumerate(zip([self.projectiles, self.powerups, self.send_queue], \
                                                    ["PROJECTILES", "POWERUPS", "PENDING MSGS"])):
                    text = font.render(f"CLEAR {text} ({len(item)})", True, (255,255,255))
                    display.blit(text, (400, i*25))
            
            t += 1
            ticks += 1
            if gui:
                pg.display.update()
            clock.tick(60)

    def run_server(self):
        ip, port = socket.gethostbyname_ex(socket.gethostname())[2][-1], self.sock.getsockname()[1]
        print(f"server {self.name} started on {ip}:{port}")
        while True:
            conn, addr = self.sock.accept()
            banned = config["banned"]
            if addr[0] in banned:
                send(conn, [["EXIT", "BANNED", 1]], self.executor)
                print(f"banned IP {addr[0]} tried to connect")
                conn.close()
            else:
                self.threads.append(threading.Thread(target=self.serve, args=(conn, addr), daemon=True))
                self.threads[-1].start()

    def serve(self, conn, addr):
        name = None
        buffer = bytes()
        exited = False
        last_communication = time.time()

        while not exited:
            try:
                data = conn.recv(4096)
                buffer += data
                items = buffer.split("\n".encode("utf-8"))
                overflow = len(data) == 4096
                if overflow:
                    print(f"can't keep up with {full_name}")
                    # discard partially sent message
                    items = items[:-1]
                for item in items:
                    if not item: continue
                    last_communication = time.time()
                    msg = json.loads(item)
                    match msg[0]:
                        case "INFO":
                            data = {"timestamp": msg[1],
                                    "name": self.name,
                                    "version": self.VERSION,
                                    "players": len(self.players),
                                    "ping": -1}
                            send(conn, [["INFO", k, v] for k, v in data.items()], self.executor)
                            return
                        case "JOIN":
                            name = msg[1]
                            if len(name) > 20:
                                send(conn, [["EXIT", "NAME"]], self.executor)
                            full_name = f"{addr[0]}:{addr[1]}:{name}"
                            plr = Player(full_name, [960,540])
                            self.players[full_name] = plr
                            self.chat(f"{name} joined.")
                            if msg[3] != self.VERSION and msg[3] not in self.allowed_versions:
                                send(conn, [["EXIT", "VERSION", self.VERSION]], self.executor)
                        case "INPUT":
                            if name is not None:
                                x = msg[1]
                                plr.shooting = x >= 16
                                plr.mvmt = x % 16
                                plr.mouse_pos = msg[2]
                        case "CHAT":
                            self.chat(msg[1], full_name)
                        case "UPDATE":
                            data = {"players": [(p[0], p[1].data_encoded_pos) for p in self.players.items()], 
                                    "pwups": [pw.pos for pw in self.powerups],
                                    "projs": [list(pr.pos // 1) for pr in self.projectiles],
                                    "plr": plr.__dict__}

                            send(conn, [["STATE",k,v] for k, v in data.items()], self.executor)

                            for msg in self.send_queue:
                                if msg[0] == full_name:
                                    send(conn, [msg[1]], self.executor)
                                    self.send_queue.remove(msg)
                                    if msg[1][0] == "EXIT":
                                        time.sleep(0.5)
                                        exited = True
                        case "QUIT":
                            # break while from within nested for
                            exited = True
                        
                if overflow:
                    buffer = buffer.split("\n".encode("utf-8"))[-1]
                    # keep partial msg to be completed later
                else:
                    buffer = bytes()

            except ConnectionResetError:
                # no QUIT message
                if name is not None:
                    self.players.pop(full_name)
                    self.projectiles = [p for p in self.projectiles if p.shooter != full_name]
                    self.chat(f"{name} left.")
                    print(f"{full_name} disconnected suddenly")
                return
            
            if time.time() - last_communication > 5:
                # prevent ghost players after particularly annoying errors
                print(f"{full_name} stopped communicating")
                exited = True
        
        if name is not None:
            self.players.pop(full_name)
            self.projectiles = [p for p in self.projectiles if p.shooter != full_name]
            self.chat(f"{name} left.")
        conn.close()


if __name__ == "__main__":
    config = json.load(open("config.json"))
    parser = argparse.ArgumentParser()
    parser.add_argument("--gui", const=True, nargs="?")
    parser.add_argument("--name", type=str, default=config["name"])
    parser.add_argument("--port", type=int, default=config["port"])
    args = parser.parse_args()
    server = GameServer(args.name, args.port)
    serv_t = threading.Thread(target=server.run_server, daemon=True)
    serv_t.start()
    server.run_game(args.gui)
    time.sleep(0.5)
    print("server stopped")
    pg.quit()
    quit()