import argparse
import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse


def main():
    parser = argparse.ArgumentParser(description="Save YouTube metadata and captions as Markdown")
    parser.add_argument("url")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--language", default="pt")
    parser.add_argument("--transcribe-audio", action="store_true", help="Download and transcribe audio if captions are unavailable")
    parser.add_argument("--force-audio", action="store_true", help="Transcribe audio even if captions are available")
    args = parser.parse_args()
    parsed = urlparse(args.url)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in (
        "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"
    ):
        parser.error("Provide a YouTube video URL")
    if args.output.exists():
        parser.error(f"Output already exists: {args.output}")
    try:
        import yt_dlp
    except ImportError:
        dependencies = Path.home() / ".cache" / "youtube-context" / "python" / f"{sys.version_info.major}.{sys.version_info.minor}"
        dependencies.mkdir(parents=True, exist_ok=True)
        sys.path.insert(0, str(dependencies))
        try:
            import yt_dlp
        except ImportError:
            print("Installing yt-dlp for youtube-context...", file=sys.stderr)
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "--target", str(dependencies), "yt-dlp"], check=True)
                import yt_dlp
            except (subprocess.CalledProcessError, ImportError) as exc:
                parser.exit(1, f"Could not install yt-dlp. Check pip and internet access: {exc}\n")

    with tempfile.TemporaryDirectory() as temporary:
        options = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": [args.language],
            "subtitlesformat": "vtt",
            "outtmpl": str(Path(temporary) / "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "socket_timeout": 20,
        }
        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(args.url, download=True)
        except Exception as exc:
            parser.exit(1, f"Could not retrieve video: {exc}\n")
        tracks = sorted(Path(temporary).glob("*.vtt"), key=lambda p: (args.language not in p.name, "en" in p.name))
        lines = []
        if tracks:
            current_time = None
            previous = ""
            for line in tracks[0].read_text(encoding="utf-8").splitlines():
                match = re.match(r"(\d\d:\d\d:\d\d\.\d+)\s+-->", line)
                if match:
                    current_time = match.group(1).split(".")[0]
                    continue
                if not current_time or not line.strip():
                    continue
                content = html.unescape(re.sub(r"<[^>]+>", "", line)).strip()
                if content and content != previous:
                    lines.append(f"- **{current_time}** {content}")
                    previous = content
        audio_source = False
        if (not lines and args.transcribe_audio) or args.force_audio:
            try:
                from faster_whisper import WhisperModel
            except ImportError:
                dependencies = Path.home() / ".cache" / "youtube-context" / "python" / f"{sys.version_info.major}.{sys.version_info.minor}"
                dependencies.mkdir(parents=True, exist_ok=True)
                sys.path.insert(0, str(dependencies))
                try:
                    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "--target", str(dependencies), "faster-whisper"], check=True)
                    from faster_whisper import WhisperModel
                except (subprocess.CalledProcessError, ImportError) as exc:
                    parser.exit(1, f"Could not install audio transcription dependencies: {exc}\n")
            try:
                audio_options = {"format": "bestaudio/best", "outtmpl": str(Path(temporary) / "audio.%(ext)s"), "noplaylist": True, "quiet": True, "socket_timeout": 20}
                with yt_dlp.YoutubeDL(audio_options) as downloader:
                    audio_info = downloader.extract_info(args.url, download=True)
                    audio_file = downloader.prepare_filename(audio_info)
                model = WhisperModel("base", device="cpu", compute_type="int8")
                segments, _ = model.transcribe(audio_file, language=args.language, vad_filter=True)
                audio_lines = []
                for segment in segments:
                    seconds = int(segment.start)
                    timestamp = f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"
                    audio_lines.append(f"- **{timestamp}** {segment.text.strip()}")
                lines = audio_lines
                audio_source = True
            except Exception as exc:
                print(f"Audio transcription failed: {exc}", file=sys.stderr)
        chapters = info.get("chapters") or []
        index = "\n".join(f"- {int(c.get('start_time', 0) // 60):02d}:{int(c.get('start_time', 0) % 60):02d} {c.get('title', '')}" for c in chapters) or "Capítulos não disponíveis."
        captions = "\n".join(lines) if lines else "Legendas não disponíveis ou não recuperadas."
        track_name = "Transcrição automática do áudio (Whisper base)" if audio_source else (tracks[0].name if tracks else "indisponível")
        result = (f"# {info.get('title', 'Vídeo')}\n\n"
                  f"Fonte: {info.get('webpage_url', args.url)}\n\n"
                  f"Canal: {info.get('uploader', 'Não informado')}\n\n"
                  f"Faixa de legenda: {track_name}\n\n"
                  f"## Índice\n\n- [Descrição](#descrição)\n- [Capítulos](#capítulos)\n- [Transcrição](#transcrição)\n\n"
                  f"## Descrição\n\n{info.get('description') or 'Não disponível.'}\n\n"
                  f"## Capítulos\n\n{index}\n\n## Transcrição\n\n{captions}\n")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as output:
            output.write(result)
        print(f"Saved {args.output}. Caption track: {track_name}")


if __name__ == "__main__":
    main()
