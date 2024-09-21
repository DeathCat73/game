import socket
import threading
import random
import json
import pygame as pg
import math
import numpy as np
import time


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
        for name, pos in players:
            if name == self.shooter:
                continue
            rect = pg.Rect(pos[0]-20, pos[1]-20, 40, 40)
            if self.rect.colliderect(rect):
                return name, self.shooter
            

def username(name: str):
    i1 = name.index(":")
    i2 = name.index(":", i1+1)
    return name[i2+1:]


def send(conn, msg):
    t = threading.Thread(target=conn.sendall, args=[("\n"+json.dumps(msg)).encode("utf-8")], daemon=True)
    t.start()


class GameServer:
    def __init__(self, port=38491):
        self.VERSION = 1.1
        self.threads = []
        self.sock = socket.create_server(("", port))
        self.players = dict()
        self.chat_hist = ["SERVER: Started."]
        self.projectiles = []
        self.powerups = []
        self.hit_queue = []
        self.pw_queue = []
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
                    if pos[0] < 400:
                        plr = list(self.players.keys())[pos[1]//25-1]
                        if event.button == 1:
                            self.chat(f"{username(plr)} was kicked.")
                            self.send_queue.append([plr, ["KICK", 1]])
                    else:
                        [self.projectiles, self.powerups, self.hit_queue, self.pw_queue, self.send_queue, self.chat_hist][pos[1]//25].clear()
                        if not self.chat_hist:
                            self.chat("SERVER: Chat cleared.")

            for pw in self.powerups:
                for name, pos in self.players.items():
                    if pw.rect.colliderect([pos[0]-20, pos[1]-20, 40, 40]):
                        self.pw_queue.append((name, pw.type))
                        self.powerups.remove(pw)
                        break
            if random.random() < 0.001:
                self.powerups.append(Powerup())
            for pr in self.projectiles:
                hit = pr.tick(self.players.items())
                if hit is not None:
                    if hit:
                        self.hit_queue.append(hit)
                    self.projectiles.remove(pr)

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
            for i, (item, text) in enumerate(zip([self.projectiles, self.powerups, self.hit_queue, self.pw_queue, self.send_queue, self.chat_hist], \
                                                 ["PROJECTILES", "POWERUPS", "PENDING HITS", "PENDING PW HITS", "PENDING MSGS", "CHAT"])):
                text = font.render(f"CLEAR {text} ({len(item)})", True, (255,255,255))
                display.blit(text, (400, i*25))
            
            t += 1
            ticks += 1
            pg.display.update()
            clock.tick(60)

    def run_server(self):
        s = socket.socket()
        s.connect(("8.8.8.8", 53))
        ip = s.getsockname()
        s.close()
        print(f"server started on {ip[0]}:{ip[1]}")
        while True:
            conn, addr = self.sock.accept()
            banned = json.load(open("banned.json", "rt"))
            if addr[0] in banned:
                send(conn, ["BANNED", 1])
                print(f"banned ip {addr[0]} tried to join")
                conn.close()
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
                            self.players[full_name] = msg[2]
                            self.chat(f"{name} joined.")
                            print(f"{full_name} joined")
                            if msg[3] != self.VERSION:
                                send(conn, ["VERSION", self.VERSION])
                        case "POS":
                            if full_name is not None:
                                self.players[full_name] = msg[1]
                        case "CHAT":
                            self.chat(f"{name}: {msg[1]}")
                        case "SHOOT":
                            if len(self.projectiles) >= 200:
                                continue
                            offset = np.array(msg[1]) - self.players[full_name]
                            self.projectiles.append(Projectile(self.players[full_name], full_name, offset))
                            if msg[2]["triple"] > 0:
                                self.projectiles.append(Projectile(self.players[full_name], full_name, offset + random.choices(range(-50, 51), k=2)))
                                self.projectiles.append(Projectile(self.players[full_name], full_name, offset + random.choices(range(-50, 51), k=2)))
                        case "HIT":
                            for h in self.hit_queue:
                                if h[0] == full_name:
                                    self.hit_queue.remove(h)
                        case "PW_HIT":
                            for h in self.pw_queue:
                                if h[0] == full_name:
                                    self.pw_queue.remove(h)
                        case "DIED":
                            self.chat(f"{name} was killed by {username(msg[1])}")
                        case "UPDATE":
                            data = {"players": self.players, 
                                    "chat": self.chat_hist[:30],
                                    "pwups": [pw.pos for pw in self.powerups],
                                    "projs": [list(pr.pos // 1) for pr in self.projectiles],
                                    "hits": self.hit_queue,
                                    "pw_hits": self.pw_queue}

                            for k, v in data.items():
                                msg = [k,v]
                                send(conn, msg)

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