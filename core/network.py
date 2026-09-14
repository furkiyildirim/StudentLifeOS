import socket

def check_internet_connection(timeout=3):
    """Google DNS sunucusuna bağlanarak aktif internet bağlantısını test eder."""
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
        return True
    except socket.error:
        return False