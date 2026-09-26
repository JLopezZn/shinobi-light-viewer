import json
import subprocess
from pathlib import Path


def probe_duration_ms(file_path: str) -> int:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", file_path],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            duration = float(stream.get("duration", 0))
            return int(duration * 1000)
    return 0


def build_filelist(paths: list, dest: Path, name: str = "filelist.txt") -> Path:
    filelist = dest / name
    with filelist.open("w") as f:
        for p in paths:
            escaped = p.replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")
    return filelist


def concat_cmd(filelist: Path, output: Path) -> list:
    return [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(filelist),
        "-c", "copy",
        "-progress", "pipe:1",
        "-nostats",
        str(output),
    ]


def compute_export_size(chunks: list) -> int:
    return sum(c["file_size_bytes"] for c in chunks)
