# game  
simple multiplayer game using pygame  

### To run a server:  

Have **banned.json** in the same folder as **server.py**  
**banned.json** should be a list of IPs to block  
Run `python3 server.py (--gui) --name [name = 'server'] --port [port = 38491]` 
- `--gui`: Opens a window containing some controls. 
- `--name`: Names the server. Doesn't do much (yet). 
- `--port`: Changes the port from the default 38491
The server will then start on the specified port  

### To run a server in a Docker container:  

Run `docker compose up`  

### To use a server:  

Logs are printed to the console (for now).  
Close the console in any way to close the server.  
- It will close suddenly but the client should handle it.

**With the GUI**:

Click on player names on the left to kick them.  
- The server name is not a player.  

Click on text on the right to clear lists if they get too big.  
To close the server, close the window:  
- A warning will be sent in the server's chat immediately  
- After 1 second, the game logic will stop and all players will be kicked  
- after another 0.5 seconds, the server and any remaining connections will close  

### To run the client:  
  
Run `python3 client.py`  
**¹Command-line arguments are deprecated**  

### To use the client:  

To join a server, enter:
- Your username (pre-fill with `--name`)¹
- The IP of the server (pre-fill with `--host`)¹
- The port the server runs on (pre-fill with `--port`)¹
  - This is usually 38491

Once in game:
- WASD to move
- Click to shoot
- T to chat
  - ENTER to send
  - ESC to cancel
- Health is in the top left
- Rainbow squares are power-ups
- ESC to quit