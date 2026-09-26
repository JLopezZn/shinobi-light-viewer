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


def build_filelist(paths: list[str], dest: Path) -> Path:
    filelist = dest / "filelist.txt"
    with filelist.open("w") as f:
        for p in paths:
            escaped = p.replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")
    return filelist


def concat_cmd(filelist: Path, output: Path) -> list[str]:
    return [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(filelist),
        "-c", "copy",
        "-progress", "pipe:1",
        "-nostats",
        str(output),
    ]


def timelapse_cmd(filelist: Path, output: Path, speed: float) -> list[str]:
    setpts = f"{1.0 / speed:.6f}*PTS"
    return [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(filelist),
        "-vf", f"setpts={setpts}",
        "-r", "30",
        "-an",
        "-progress", "pipe:1",
        "-nostats",
        str(output),
    ]


def compute_speed(total_source_ms: int, target_output_ms: int = 60_000) -> float:
    return max(total_source_ms / target_output_ms, 1.0)
