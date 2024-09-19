# game
simple multiplayer game using pygame

### To run a server:

Have banned.json in the same folder as server.py  
banned.json should be a list of IPs to block  
Run server.py  
The server will start on port 38491

### To use a server:

Click on player names to kick them  
To close the server:  
- Close the window  
- Press enter in the console  
- IF DONE IN THE WRONG ORDER IT WILL NOT WORK  
- YOU WILL HAVE TO KILL THE PROCESS  

### To run the client:

Have config.json in the same folder as client.py  
config.json should look like this:  
`{  
    "HOST": "host IP",  
    "PORT": port as integer (38491 unless otherwise specified),  
    "NAME" "your username"  
}`  
If config.json is not present in the same folder as client.py, it will be created  
run client.py

### To use the client:

WASD to move  
Click to shoot  
T to chat  
- ENTER to send  
- ESC to cancel  
Health is in the top left  
Rainbow squares are power-ups  
ESC to quit