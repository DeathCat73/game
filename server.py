import socket
import threading
import random
import json
import pygame as pg
import math
import numpy as np
import time


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
    
    def tick(self):
        for pwrup in self.powerups.keys():
            self.powerups[pwrup] -= 1
        self.cooldown -= 1
        self.iframes -= 1
        self.respawn_timer -= 1
        if self.shooting and self.cooldown <= 0:
            self.cooldown = self.rate
            if self.powerups["rapid"] > 0:
                self.cooldown /= 2
            return True
        return False


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


def send(conn, msgs):
    data = ""
    for m in msgs:
        data += "\n"+json.dumps(m)
    t = threading.Thread(target=conn.sendall, args=[data.encode("utf-8")], daemon=True)
    t.start()


class GameServer:
    def __init__(self, port=38491):
        self.VERSION = 1.2
        self.threads = []
        self.sock = socket.create_server(("", port))
        self.players = dict()
        self.chat_hist = ["SERVER: Started."]
        self.projectiles = []
        self.powerups = []
        self.send_queue = []

    def chat(self, msg):
        print(msg)
        self.chat_hist.insert(0,msg)
        while len("  ".join(self.chat_hist)) > 3500:
            self.chat_hist = self.chat_hist[:-1]

    def run_game(self):
        pg.init()
        display = pg.display.set_mode((800, 400))
        clock = pg.time.Clock()
        font = pg.font.Font(None, 32)
        t = 0
        ticks = 0
        tps = 0
        timer = time.perf_counter()
        print("game started")
        while True:
            display.fill(0)

            for event in pg.event.get():
                if event.type == pg.QUIT:
                    self.chat("! STOPPING !")
                    pg.quit()
                    time.sleep(1)
                    for plr in self.players:
                        self.send_queue.append([plr, ["SHUTDOWN", 1]])
                    print("game stopped")
                    return
                elif event.type == pg.MOUSEBUTTONDOWN:
                    pos = pg.mouse.get_pos()
                    try:
                        if pos[0] < 400:
                            plr = list(self.players.keys())[pos[1]//25-1]
                            if event.button == 1:
                                self.chat(f"{username(plr.name)} was kicked.")
                                self.send_queue.append([plr.name, ["KICK", 1]])
                        else:
                            [self.projectiles, self.powerups, self.send_queue, self.chat_hist][pos[1]//25].clear()
                            if not self.chat_hist:
                                self.chat("SERVER: Chat cleared.")
                    except IndexError:
                        pass

            for pw in self.powerups:
                for name, plr in self.players.items():
                    if pw.rect.colliderect([plr.pos[0]-20, plr.pos[1]-20, 40, 40]):
                        self.players[name].powerups[pw.type] = 300
                        self.powerups.remove(pw)
                        break
            if random.random() < 0.001:
                self.powerups.append(Powerup())
            for pr in self.projectiles:
                hit = pr.tick(self.players.items())
                if hit is not None:
                    if hit:
                        p = self.players[hit[0]]
                        p.hp -= 1
                        if p.hp <= 0:
                            self.chat(f"{hit[0]} was killed by {hit[1]}")
                            p.killer = hit[1]
                            p.deaths += 1
                            self.players[hit[1]].kills += 1
                            p.hp = 3
                            p.respawn_timer = 180
                            p.iframes = 240
                            for pwup in p.powerups.keys():
                                p.powerups[pwup] = 0
                    self.projectiles.remove(pr)

            for name, p in self.players.items():
                if p.tick():
                    self.projectiles.append(Projectile(p.pos, name, np.array(p.mouse_pos) - p.pos))
                    if p.powerups["triple"] > 0:
                        self.projectiles.append(Projectile(p.pos, name, np.array(p.mouse_pos) + [random.random()*100, random.random()*100] - p.pos - (50,50)))
                        self.projectiles.append(Projectile(p.pos, name, np.array(p.mouse_pos) + [random.random()*100, random.random()*100] - p.pos - (50,50)))

            if ticks == 30:
                ticks = 0
                tps = 30 / (time.perf_counter() - timer)
                timer = time.perf_counter()
            text = font.render(f"{round(tps, 2)} TPS", True, (255,255*(tps>59),255*(tps>59)))
            display.blit(text, (0,0))

            pg.draw.line(display, (128,128,128), (395, 0), (395, 400), 5)

            for i, p in enumerate(self.players.keys()):
                text = font.render(p, True, (255,255,255))
                display.blit(text, (0, (i+1)*25))
            for i, (item, text) in enumerate(zip([self.projectiles, self.powerups, self.send_queue, self.chat_hist], \
                                                 ["PROJECTILES", "POWERUPS", "PENDING MSGS", "CHAT"])):
                text = font.render(f"CLEAR {text} ({len(item)})", True, (255,255,255))
                display.blit(text, (400, i*25))
            
            t += 1
            ticks += 1
            pg.display.update()
            clock.tick(60)

    def run_server(self):
        ip, port = socket.gethostbyname_ex(socket.gethostname())[2][-1], self.sock.getsockname()[1]
        print(f"server started on {ip}:{port}")
        while True:
            conn, addr = self.sock.accept()
            banned = json.load(open("banned.json", "rt"))
            if addr[0] in banned:
                send(conn, ["BANNED", 1])
                print(f"banned ip {addr[0]} tried to join")
                conn.close()
            else:
                self.threads.append(threading.Thread(target=self.serve, args=(conn, addr), daemon=True))
                self.threads[-1].start()

    def serve(self, conn, addr):
        name = None
        while True:
            try:
                data = conn.recv(4096).split("\n".encode("utf-8"))
                if len(data) == 4096:
                    print(f"can't keep up with {full_name}")
                for msg in map(json.loads, data[1:]):
                    match msg[0]:
                        case "JOIN":
                            name = msg[1]
                            full_name = f"{addr[0]}:{addr[1]}:{name}"
                            plr = Player(full_name, [960,540])
                            self.players[full_name] = plr
                            self.chat(f"{name} joined.")
                            print(f"{full_name} joined")
                            if msg[3] != self.VERSION:
                                send(conn, ["VERSION", self.VERSION])
                        case "INPUT":
                            if full_name is not None:
                                x = msg[1]
                                plr.shooting = x >= 16
                                x %= 16
                                if x >= 8:
                                    plr.pos[1] -= 5
                                x %= 8
                                if x >= 4:
                                    plr.pos[0] -= 5
                                x %= 4
                                if x >= 2:
                                    plr.pos[1] += 5
                                x %= 2
                                if x:
                                    plr.pos[0] += 5

                                plr.mouse_pos = msg[2]
                        case "CHAT":
                            self.chat(f"{name}: {msg[1]}")
                        case "UPDATE":
                            data = {"players": [(p[0], p[1].pos) for p in self.players.items()], 
                                    "chat": self.chat_hist[:30],
                                    "pwups": [pw.pos for pw in self.powerups],
                                    "projs": [list(pr.pos // 1) for pr in self.projectiles],
                                    "plr": plr.__dict__}

                            send(conn, [[k,v] for k, v in data.items()])

                            for msg in self.send_queue:
                                if msg[0] == full_name:
                                    send(conn, msg[1])
                                    self.send_queue.remove(msg)
                        case "QUIT":
                            conn.close()
                            self.players.pop(full_name)
                            self.chat(f"{name} left.")
                            print(f"{full_name} disconnected")
                            return
                            
            except json.JSONDecodeError:
                pass
            except ConnectionResetError:
                self.players.pop(full_name)
                self.chat(f"{name} left.")
                print(f"{full_name} disconnected suddenly")
                return


if __name__ == "__main__":
    server = GameServer()
    serv_t = threading.Thread(target=server.run_server, daemon=True)
    serv_t.start()
    server.run_game()
    time.sleep(0.5)
    print("server stopped")
    pg.quit()
    quit()