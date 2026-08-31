#!/usr/bin/env python3
"""Refresh the local metadata used by kristian.mk.

Only Python's standard library is used. The deployed page reads the generated
JSON files and never depends on a third-party API at page-load time.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PROJECTS_FILE = DATA_DIR / "projects.json"
PUBLICATIONS_FILE = DATA_DIR / "publications.json"

GITHUB_USER = "kristianmk"
FEATURED_REPOS = [
    "microgpt.cpp",
    "ros2-examples-ads",
    "ctrl-c-gpt-v",
    "party-hat-generator",
    "opencv-test-cmake",
]
ORCID_ID = "0000-0003-4088-1642"
DBLP_PID = "239/4279"
TODAY = dt.datetime.now(dt.timezone.utc).date().isoformat()
USER_AGENT = "kristian-mk-profile-refresh/1.0 (+https://kristian.mk/)"

DESCRIPTION_OVERRIDES = {
    "microgpt.cpp": "Small C++23 implementations of a tiny character-level GPT model.",
    "ros2-examples-ads": "ROS 2 examples for communicating with Beckhoff PLCs through ADS/AMS.",
    "ctrl-c-gpt-v": "Clipboard spelling and grammar correction using GPT.",
    "party-hat-generator": "Customizable CadQuery party hats ready for 3D printing.",
    "opencv-test-cmake": "A modern CMake example for a focused OpenCV build.",
}

VENUE_OVERRIDES = {
    "10.1016/j.cviu.2025.104575": "Computer Vision and Image Understanding",
    "10.1109/iccma67641.2025.11369605": "ICCMA 2025",
    "10.1109/access.2024.3408318": "IEEE Access",
    "10.1007/978-3-031-77918-3_2": "SGAI 2024",
    "10.7557/18.6824": "NLDL 2023",
    "10.1007/978-3-031-08223-8_12": "EANN 2022",
    "10.1007/978-3-031-08223-8_38": "EANN 2022",
    "10.1007/978-3-031-10525-8_9": "INTAP 2021",
    "10.1007/978-3-031-10525-8_29": "INTAP 2021",
    "10.1007/978-3-030-22999-3_9": "IEA/AIE 2019",
}

MANUAL_PUBLICATIONS = [
    {
        "title": "Accurate Wound and Lice Detection in Atlantic Salmon Fish Using a Convolutional Neural Network",
        "year": 2022,
        "venue": "Fishes",
        "type": "journal article",
        "doi": "10.3390/fishes7060345",
        "source": "ORCID",
    },
    {
        "title": "Unlocking the potential of deep learning for marine ecology: overview, applications, and outlook",
        "year": 2022,
        "venue": "ICES Journal of Marine Science",
        "type": "journal article",
        "doi": "10.1093/icesjms/fsab255",
        "source": "ORCID",
    },
]


def log(message: str) -> None:
    print(message, flush=True)


def warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr, flush=True)


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def year(value: Any) -> int:
    match = re.search(r"\b(?:19|20)\d{2}\b", clean(value))
    return int(match.group(0)) if match else 0


def doi(value: Any) -> str:
    value = clean(value).lower()
    value = re.sub(r"^(?:https?://)?(?:dx\.)?doi\.org/", "", value)
    value = re.sub(r"^doi:\s*", "", value)
    return value.rstrip(" .")


def title_key(value: Any) -> str:
    value = unicodedata.normalize("NFKD", clean(value))
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", value.casefold().replace("&", " and "))


def text(element: ET.Element | None) -> str:
    return clean("".join(element.itertext())) if element is not None else ""


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def request_bytes(
    url: str,
    *,
    accept: str,
    headers: dict[str, str] | None = None,
    attempts: int = 3,
) -> bytes:
    request_headers = {"Accept": accept, "User-Agent": USER_AGENT}
    request_headers.update(headers or {})
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers=request_headers)
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as error:
            last_error = error
            if attempt < attempts:
                time.sleep(attempt * 2)

    raise RuntimeError(f"request failed: {url}: {last_error}")


def request_json(url: str, *, accept: str = "application/json", headers: dict[str, str] | None = None) -> Any:
    return json.loads(request_bytes(url, accept=accept, headers=headers).decode("utf-8"))


def github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def integer_field(remote: dict[str, Any], key: str, fallback: dict[str, Any], fallback_key: str) -> int:
    value = remote.get(key)
    if value is None:
        value = fallback.get(fallback_key, 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def refresh_projects() -> tuple[dict[str, Any], bool]:
    existing = read_json(PROJECTS_FILE)
    by_name = {
        clean(item.get("name")): item
        for item in existing.get("items", [])
        if isinstance(item, dict) and clean(item.get("name"))
    }
    items: list[dict[str, Any]] = []
    successes = 0

    for name in FEATURED_REPOS:
        fallback = dict(by_name.get(name, {"name": name}))
        url = f"https://api.github.com/repos/{GITHUB_USER}/{urllib.parse.quote(name, safe='')}"
        try:
            remote = request_json(url, headers=github_headers())
            if not isinstance(remote, dict):
                raise ValueError("unexpected GitHub response")
            items.append(
                {
                    "name": clean(remote.get("name")) or name,
                    "url": clean(remote.get("html_url")) or f"https://github.com/{GITHUB_USER}/{name}",
                    "description": DESCRIPTION_OVERRIDES.get(name) or clean(remote.get("description")) or clean(fallback.get("description")),
                    "language": clean(remote.get("language")) or clean(fallback.get("language")) or "Code",
                    "stars": integer_field(remote, "stargazers_count", fallback, "stars"),
                    "forks": integer_field(remote, "forks_count", fallback, "forks"),
                    "updated_at": clean(remote.get("updated_at")) or clean(fallback.get("updated_at")),
                }
            )
            successes += 1
        except Exception as error:
            warn(f"GitHub metadata for {name} was not refreshed: {error}")
            fallback.setdefault("name", name)
            fallback.setdefault("url", f"https://github.com/{GITHUB_USER}/{name}")
            fallback["description"] = DESCRIPTION_OVERRIDES.get(name) or clean(fallback.get("description"))
            items.append(fallback)

    if not items:
        return existing, False
    return {
        "updated": TODAY if successes else clean(existing.get("updated")) or TODAY,
        "source": "GitHub REST API",
        "items": items,
    }, bool(successes)


def doi_and_url(values: Iterable[str]) -> tuple[str, str]:
    first_url = ""
    for raw in values:
        value = clean(raw)
        lower = value.lower()
        if not first_url and value.startswith(("http://", "https://")):
            first_url = value
        if "doi.org/" in lower or lower.startswith("10."):
            candidate = doi(value)
            if candidate.startswith("10."):
                return candidate, f"https://doi.org/{candidate}"
        match = re.search(r"arxiv(?:\.org/(?:abs|pdf)/|:|\.)\s*([0-9]{4}\.[0-9]{4,5}(?:v\d+)?)", lower)
        if match:
            candidate = f"10.48550/arxiv.{match.group(1)}"
            return candidate, f"https://doi.org/{candidate}"
    return "", first_url


def dblp_type(tag: str, venue: str) -> str:
    if "corr" in venue.casefold() or "arxiv" in venue.casefold():
        return "preprint"
    return {
        "article": "journal article",
        "inproceedings": "conference paper",
        "incollection": "book chapter",
        "book": "book",
        "phdthesis": "doctoral thesis",
        "mastersthesis": "master thesis",
    }.get(tag, "publication")


def parse_dblp(body: bytes) -> list[dict[str, Any]]:
    root = ET.fromstring(body)
    result: list[dict[str, Any]] = []
    for wrapper in root.findall(".//r"):
        record = next(iter(wrapper), None)
        if record is None:
            continue
        publication_title = text(record.find("title")).rstrip(".")
        publication_year = year(record.findtext("year"))
        venue = clean(record.findtext("journal") or record.findtext("booktitle") or record.findtext("publisher") or record.findtext("school"))
        values = [text(item) for item in record.findall("ee") + record.findall("url")]
        publication_doi, url = doi_and_url(values)
        if publication_doi in VENUE_OVERRIDES:
            venue = VENUE_OVERRIDES[publication_doi]
        if publication_doi.startswith("10.48550/arxiv."):
            venue = "arXiv"
        if not publication_title or not publication_year:
            continue
        record_key = clean(record.attrib.get("key"))
        result.append(
            {
                "id": f"doi:{publication_doi}" if publication_doi else f"dblp:{record_key or title_key(publication_title)}",
                "title": publication_title,
                "year": publication_year,
                "venue": venue or "Research publication",
                "type": dblp_type(record.tag, venue),
                "doi": publication_doi,
                "url": url or (f"https://dblp.org/rec/{record_key}" if record_key else ""),
                "source": "DBLP",
            }
        )
    return result


def nested(value: Any, *keys: str) -> str:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return clean(current)


def orcid_type(value: Any) -> str:
    value = clean(value).casefold().replace("_", "-")
    return {
        "journal-article": "journal article",
        "conference-paper": "conference paper",
        "conference-abstract": "conference paper",
        "book-chapter": "book chapter",
        "book": "book",
        "preprint": "preprint",
        "dissertation-thesis": "doctoral thesis",
    }.get(value, value.replace("-", " ") or "publication")


def parse_orcid(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    result: list[dict[str, Any]] = []
    for group in payload.get("group", []):
        if not isinstance(group, dict):
            continue
        summaries = group.get("work-summary") or group.get("work_summary") or []
        summary = next((item for item in summaries if isinstance(item, dict)), None)
        if summary is None:
            continue
        publication_title = nested(summary, "title", "title", "value")
        publication_year = year(nested(summary, "publication-date", "year", "value") or nested(summary, "publication_date", "year", "value"))
        venue = nested(summary, "journal-title", "value") or nested(summary, "journal_title", "value")
        values: list[str] = []
        external = summary.get("external-ids") or summary.get("external_ids") or {}
        identifiers: list[Any] = []
        if isinstance(external, dict):
            candidates = external.get("external-id") or external.get("external_id") or []
            if isinstance(candidates, list):
                identifiers = candidates
        for identifier in identifiers:
            if not isinstance(identifier, dict):
                continue
            kind = clean(identifier.get("external-id-type") or identifier.get("external_id_type")).casefold()
            raw = clean(identifier.get("external-id-value") or identifier.get("external_id_value"))
            if kind == "doi" and raw:
                values.insert(0, raw)
            elif kind == "arxiv" and raw:
                values.append(f"arXiv:{raw}")
            link = nested(identifier, "external-id-url", "value") or nested(identifier, "external_id_url", "value")
            if link:
                values.append(link)
        direct_url = nested(summary, "url", "value")
        if direct_url:
            values.append(direct_url)
        publication_doi, url = doi_and_url(values)
        publication_type = orcid_type(summary.get("type"))
        if publication_doi in VENUE_OVERRIDES:
            venue = VENUE_OVERRIDES[publication_doi]
        if publication_doi.startswith("10.48550/arxiv."):
            venue = "arXiv"
            publication_type = "preprint"
        if not publication_title or not publication_year:
            continue
        put_code = summary.get("put-code") or summary.get("put_code")
        result.append(
            {
                "id": f"doi:{publication_doi}" if publication_doi else f"orcid:{put_code or title_key(publication_title)}",
                "title": publication_title.rstrip("."),
                "year": publication_year,
                "venue": venue or "Research publication",
                "type": publication_type,
                "doi": publication_doi,
                "url": url or f"https://orcid.org/{ORCID_ID}",
                "source": "ORCID",
            }
        )
    return result


def score(item: dict[str, Any]) -> int:
    base = {
        "journal article": 60,
        "conference paper": 50,
        "book chapter": 40,
        "book": 35,
        "doctoral thesis": 30,
        "master thesis": 25,
        "preprint": 10,
    }.get(clean(item.get("type")).casefold(), 20)
    item_doi = doi(item.get("doi"))
    venue = clean(item.get("venue")).casefold()
    return base + (10 if item_doi else 0) + (8 if item_doi and not item_doi.startswith("10.48550/arxiv.") else 0) + (4 if venue not in {"", "arxiv", "corr", "research publication"} else 0)


def merge(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    preferred, other = (first, second) if score(first) >= score(second) else (second, first)
    result = dict(preferred)
    for field in ("id", "title", "year", "venue", "type", "doi", "url"):
        if not result.get(field) and other.get(field):
            result[field] = other[field]
    sources = sorted({clean(first.get("source")), clean(second.get("source"))} - {""})
    result["source"] = "+".join(sources)
    return result


def deduplicate(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for raw in items:
        item = dict(raw)
        item["title"] = clean(item.get("title")).rstrip(".")
        item["year"] = year(item.get("year"))
        item["venue"] = clean(item.get("venue")) or "Research publication"
        item["type"] = clean(item.get("type")).casefold() or "publication"
        item["doi"] = doi(item.get("doi"))
        if not item["title"] or not item["year"]:
            continue
        if item["doi"]:
            item["id"] = f"doi:{item['doi']}"
            item["url"] = f"https://doi.org/{item['doi']}"
        key = f"doi:{item['doi']}" if item["doi"] else f"title:{title_key(item['title'])}"
        by_key[key] = merge(by_key[key], item) if key in by_key else item

    # A second pass merges records that have the same title but different identifiers.
    by_title: dict[str, dict[str, Any]] = {}
    for item in by_key.values():
        key = title_key(item["title"])
        by_title[key] = merge(by_title[key], item) if key in by_title else item

    result = list(by_title.values())
    for item in result:
        item_doi = doi(item.get("doi"))
        if item_doi in VENUE_OVERRIDES:
            item["venue"] = VENUE_OVERRIDES[item_doi]
        if item_doi.startswith("10.48550/arxiv."):
            item["venue"] = "arXiv"
            item["type"] = "preprint"
        item["id"] = item.get("id") or f"title:{title_key(item['title'])}"
    result.sort(key=lambda item: (-int(item["year"]), -score(item), clean(item["title"]).casefold()))
    return result


def refresh_publications() -> tuple[dict[str, Any], bool]:
    existing = read_json(PUBLICATIONS_FILE)
    existing_items = [item for item in existing.get("items", []) if isinstance(item, dict)]
    fetched: list[dict[str, Any]] = []
    successful_sources = 0

    try:
        body = request_bytes(f"https://dblp.org/pid/{DBLP_PID}.xml", accept="application/xml,text/xml;q=0.9,*/*;q=0.1")
        items = parse_dblp(body)
        if items:
            fetched.extend(items)
            successful_sources += 1
            log(f"DBLP: {len(items)} records")
    except Exception as error:
        warn(f"DBLP metadata was not refreshed: {error}")

    try:
        payload = request_json(f"https://pub.orcid.org/v3.0/{ORCID_ID}/works", accept="application/vnd.orcid+json")
        items = parse_orcid(payload)
        if items:
            fetched.extend(items)
            successful_sources += 1
            log(f"ORCID: {len(items)} records")
    except Exception as error:
        warn(f"ORCID metadata was not refreshed: {error}")

    if not successful_sources:
        return existing, False

    publications = deduplicate(fetched + existing_items + MANUAL_PUBLICATIONS)
    return {
        "updated": TODAY,
        "sources": [f"ORCID {ORCID_ID}", f"DBLP {DBLP_PID}"],
        "items": publications,
    }, True


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    projects, project_success = refresh_projects()
    publications, publication_success = refresh_publications()

    if projects:
        write_json(PROJECTS_FILE, projects)
        log(f"projects: {len(projects.get('items', []))} items {'refreshed' if project_success else 'retained'}")
    if publications:
        write_json(PUBLICATIONS_FILE, publications)
        log(f"publications: {len(publications.get('items', []))} items {'refreshed' if publication_success else 'retained'}")

    if not projects and not publications:
        warn("No local data was available and no remote source could be reached.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
