from __future__ import annotations
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import json
import time

from .utils_hebrew import normalize_token

@dataclass
class WordEntry:
    id: str
    word_raw: str
    word_nikud: str
    english: str
    hebrew: str = ""
    sources: List[str] = field(default_factory=list)  # e.g. ["suka 2a-4a gemara", "suka 2a tos"]
    sheet: Optional[str] = None
    created_at: float = 0.0

    @property
    def norm(self) -> str:
        return normalize_token(self.word_raw)

@dataclass
class Project:
    id: str
    title: str
    created_at: float
    updated_at: float

    masechta: str = "Sukkah"
    perek: str = "1"
    daf: str = "2a"
    
    rows: List[Dict[str, Any]] = field(default_factory=list)  # each: {"word": "...", "explanation": "..."}
    meta: Dict[str, Any] = field(default_factory=dict)  # for future extensibility

class DataStore:
    """
    Small local JSON store.
    - words.json: imported dictionary entries
    - projects.json: dialogues/projects created in the app
    - files.json: imported/created file registry for Browse
    """
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.words_path = self.root / "words.json"
        self.projects_path = self.root / "projects.json"
        self.files_path = self.root / "files.json"

        self._words: Dict[str, WordEntry] = {}
        self._projects: Dict[str, Project] = {}
        self._files: List[Dict[str, Any]] = []

        self._load_all()

    # ---------- load/save ----------
    def _load_all(self) -> None:
        self._words = {}
        self._projects = {}
        self._files = []

        if self.words_path.exists():
            data = json.loads(self.words_path.read_text(encoding="utf-8"))
            for d in data:
                # Backward compatible: old stores don't have 'hebrew'
                if "hebrew" not in d:
                    d["hebrew"] = ""
                we = WordEntry(**d)
                self._words[we.id] = we

        if self.projects_path.exists():
            data = json.loads(self.projects_path.read_text(encoding="utf-8"))
            for d in data:
                pr = Project(**d)
                if pr.rows is None: pr.rows = []
                if pr.meta is None: pr.meta = {}
                self._projects[pr.id] = pr

        if self.files_path.exists():
            self._files = json.loads(self.files_path.read_text(encoding="utf-8"))

    def save_all(self) -> None:
        self.words_path.write_text(json.dumps([asdict(w) for w in self._words.values()], ensure_ascii=False, indent=2), encoding="utf-8")
        self.projects_path.write_text(json.dumps([asdict(p) for p in self._projects.values()], ensure_ascii=False, indent=2), encoding="utf-8")
        self.files_path.write_text(json.dumps(self._files, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- words ----------
    def upsert_word(self, word_raw: str, word_nikud: str, english: str = "", source: str = "", sheet: str | None = None, hebrew: str = "") -> WordEntry:
        """Insert or merge a word entry.

        Merge rule (requested):
        - same normalized word + same english explanation => ONE entry
        - if saved again from a different place, append a new source
        """

        norm = normalize_token(word_raw)
        key = f"{norm}||{(english or '').strip()}||{(hebrew or '').strip()}"
        # stable id derived from key (local-only)
        wid = "w_" + str(abs(hash(key)))
        now = time.time()

        if wid in self._words:
            we = self._words[wid]
            # keep best fields
            if word_nikud and not we.word_nikud:
                we.word_nikud = word_nikud
            if source:
                if source not in we.sources:
                    we.sources.append(source)
            if sheet and not we.sheet:
                we.sheet = sheet
            if hebrew and not we.hebrew:
                we.hebrew = hebrew
            return we

        we = WordEntry(
            id=wid,
            word_raw=word_raw or "",
            word_nikud=word_nikud or "",
            english=english or "",
            hebrew=hebrew or "",
            sources=[source] if source else [],
            sheet=sheet,
            created_at=now,
        )
        self._words[we.id] = we
        return we

    def search_words(self, query: str, limit: int = 50) -> List[WordEntry]:
        q = normalize_token(query)
        if not q:
            # recent-ish: by created_at desc
            return sorted(self._words.values(), key=lambda w: w.created_at, reverse=True)[:limit]
        out = []
        for w in self._words.values():
            if q in w.norm or q in normalize_token(w.word_nikud) or q in normalize_token(w.english) or q in normalize_token(w.hebrew):
                out.append(w)
        # basic ranking: shorter norm distance and more sources
        out.sort(key=lambda w: (len(w.norm), -len(w.sources)))
        return out[:limit]

    def suggest_explanations(self, word_query: str, limit: int = 50) -> List[Tuple[str, str, str]]:
        """Return deduped suggestions for a word.

        Returns list of tuples: (display, english, hebrew)
        Display includes aggregated sources.
        """
        hits = self.search_words(word_query, limit=300)
        by_key: Dict[str, WordEntry] = {}
        for w in hits:
            k = f"{(w.english or '').strip()}||{(w.hebrew or '').strip()}"
            if k not in by_key:
                by_key[k] = w
            else:
                # merge sources for display purposes
                for s in w.sources:
                    if s not in by_key[k].sources:
                        by_key[k].sources.append(s)

        out: List[Tuple[str, str, str]] = []
        for w in by_key.values():
            eng = (w.english or "").strip()
            heb = (w.hebrew or "").strip()
            expl = eng if eng else heb
            if not expl:
                continue
            src = ", ".join(w.sources[:6])
            if len(w.sources) > 6:
                src += f" (+{len(w.sources)-6})"
            display = f"{expl}  —  {src}" if src else expl
            out.append((display, eng, heb))

        # stable order: more sources first, then shorter
        out.sort(key=lambda t: (-len(by_key[f"{t[1].strip()}||{t[2].strip()}"].sources), len(t[0])))
        return out[:limit]

    def all_words_count(self) -> int:
        return len(self._words)

    # ---------- projects ----------
    def make_unique_project_title(self, title: str, exclude_id: str | None = None) -> str:
        """Return a unique title by adding ' (2)', ' (3)', ... if needed."""
        base = (title or "").strip() or "Untitled"
        existing = set()
        for pid, pr in self._projects.items():
            if exclude_id and pid == exclude_id:
                continue
            existing.add((pr.title or "").strip().lower())
        if base.lower() not in existing:
            return base
        n = 2
        while True:
            cand = f"{base} ({n})"
            if cand.lower() not in existing:
                return cand
            n += 1

    def create_project(self, title: str) -> Project:
        now = time.time()
        pid = "p_" + str(abs(hash(f"{title}||{now}")))
        pr = Project(
            id=pid,
            title=title.strip() or "Untitled",
            created_at=now,
            updated_at=now,
            rows=[],
            meta={},
        )
        self._projects[pid] = pr

        # Register in files list as "created"
        self._register_file({
            "id": pid,
            "kind": "project",
            "title": pr.title,
            "type": "created",
            "updated_at": pr.updated_at,
        })
        self.save_all()
        return pr

    def update_project(self, pr: Project) -> None:
        pr.updated_at = time.time()
        self._projects[pr.id] = pr
        # update files registry
        for f in self._files:
            if f.get("kind") == "project" and f.get("id") == pr.id:
                f["title"] = pr.title
                f["updated_at"] = pr.updated_at
        self.save_all()

    def list_projects(self) -> List[Project]:
        return sorted(self._projects.values(), key=lambda p: p.updated_at, reverse=True)

    def get_project(self, pid: str) -> Optional[Project]:
        return self._projects.get(pid)

    def delete_project(self, pid: str) -> bool:
        """Hard-delete a working page project from projects + files registry."""
        if pid not in self._projects:
            return False
        del self._projects[pid]
        self._files = [f for f in self._files if not (f.get("kind") == "project" and f.get("id") == pid)]
        self.save_all()
        return True

    # ---------- files registry ----------
    def _register_file(self, item: Dict[str, Any]) -> None:
        # If exists, update; else append
        for f in self._files:
            if f.get("kind") == item.get("kind") and f.get("id") == item.get("id"):
                f.update(item)
                return
        self._files.append(item)

    def register_import(self, import_id: str, title: str) -> None:
        self._register_file({
            "id": import_id,
            "kind": "import",
            "title": title,
            "type": "imported",
            "updated_at": time.time(),
        })
        self.save_all()


    def register_saved_export(self, export_id: str, title: str, fmt: str, source_project_id: str | None = None, out_path: str | None = None) -> None:
        """Register a file that was exported/saved (e.g., .docx/.xlsx)."""
        item: Dict[str, Any] = {
            "id": export_id,
            "kind": "export",
            "title": title,
            "type": "saved",
            "format": fmt,
            "source_project_id": source_project_id,
            "path": out_path,
            "updated_at": time.time(),
        }
        # prune None keys for cleanliness
        item = {k:v for k,v in item.items() if v is not None}
        self._register_file(item)
        self.save_all()
    def list_files(self) -> List[Dict[str, Any]]:
        return sorted(self._files, key=lambda f: f.get("updated_at", 0), reverse=True)

    def list_recent_files(self, limit: int = 8) -> List[Dict[str, Any]]:
        return self.list_files()[:limit]