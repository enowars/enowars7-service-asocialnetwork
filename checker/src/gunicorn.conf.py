import multiprocessing

worker_class = "uvicorn.workers.UvicornWorker"
workers = min(4, multiprocessing.cpu_count())
bind = "0.0.0.0:8000"
timeout = 90
keepalive = 3600
max_requests = 1000
max_requests_jitter = 100
preload_app = True