import socket

def check_port(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0

ports = {
    8099: "Dashboard Server",
    8088: "Preview Server",
    5000: "Payment Server"
}

for port, name in ports.items():
    if check_port(port):
        print(f"[OK] {name} is listening on port {port}")
    else:
        print(f"[FAIL] {name} is NOT listening on port {port}")
