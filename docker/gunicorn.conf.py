import os

port = int(os.environ.get('APP_PORT', '2112'))
if not 1 <= port <= 65535:
    raise ValueError('APP_PORT must be between 1 and 65535')
bind = f'0.0.0.0:{port}'
workers = 1
threads = 2
timeout = 60
graceful_timeout = 30
accesslog = '-'
errorlog = '-'
capture_output = True
# Docker signals manage this single process; no extra administrative socket.
control_socket_disable = True
# Do not include query strings or form data in access logs.
access_log_format = '%(h)s %(m)s %(U)s %(s)s %(L)s'
