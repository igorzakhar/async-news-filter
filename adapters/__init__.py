from . import inosmi_ru
from . import dvmn_org
from .exceptions import ArticleNotFound

__all__ = ['SANITIZERS', 'ArticleNotFound']

SANITIZERS = {
    'inosmi_ru': inosmi_ru.sanitize,
    'dvmn_org': dvmn_org.sanitize,
}
