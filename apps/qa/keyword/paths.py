from pathlib import Path

from django.conf import settings


def qa_kb_dir() -> Path:
    return Path(settings.BASE_DIR) / 'apps' / 'qa' / 'knowledge_base'


def qa_kb_sources_dir() -> Path:
    return qa_kb_dir() / 'sources'


def qa_kb_index_dir() -> Path:
    return qa_kb_dir() / 'index'


def qa_keyword_index_path() -> Path:
    return qa_kb_index_dir() / 'keyword_index.json'

