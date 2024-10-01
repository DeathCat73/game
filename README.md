# game  
simple multiplayer game using pygame  

### To run a server:  

Have **banned.json** in the same folder as **server.py**  
**banned.json** should be a list of IPs to block  
Run `python3 server.py (--gui) --name [name = 'server'] --port [port = 38491]`  
The server will start on the specified port or 38491 by default  
A GUI window will open if the `--gui` flag is set  

### To run a server in a Docker container:  

Run `docker compose up`  

### To use a server:  

Click on player names on the left to kick them  
Click on text on the right to clear lists if they get too big  
To close the server, close the window:  
- A warning will be sent in the server's chat immediately  
- After 1 second, the game logic will stop and all players will be kicked  
- after another 0.5 seconds, the server and any remaining connections will close  

### To run the client:  
  
run `python3 client.py --name [your username] --host [server IP = 127.0.0.1] --port [server port = 38491] `  

### To use the client:  

WASD to move  
Click to shoot  
T to chat  
- ENTER to send  
- ESC to cancel  

Health is in the top left  
Rainbow squares are power-ups  
ESC to quit