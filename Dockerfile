FROM python:3
WORKDIR /usr/src/app
COPY . .
RUN sudo apt install libsdl2-dev
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "-u", "./server.py", "--name", "cloud-1"]
