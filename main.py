import os
import sys
import time
import logging
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from yt_dlp import YoutubeDL
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TCON, TRCK, TDRC, APIC
import requests
from urllib.parse import quote
import json
from datetime import datetime
import re
import getpass
import browser_cookie3
import tempfile
import subprocess

# Configuración
SPOTIFY_CLIENT_ID = 'XXXX'
SPOTIFY_CLIENT_SECRET = 'XXX'
SPOTIFY_REDIRECT_URI = 'http://127.0.0.1:8888/callback'
SPOTIFY_USERNAME = 'XXX'

# Configuración para cookies de YouTube
YT_COOKIES_FILE = 'youtube_cookies.txt'

# Scope necesario para acceder a playlists privadas
SCOPE = 'playlist-read-private'

# Configurar logging
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('spotify_downloader.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

class YouTubeAuthenticator:
    """Maneja la autenticación con YouTube de forma más robusta"""
    
    def __init__(self):
        self.cookies_file = YT_COOKIES_FILE
        self.authenticated = False
        self.auth_method = None
        
    def extract_cookies_from_browser(self):
        """Extrae cookies directamente del navegador (método más confiable)"""
        print("\nExtrayendo cookies del navegador...")
        browsers = [
            ('Chrome', browser_cookie3.chrome),
            ('Firefox', browser_cookie3.firefox),
            ('Edge', browser_cookie3.edge),
            ('Opera', browser_cookie3.opera),
            ('Brave', browser_cookie3.brave),
            ('Safari', browser_cookie3.safari),
        ]
        
        for browser_name, browser_func in browsers:
            try:
                print(f"Intentando con {browser_name}...")
                cj = browser_func(domain_name='youtube.com')
                if cj:
                    # Verificar si hay cookies válidas de YouTube
                    youtube_cookies = []
                    for cookie in cj:
                        if 'youtube.com' in cookie.domain or '.youtube.com' in cookie.domain:
                            youtube_cookies.append(cookie)
                    
                    if youtube_cookies:
                        # Guardar cookies en archivo temporal
                        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
                            for cookie in youtube_cookies:
                                f.write(f"{cookie.domain}\t{'TRUE' if cookie.domain.startswith('.') else 'FALSE'}\t{cookie.path}\t{'TRUE' if cookie.secure else 'FALSE'}\t{cookie.expires or '0'}\t{cookie.name}\t{cookie.value}\n")
                            temp_cookie_file = f.name
                        
                        # Verificar si las cookies funcionan
                        if self.verify_cookies(temp_cookie_file):
                            # Copiar al archivo permanente
                            import shutil
                            shutil.copy2(temp_cookie_file, self.cookies_file)
                            os.unlink(temp_cookie_file)
                            logger.info(f"Cookies extraídas exitosamente de {browser_name}")
                            return True
                        else:
                            os.unlink(temp_cookie_file)
                            
            except Exception as e:
                print(f"Error con {browser_name}: {str(e)}")
                continue
                
        return False

    def verify_cookies(self, cookie_file):
        """Verifica si las cookies son válidas"""
        try:
            ydl_opts = {
                'cookiefile': cookie_file,
                'quiet': True,
                'extract_flat': True,
                'no_warnings': True,
            }
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info('https://www.youtube.com/watch?v=jNQXAC9IVRw', download=False)
                if info:
                    return True
        except Exception as e:
            logger.warning(f"Cookies no válidas: {str(e)}")
        return False

    def manual_cookies_upload(self):
        """Guía al usuario para subir manualmente el archivo de cookies"""
        print("\n" + "="*60)
        print("SUBIDA MANUAL DE ARCHIVO DE COOKIES")
        print("="*60)
        print("\nPara obtener un archivo de cookies válido:")
        print("1. Instala la extensión 'cookies.txt' en Firefox o")
        print("   'Get cookies.txt LOCALLY' en Chrome")
        print("2. Ve a youtube.com y asegúrate de estar logueado")
        print("3. Usa la extensión para exportar las cookies")
        print("4. Sube el archivo descargado")
        
        while True:
            try:
                file_path = input("\nRuta al archivo de cookies (o Enter para cancelar): ").strip()
                if not file_path:
                    return False
                
                if not os.path.exists(file_path):
                    print("❌ El archivo no existe. Verifica la ruta.")
                    continue
                
                # Verificar el formato del archivo
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if 'youtube.com' not in content and '.youtube.com' not in content:
                        print("❌ El archivo no parece contener cookies de YouTube")
                        retry = input("¿Quieres intentar con otro archivo? (s/n): ").lower()
                        if retry != 's':
                            return False
                        continue
                
                # Verificar si las cookies funcionan
                if self.verify_cookies(file_path):
                    import shutil
                    shutil.copy2(file_path, self.cookies_file)
                    print("✅ Cookies válidas guardadas correctamente")
                    return True
                else:
                    print("❌ Las cookies no son válidas o han expirado")
                    retry = input("¿Quieres intentar con otro archivo? (s/n): ").lower()
                    if retry != 's':
                        return False
                        
            except Exception as e:
                print(f"❌ Error: {str(e)}")
                retry = input("¿Quieres intentar de nuevo? (s/n): ").lower()
                if retry != 's':
                    return False

    def setup_with_credentials_advanced(self):
        """Configuración avanzada con credenciales usando sesión persistente"""
        print("\n" + "="*60)
        print("AUTENTICACIÓN CON CREDENCIALES AVANZADA")
        print("="*60)
        print("\nEste método creará una sesión persistente.")
        
        try:
            # Crear un archivo de configuración para yt-dlp
            config_content = """# Configuración para YouTube
# Este archivo contiene las credenciales para yt-dlp
"""
            
            with open('yt_dlp_config.txt', 'w') as f:
                f.write(config_content)
            
            print("Por favor ingresa tus credenciales de Google:")
            username = input("Email o usuario: ").strip()
            password = getpass.getpass("Contraseña: ")
            
            if not username or not password:
                print("Se requieren ambos campos.")
                return False
            
            # Configuración para yt-dlp con autenticación
            ydl_opts = {
                'username': username,
                'password': password,
                'quiet': False,
                'no_warnings': False,
                'cookiefile': self.cookies_file,  # Guardar cookies para sesión futura
            }
            
            print("\n🔐 Iniciando sesión en YouTube...")
            try:
                with YoutubeDL(ydl_opts) as ydl:
                    # Intentar acceder a contenido que requiere login
                    info = ydl.extract_info('https://www.youtube.com/feed/library', download=False)
                    
                if os.path.exists(self.cookies_file):
                    print("✅ Sesión guardada correctamente en cookies.txt")
                    return True
                else:
                    print("❌ No se pudo guardar la sesión")
                    return False
                    
            except Exception as e:
                if "Two-factor authentication" in str(e):
                    print("\n🔐 Tu cuenta tiene autenticación de dos factores habilitada.")
                    print("Por favor usa el método de cookies del navegador.")
                elif "Wrong password" in str(e) or "Invalid credentials" in str(e):
                    print("❌ Credenciales incorrectas")
                else:
                    print(f"❌ Error de autenticación: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"Error en autenticación avanzada: {str(e)}")
            return False

    def setup_authentication(self):
        """Configura la autenticación con múltiples opciones robustas"""
        print("\n" + "="*60)
        print("CONFIGURACIÓN DE AUTENTICACIÓN YOUTUBE")
        print("="*60)
        
        # Opción 1: Verificar cookies existentes
        if os.path.exists(self.cookies_file) and self.verify_cookies(self.cookies_file):
            print("✅ Se encontraron cookies válidas existentes")
            self.authenticated = True
            self.auth_method = "existing_cookies"
            return True
        
        # Mostrar opciones al usuario
        print("\nSelecciona un método de autenticación:")
        print("1. 🚀 AUTOMÁTICO - Extraer cookies del navegador (Recomendado)")
        print("2. 📁 MANUAL - Subir archivo de cookies")
        print("3. 🔐 AVANZADO - Iniciar sesión con credenciales")
        print("4. ⏩ CONTINUAR - Sin autenticación (puede fallar con contenido restringido)")
        
        while True:
            try:
                choice = input("\nSelecciona una opción (1-4): ").strip()
                
                if choice == '1':
                    if self.extract_cookies_from_browser():
                        self.authenticated = True
                        self.auth_method = "browser_extraction"
                        print("✅ Autenticación automática exitosa!")
                        return True
                    else:
                        print("❌ No se pudieron extraer cookies automáticamente")
                        continue
                        
                elif choice == '2':
                    if self.manual_cookies_upload():
                        self.authenticated = True
                        self.auth_method = "manual_upload"
                        return True
                    else:
                        continue
                        
                elif choice == '3':
                    if self.setup_with_credentials_advanced():
                        self.authenticated = True
                        self.auth_method = "credentials"
                        return True
                    else:
                        continue
                        
                elif choice == '4':
                    print("⚠️ Continuando sin autenticación...")
                    self.authenticated = False
                    self.auth_method = "none"
                    return True
                    
                else:
                    print("❌ Opción inválida. Por favor selecciona 1-4.")
                    
            except KeyboardInterrupt:
                print("\nOperación cancelada por el usuario")
                return False
            except Exception as e:
                print(f"❌ Error: {str(e)}")
                continue

    def get_auth_options(self):
        """Retorna las opciones de autenticación para yt-dlp"""
        if self.authenticated and os.path.exists(self.cookies_file):
            return {
                'cookiefile': self.cookies_file,
                'no_check_certificate': True,
                'ignoreerrors': False,
            }
        else:
            return {}

class SpotifyDownloader:
    def __init__(self):
        try:
            self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET,
                redirect_uri=SPOTIFY_REDIRECT_URI,
                scope=SCOPE,
                username=SPOTIFY_USERNAME
            ))
            logger.info("Autenticación con Spotify exitosa")
            
            # Inicializar autenticador de YouTube
            self.yt_auth = YouTubeAuthenticator()
            
        except Exception as e:
            logger.error(f"Error en autenticación: {str(e)}")
            raise

    def setup_youtube_auth(self):
        """Configura la autenticación de YouTube"""
        return self.yt_auth.setup_authentication()

    def clean_filename(self, filename):
        """
        Limpia el nombre de archivo removiendo caracteres no válidos
        y reemplazando espacios con guiones bajos
        """
        # Caracteres no permitidos en nombres de archivo
        invalid_chars = '<>:"/\\|?*\'"'
        
        # Remover caracteres inválidos
        for char in invalid_chars:
            filename = filename.replace(char, '')
        
        # Reemplazar múltiples espacios con un solo guión bajo
        filename = re.sub(r'\s+', '_', filename)
        
        # Remover guiones bajos al inicio y final
        filename = filename.strip('_')
        
        # Limitar longitud del nombre (máximo 100 caracteres)
        if len(filename) > 100:
            filename = filename[:100]
        
        return filename

    def get_playlist_tracks(self, playlist_id):
        """Obtiene todas las canciones de una playlist"""
        try:
            results = self.sp.playlist_tracks(playlist_id)
            tracks = results['items']
            
            while results['next']:
                results = self.sp.next(results)
                tracks.extend(results['items'])
            
            logger.info(f"Se encontraron {len(tracks)} canciones en la playlist")
            return tracks
        except Exception as e:
            logger.error(f"Error al obtener tracks: {str(e)}")
            raise

    def search_youtube(self, track_name, artist_name):
        """Busca el video en YouTube con autenticación si está disponible"""
        search_query = f"{track_name} {artist_name} official audio"
        
        # Configuración base para yt-dlp
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'force_json': True,
            'no_warnings': True,
        }
        
        # Añadir opciones de autenticación si están disponibles
        auth_options = self.yt_auth.get_auth_options()
        ydl_opts.update(auth_options)
        
        try:
            with YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(
                    f"ytsearch1:{search_query}",
                    download=False
                )
                if result['entries']:
                    video_url = result['entries'][0]['url']
                    logger.info(f"Video encontrado: {video_url}")
                    return video_url
                else:
                    logger.warning(f"No se encontraron videos para: {search_query}")
                    return None
        except Exception as e:
            error_msg = str(e)
            if "Sign in to confirm you're not a bot" in error_msg or "age-restricted" in error_msg:
                logger.warning(f"Video restringido que requiere autenticación: {track_name}")
            elif "Private video" in error_msg:
                logger.warning(f"Video privado: {track_name}")
            else:
                logger.error(f"Error en búsqueda YouTube: {search_query} - {error_msg}")
            return None

    def download_audio_advanced(self, url, output_path, metadata):
        """Descarga audio usando estrategias avanzadas para evitar el problema SABR"""
        
        # Estrategia 1: Usar yt-dlp con configuración específica para SABR
        ydl_opts_sabr = {
            'format': 'bestaudio/best',
            'outtmpl': output_path,
            'quiet': False,
            'no_warnings': False,
            'ignoreerrors': False,
            'retries': 10,
            'fragment_retries': 10,
            'skip_unavailable_fragments': True,
            'extractaudio': True,
            'audioformat': 'mp3',
            'audioquality': '0',  # Mejor calidad
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            # Configuraciones específicas para SABR
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['configs', 'webpage']
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Sec-Fetch-Mode': 'navigate',
            }
        }
        
        # Añadir autenticación si está disponible
        auth_options = self.yt_auth.get_auth_options()
        ydl_opts_sabr.update(auth_options)
        
        # Estrategia 2: Formatos alternativos específicos
        format_strategies = [
            'bestaudio[ext=m4a]/bestaudio/best',
            'bestaudio/best',
            'worstaudio/worst',
            'm4a/bestaudio/best',
            'mp3/best',
            'best[height<=480]',  # Formatos de video con audio
            'worst[height<=480]',
        ]
        
        last_error = None
        
        # Intentar con diferentes estrategias de formato
        for format_strategy in format_strategies:
            try:
                ydl_opts_sabr['format'] = format_strategy
                logger.info(f"🔧 Intentando estrategia de formato: {format_strategy}")
                
                with YoutubeDL(ydl_opts_sabr) as ydl:
                    ydl.download([url])
                
                # Verificar si el archivo se descargó
                downloaded_path = self.find_downloaded_file(output_path)
                if downloaded_path:
                    # Convertir a MP3 si es necesario
                    final_path = self.ensure_mp3_format(downloaded_path, output_path + '.mp3')
                    if final_path and os.path.exists(final_path):
                        self.add_metadata(final_path, metadata)
                        logger.info(f"✅ Descarga exitosa con formato: {format_strategy}")
                        return True
                        
            except Exception as e:
                last_error = str(e)
                logger.warning(f"❌ Estrategia {format_strategy} falló: {last_error}")
                continue
        
        # Estrategia 3: Usar descarga directa sin post-processing
        try:
            logger.info("🔄 Intentando descarga directa sin post-processing...")
            ydl_opts_direct = {
                'format': 'bestaudio/best',
                'outtmpl': output_path + '.%(ext)s',
                'quiet': False,
                'no_warnings': False,
                'retries': 10,
                'extractaudio': False,  # No extraer audio inmediatamente
                'postprocessors': [],   # Sin post-processing
            }
            ydl_opts_direct.update(auth_options)
            
            with YoutubeDL(ydl_opts_direct) as ydl:
                info = ydl.extract_info(url, download=True)
                downloaded_file = ydl.prepare_filename(info)
            
            if os.path.exists(downloaded_file):
                # Convertir manualmente a MP3
                mp3_path = output_path + '.mp3'
                if self.convert_to_mp3(downloaded_file, mp3_path):
                    os.remove(downloaded_file)  # Limpiar archivo original
                    self.add_metadata(mp3_path, metadata)
                    logger.info("✅ Descarga directa exitosa")
                    return True
                    
        except Exception as e:
            last_error = str(e)
            logger.warning(f"❌ Descarga directa falló: {last_error}")
        
        # Estrategia 4: Usar yt-dlp con extractor alternativo
        try:
            logger.info("🔄 Intentando con extractor alternativo...")
            ydl_opts_alt = {
                'format': 'bestaudio/best',
                'outtmpl': output_path,
                'quiet': False,
                'no_warnings': False,
                'retries': 10,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'extractor_args': {'youtube': {'player_client': ['android']}},
            }
            ydl_opts_alt.update(auth_options)
            
            with YoutubeDL(ydl_opts_alt) as ydl:
                ydl.download([url])
            
            downloaded_path = self.find_downloaded_file(output_path)
            if downloaded_path:
                self.add_metadata(downloaded_path, metadata)
                logger.info("✅ Descarga con extractor alternativo exitosa")
                return True
                
        except Exception as e:
            last_error = str(e)
            logger.warning(f"❌ Extractor alternativo falló: {last_error}")
        
        logger.error(f"❌ Todas las estrategias fallaron para: {metadata['title']}")
        if last_error:
            logger.error(f"Último error: {last_error}")
        return False

    def find_downloaded_file(self, base_path):
        """Encuentra el archivo descargado con cualquier extensión"""
        possible_extensions = ['.mp3', '.m4a', '.webm', '.opus', '.mkv', '.mp4']
        for ext in possible_extensions:
            path = base_path + ext
            if os.path.exists(path):
                return path
        return None

    def ensure_mp3_format(self, input_path, output_path):
        """Asegura que el archivo esté en formato MP3"""
        if input_path.endswith('.mp3'):
            return input_path
        
        if self.convert_to_mp3(input_path, output_path):
            if input_path != output_path and os.path.exists(input_path):
                os.remove(input_path)
            return output_path
        return None

    def convert_to_mp3(self, input_path, output_path):
        """Convierte un archivo de audio a MP3 usando FFmpeg"""
        try:
            cmd = [
                'ffmpeg', '-i', input_path,
                '-codec:a', 'libmp3lame',
                '-qscale:a', '2',
                '-y',  # Sobrescribir si existe
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                logger.info(f"✅ Conversión exitosa: {input_path} -> {output_path}")
                return True
            else:
                logger.error(f"❌ Error en conversión FFmpeg: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error al convertir a MP3: {str(e)}")
            return False

    def download_audio(self, url, output_path, metadata):
        """Wrapper para la descarga de audio con manejo de errores mejorado"""
        try:
            return self.download_audio_advanced(url, output_path, metadata)
        except Exception as e:
            logger.error(f"❌ Error crítico en download_audio: {str(e)}")
            return False

    def add_metadata(self, file_path, metadata):
        """Añade metadata ID3 al archivo MP3"""
        try:
            # Asegurarse de que el archivo existe
            if not os.path.exists(file_path):
                logger.error(f"Archivo no encontrado para metadata: {file_path}")
                return
            
            try:
                audio = MP3(file_path, ID3=ID3)
            except:
                audio = MP3(file_path)
                audio.add_tags()
            
            # Añadir tags básicos
            audio['TIT2'] = TIT2(encoding=3, text=metadata['title'])
            audio['TPE1'] = TPE1(encoding=3, text=metadata['artist'])
            audio['TALB'] = TALB(encoding=3, text=metadata['album'])
            audio['TCON'] = TCON(encoding=3, text=metadata['genre'])
            audio['TRCK'] = TRCK(encoding=3, text=str(metadata['track_number']))
            audio['TDRC'] = TDRC(encoding=3, text=metadata['release_date'])
            
            # Añadir carátula si está disponible
            if metadata.get('cover_url'):
                try:
                    response = requests.get(metadata['cover_url'], timeout=10)
                    if response.status_code == 200:
                        audio['APIC'] = APIC(
                            encoding=3,
                            mime='image/jpeg',
                            type=3,
                            desc='Cover',
                            data=response.content
                        )
                except Exception as e:
                    logger.warning(f"No se pudo añadir carátula: {str(e)}")
            
            audio.save()
            logger.info(f"Metadata añadida a: {file_path}")
            
        except Exception as e:
            logger.error(f"Error al añadir metadata: {str(e)}")

    def create_playlist_file(self, playlist_info, output_dir):
        """Crea archivo .pla con la información de la playlist"""
        try:
            # Limpiar nombre de la playlist para el archivo
            clean_playlist_name = self.clean_filename(playlist_info['name'])
            playlist_file = os.path.join(output_dir, f"{clean_playlist_name}.pla")
            
            playlist_data = {
                'name': playlist_info['name'],
                'description': playlist_info.get('description', ''),
                'tracks': []
            }
            
            with open(playlist_file, 'w', encoding='utf-8') as f:
                json.dump(playlist_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Archivo .pla creado: {playlist_file}")
            return playlist_file
            
        except Exception as e:
            logger.error(f"Error al crear archivo .pla: {str(e)}")
            return None

    def download_playlist(self, playlist_url, output_dir='downloads'):
        """Descarga toda una playlist de Spotify"""
        try:
            # Crear directorio de salida
            os.makedirs(output_dir, exist_ok=True)
            
            # Configurar autenticación de YouTube
            if not self.setup_youtube_auth():
                print("⚠️ Continuando sin autenticación de YouTube...")
            
            # Obtener información de la playlist
            playlist_info = self.sp.playlist(playlist_url)
            playlist_id = playlist_info['id']
            playlist_name = playlist_info['name']
            
            logger.info(f"Iniciando descarga de playlist: {playlist_name}")
            if self.yt_auth.authenticated:
                logger.info("Autenticación YouTube: ACTIVADA (puede descargar contenido restringido)")
            else:
                logger.info("Autenticación YouTube: DESACTIVADA (puede fallar con contenido restringido)")
            
            # Crear archivo .pla
            self.create_playlist_file(playlist_info, output_dir)
            
            # Obtener tracks
            tracks = self.get_playlist_tracks(playlist_id)
            
            downloaded_count = 0
            failed_tracks = []
            
            for i, item in enumerate(tracks):
                if not item['track']:
                    continue
                    
                track = item['track']
                track_name = track['name']
                artist_name = track['artists'][0]['name']
                album_name = track['album']['name']
                
                logger.info(f"Procesando [{i+1}/{len(tracks)}]: {track_name} - {artist_name}")
                
                # Metadata para el archivo
                metadata = {
                    'title': track_name,
                    'artist': artist_name,
                    'album': album_name,
                    'genre': ', '.join([g for g in track.get('genres', [])]),
                    'track_number': track.get('track_number', 1),
                    'release_date': track['album'].get('release_date', ''),
                    'cover_url': track['album']['images'][0]['url'] if track['album']['images'] else None
                }
                
                # Buscar en YouTube
                youtube_url = self.search_youtube(track_name, artist_name)
                if not youtube_url:
                    logger.warning(f"No se encontró video para: {track_name} - {artist_name}")
                    failed_tracks.append(f"{track_name} - {artist_name}")
                    continue
                
                # Limpiar nombre del archivo
                clean_filename = self.clean_filename(f"{track_name}_{artist_name}")
                output_path = os.path.join(output_dir, clean_filename)
                
                # Descargar audio
                if self.download_audio(youtube_url, output_path, metadata):
                    downloaded_count += 1
                    logger.info(f"✅ Descargado: {clean_filename}.mp3")
                else:
                    failed_tracks.append(f"{track_name} - {artist_name}")
                
                # Pequeña pausa para evitar rate limiting
                time.sleep(2)  # Aumentar pausa para evitar bloqueos
            
            # Resumen final
            logger.info(f"🎉 Descarga completada. Exitosas: {downloaded_count}, Fallidas: {len(failed_tracks)}")
            
            if failed_tracks:
                logger.warning("Canciones que fallaron:")
                for track in failed_tracks:
                    logger.warning(f"  - {track}")
            
            return downloaded_count, failed_tracks
            
        except Exception as e:
            logger.error(f"Error fatal en download_playlist: {str(e)}")
            raise

def main():
    """Función principal"""
    try:
        # Instrucciones iniciales
        print("🎵 Spotify to YouTube Downloader - VERSIÓN SABR FIX")
        print("="*60)
        print("ESTA VERSIÓN INCLUYE SOLUCIONES PARA EL PROBLEMA SABR DE YOUTUBE")
        print("\nAsegúrate de tener:")
        print("• pip install spotipy yt-dlp mutagen requests browser_cookie3")
        print("• ffmpeg instalado en tu sistema")
        print("• Estar logueado en YouTube en tu navegador")
        print("\n" + "="*50)
        
        # Inicializar downloader
        downloader = SpotifyDownloader()
        
        # URL de la playlist de Spotify
        playlist_url = input("\nIngresa la URL de la playlist de Spotify: ").strip()
        
        # Directorio de descarga
        output_dir = input("Ingresa el directorio de descarga (presiona Enter para 'downloads'): ").strip()
        if not output_dir:
            output_dir = 'downloads'
        
        # Descargar playlist
        success, failures = downloader.download_playlist(playlist_url, output_dir)
        
        print(f"\n🎉 Descarga completada!")
        print(f"✅ Canciones descargadas: {success}")
        print(f"❌ Canciones fallidas: {len(failures)}")
        
        if failures:
            print("\nCanciones que fallaron:")
            for track in failures:
                print(f"  - {track}")
                
    except KeyboardInterrupt:
        logger.info("Descarga interrumpida por el usuario")
        print("\nOperación cancelada por el usuario")
    except Exception as e:
        logger.critical(f"Error crítico en la aplicación: {str(e)}")
        print(f"Error crítico: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
