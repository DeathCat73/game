import cProfile

cProfile.run(open("client.py", "rt").read(), sort=2)