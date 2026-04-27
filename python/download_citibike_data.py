from __future__ import annotations

import argparse
import json
import re
import ssl
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree


ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
TRIP_ZIP_DIR = RAW_DIR / "tripdata_zip"
TRIP_CSV_DIR = RAW_DIR / "tripdata_csv"
GBFS_DIR = RAW_DIR / "gbfs"

TRIP_BUCKET_URL = "https://s3.amazonaws.com/tripdata"
GBFS_DISCOVERY_URL = "https://gbfs.citibikenyc.com/gbfs/2.3/gbfs.json"

MONTH_PATTERN = re.compile(r"(?P<month>\d{6})-citibike-tripdata.*\.zip$")


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request) as response:
            return response.read().decode("utf-8")
    except URLError as exc:
        if isinstance(exc.reason, ssl.SSLCertVerificationError):
            insecure_context = ssl._create_unverified_context()
            with urlopen(request, context=insecure_context) as response:
                return response.read().decode("utf-8")
        raise


def fetch_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request) as response:
            return response.read()
    except URLError as exc:
        if isinstance(exc.reason, ssl.SSLCertVerificationError):
            insecure_context = ssl._create_unverified_context()
            with urlopen(request, context=insecure_context) as response:
                return response.read()
        raise


def parse_bucket_page(xml_text: str) -> tuple[list[tuple[str, str]], str | None]:
    root = ElementTree.fromstring(xml_text)
    keys: list[tuple[str, str]] = []
    for content in root.findall("{http://s3.amazonaws.com/doc/2006-03-01/}Contents"):
        key = content.findtext("{http://s3.amazonaws.com/doc/2006-03-01/}Key", default="")
        match = MONTH_PATTERN.search(key)
        if match:
            keys.append((match.group("month"), key))
    next_token = root.findtext("{http://s3.amazonaws.com/doc/2006-03-01/}NextContinuationToken")
    return keys, next_token


def list_trip_archives() -> list[tuple[str, str]]:
    all_keys: list[tuple[str, str]] = []
    next_token: str | None = None
    while True:
        url = f"{TRIP_BUCKET_URL}?list-type=2"
        if next_token:
            url += f"&continuation-token={next_token}"
        page_keys, next_token = parse_bucket_page(fetch_text(url))
        all_keys.extend(page_keys)
        if not next_token:
            break
    return all_keys


def select_latest_archives(months: int) -> list[str]:
    archives = list_trip_archives()
    grouped: dict[str, list[str]] = {}
    for month, key in archives:
        grouped.setdefault(month, []).append(key)

    latest_months = sorted(grouped.keys(), reverse=True)[:months]
    selected: list[str] = []
    for month in latest_months:
        selected.extend(sorted(grouped[month]))
    return selected


def download_trip_archives(keys: list[str]) -> list[Path]:
    TRIP_ZIP_DIR.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    for key in keys:
        target = TRIP_ZIP_DIR / Path(key).name
        if not target.exists():
            target.write_bytes(fetch_bytes(f"{TRIP_BUCKET_URL}/{key}"))
        downloaded.append(target)
    return downloaded


def extract_trip_archives(archives: list[Path]) -> list[Path]:
    TRIP_CSV_DIR.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    for archive in archives:
        with zipfile.ZipFile(archive) as zip_file:
            for name in zip_file.namelist():
                if name.endswith(".csv"):
                    output_path = TRIP_CSV_DIR / Path(name).name
                    with zip_file.open(name) as src, open(output_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    extracted.append(output_path)
    return extracted


def download_gbfs_snapshot() -> list[Path]:
    GBFS_DIR.mkdir(parents=True, exist_ok=True)
    discovery = json.loads(fetch_text(GBFS_DISCOVERY_URL))
    feeds = discovery["data"]["en"]["feeds"]
    wanted = {"system_information", "station_information", "station_status", "vehicle_types"}
    snapshot_time = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    saved: list[Path] = []
    for feed in feeds:
        if feed["name"] in wanted:
            data = json.loads(fetch_text(feed["url"]))
            target = GBFS_DIR / f"{snapshot_time}_{feed['name']}.json"
            target.write_text(json.dumps(data, indent=2), encoding="utf-8")
            saved.append(target)
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description="Download real Citi Bike data.")
    parser.add_argument("--months", type=int, default=3, help="How many latest months to download.")
    args = parser.parse_args()

    keys = select_latest_archives(args.months)
    if not keys:
        raise RuntimeError("No Citi Bike trip archives were found in the official tripdata bucket.")

    archives = download_trip_archives(keys)
    extracted = extract_trip_archives(archives)
    gbfs_files = download_gbfs_snapshot()

    print(f"Downloaded {len(archives)} Citi Bike trip archives.")
    print(f"Extracted {len(extracted)} CSV files.")
    print(f"Saved {len(gbfs_files)} GBFS snapshot files.")


if __name__ == "__main__":
    main()
