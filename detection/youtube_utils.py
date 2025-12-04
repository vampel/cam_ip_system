# detection/youtube_utils.py - VERSIÓN MEJORADA
import re
import requests
import subprocess
import time

class YouTubeStreamExtractor:
    def __init__(self):
        self.last_request_time = 0
        self.request_delay = 2  # Segundos entre requests
    
    def get_youtube_stream_url(self, youtube_url):
        """Extraer stream directo de URL de YouTube usando múltiples métodos"""
        # Respeta el delay entre requests
        current_time = time.time()
        if current_time - self.last_request_time < self.request_delay:
            time.sleep(self.request_delay - (current_time - self.last_request_time))
        
        self.last_request_time = time.time()
        
        # Método 1: Intentar con yt-dlp
        stream_url = self._try_ytdlp(youtube_url)
        if stream_url:
            return stream_url
        
        # Método 2: Intentar con youtube-dl
        stream_url = self._try_youtube_dl(youtube_url)
        if stream_url:
            return stream_url
        
        # Método 3: Formato directo (para streams conocidos)
        stream_url = self._try_direct_format(youtube_url)
        if stream_url:
            return stream_url
        
        print(f"❌ Todos los métodos fallaron para: {youtube_url}")
        return None
    
    def _try_ytdlp(self, youtube_url):
        """Intentar con yt-dlp"""
        try:
            import yt_dlp
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'format': 'best[height<=480][ext=mp4]',
                'extract_flat': False,
                'noplaylist': True,
            }
            
            print(f"🔍 yt-dlp buscando: {youtube_url}")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
                
                if 'url' in info:
                    print(f"✅ yt-dlp encontró stream directo")
                    return info['url']
                
                # Buscar en formats
                if 'formats' in info:
                    for fmt in info['formats']:
                        if (fmt.get('protocol', '').startswith('http') and 
                            fmt.get('vcodec') != 'none' and
                            fmt.get('height', 0) <= 480):
                            print(f"✅ yt-dlp encontró formato: {fmt.get('format_note', 'N/A')}")
                            return fmt['url']
        
        except ImportError:
            print("⚠️ yt-dlp no está instalado")
        except Exception as e:
            print(f"⚠️ Error en yt-dlp: {e}")
        
        return None
    
    def _try_youtube_dl(self, youtube_url):
        """Intentar con youtube-dl (backup)"""
        try:
            import youtube_dl
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'format': 'best[height<=480]',
            }
            
            print(f"🔍 youtube-dl buscando: {youtube_url}")
            
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
                
                if 'url' in info:
                    print(f"✅ youtube-dl encontró stream")
                    return info['url']
        
        except ImportError:
            print("⚠️ youtube-dl no está instalado")
        except Exception as e:
            print(f"⚠️ Error en youtube-dl: {e}")
        
        return None
    
    def _try_direct_format(self, youtube_url):
        """Intentar con formato directo conocido"""
        try:
            # Extraer video ID
            video_id = self._extract_video_id(youtube_url)
            if not video_id:
                return None
            
            # Para YouTube, intentar formato directo
            direct_urls = [
                f"https://www.youtube.com/watch?v={video_id}",
                f"http://www.youtube.com/watch?v={video_id}",
            ]
            
            print(f"🔍 Probando formato directo para: {video_id}")
            
            # Intentar cada URL
            for url in direct_urls:
                try:
                    # Pequeño test de conexión
                    cap = cv2.VideoCapture(url)
                    if cap.isOpened():
                        cap.release()
                        print(f"✅ Formato directo funciona: {url}")
                        return url
                    cap.release()
                except:
                    pass
            
        except Exception as e:
            print(f"⚠️ Error en formato directo: {e}")
        
        return None
    
    def _extract_video_id(self, url):
        """Extraer video ID de URL de YouTube"""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtube\.com/embed/|youtu\.be/)([a-zA-Z0-9_-]{11})',
            r'^([a-zA-Z0-9_-]{11})$'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

# Para probar directamente
if __name__ == "__main__":
    import cv2
    
    extractor = YouTubeStreamExtractor()
    
    # URLs de prueba
    test_urls = [
        "https://www.youtube.com/embed/DjdUEyjx8GM",
        "https://www.youtube.com/watch?v=DjdUEyjx8GM",
        "https://youtu.be/DjdUEyjx8GM",
        "DjdUEyjx8GM"  # Solo el ID
    ]
    
    for url in test_urls:
        print(f"\n🔍 Probando: {url}")
        stream_url = extractor.get_youtube_stream_url(url)
        
        if stream_url:
            print(f"✅ Stream obtenido: {stream_url[:100]}...")
            
            # Probar si OpenCV puede abrirlo
            cap = cv2.VideoCapture(stream_url)
            if cap.isOpened():
                print(f"✅ OpenCV puede abrir el stream")
                cap.release()
            else:
                print(f"❌ OpenCV NO puede abrir el stream")
        else:
            print(f"❌ No se pudo obtener stream")