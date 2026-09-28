import socket

def check_internet_connection(timeout=3):
    """Check whether the device has an active internet connection."""
    try:
        # Birinci Tercih: Cloudflare DNS (Dünya çapında en hızlı ve kesintisiz sunucu)
        # HTTP isteği indirmek yerine sadece 53. porta ufak bir sinyal gönderilir.
        socket.setdefaulttimeout(timeout)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(("1.1.1.1", 53))
        return True
    except OSError:
        try:
            # Yedek Tercih: Google DNS (Eğer Cloudflare o an yanıt vermezse)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(("8.8.8.8", 53))
            return True
        except OSError:
            # Her ikisi de başarısız olursa cihaz gerçekten çevrimdışıdır
            return False