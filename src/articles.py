"""Récupération d'articles avec des stratégies de repli bornées."""

import time
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import cloudscraper
import requests
from bs4 import BeautifulSoup
from newspaper import Article, Config
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


REQUEST_TIMEOUT = 15
TOTAL_TIMEOUT = 60
MIN_TEXT_LENGTH = 100
SELENIUM_WAIT = 3

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}
SHORTENER_DOMAINS = {
    "flip.it", "bit.ly", "t.co", "tinyurl.com", "goo.gl", "ow.ly",
    "short.link", "buff.ly", "is.gd", "v.gd", "cutt.ly", "rebrand.ly",
    "tiny.cc",
}
REDIRECT_CODES = {301, 302, 303, 307, 308}


class ExtractionError(Exception):
    """Une stratégie n'a pas produit un article exploitable."""


def clean_url(url):
    """Retire les paramètres utm_* de la query et du fragment."""
    if not url:
        return url
    try:
        parsed = urlparse(url.strip().rstrip(".,;:!'\"]>)"))
        query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
                 if not k.lower().startswith("utm_")]
        fragment = parsed.fragment
        if fragment and ("=" in fragment or "&" in fragment):
            fragment_items = [
                (k, v) for k, v in parse_qsl(fragment, keep_blank_values=True)
                if not k.lower().startswith("utm_")
            ]
            fragment = urlencode(fragment_items, doseq=True) if fragment_items else ""
        return urlunparse(parsed._replace(
            query=urlencode(query, doseq=True), fragment=fragment
        ))
    except (TypeError, ValueError):
        return url


def is_shortener_url(url):
    """Teste le nom d'hôte, sans faux positif par simple sous-chaîne."""
    hostname = (urlparse(url).hostname or "").lower()
    return hostname in SHORTENER_DOMAINS


def resolve_redirects(url, max_redirects=10, timeout=REQUEST_TIMEOUT):
    """Résout un raccourci en détectant les cycles de redirection."""
    current_url = clean_url(url)
    visited = set()
    session = requests.Session()
    session.headers.update(HEADERS)

    for _ in range(max_redirects):
        if current_url in visited:
            raise ExtractionError(f"Cycle de redirection détecté: {current_url}")
        visited.add(current_url)

        response = session.head(
            current_url, allow_redirects=False, timeout=timeout
        )
        if response.status_code not in REDIRECT_CODES:
            return clean_url(current_url)
        location = response.headers.get("Location")
        if not location:
            return clean_url(current_url)
        current_url = clean_url(urljoin(current_url, location))

    raise ExtractionError(f"Plus de {max_redirects} redirections: {url}")


def _remaining(deadline, maximum=REQUEST_TIMEOUT):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Budget global d'extraction épuisé")
    return max(1, min(maximum, remaining))


def _article_result(article, fallback_url):
    return {
        "title": (article.title or "").strip(),
        "text": (article.text or "").strip(),
        "canonical_link": article.canonical_link or fallback_url,
        "image": article.top_image or "",
        "publish": article.publish_date or "",
    }


def _validate(result):
    if not result or len(result.get("text", "")) <= MIN_TEXT_LENGTH:
        raise ExtractionError("Contenu extrait insuffisant")
    if not result.get("title"):
        result["title"] = "Sans titre"
    return result


def parse_with_newspaper(url, html=None, timeout=REQUEST_TIMEOUT):
    """Analyse avec newspaper, qui reste l'extracteur de référence."""
    config = Config()
    config.request_timeout = max(1, int(timeout))
    config.browser_user_agent = USER_AGENT
    article = Article(url, config=config)
    if html is None:
        article.download()
    else:
        article.set_html(html)
    article.parse()
    return _validate(_article_result(article, url))


def _fetch_requests(url, timeout):
    response = requests.get(
        url, headers=HEADERS, timeout=timeout, allow_redirects=True
    )
    response.raise_for_status()
    return response.content, clean_url(response.url)


def _fetch_cloudscraper(url, timeout):
    scraper = cloudscraper.create_scraper(browser={
        "browser": "chrome", "platform": "darwin", "desktop": True,
    })
    response = scraper.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.content, clean_url(response.url)


def _selenium_html(url, timeout):
    driver = None
    try:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"--user-agent={USER_AGENT}")
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(max(1, int(timeout)))
        try:
            driver.get(url)
        except TimeoutException:
            # Chrome possède souvent déjà assez de HTML pour tenter l'extraction.
            driver.execute_script("window.stop();")

        time.sleep(min(SELENIUM_WAIT, max(0, timeout / 4)))
        try:
            buttons = driver.find_elements(
                By.XPATH,
                "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
                "'abcdefghijklmnopqrstuvwxyz'), 'accept')]",
            )
            if buttons:
                buttons[0].click()
                time.sleep(1)
        except Exception:
            pass
        return driver.page_source, clean_url(driver.current_url or url)
    finally:
        if driver is not None:
            driver.quit()


def selenium_manual_fallback(html, url):
    """Dernier recours lorsque newspaper ne comprend pas le HTML rendu."""
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    for selector in ("h1", "title", ".article-title", ".entry-title", ".post-title"):
        node = soup.select_one(selector)
        if node and node.get_text(strip=True):
            title = node.get_text(" ", strip=True)
            break

    text = ""
    for selector in ("article", ".article-content", ".entry-content",
                     ".post-content", "main", "#content"):
        node = soup.select_one(selector)
        candidate = node.get_text("\n", strip=True) if node else ""
        if len(candidate) > MIN_TEXT_LENGTH:
            text = candidate
            break

    image = ""
    image_node = soup.select_one(
        "article img, .article-content img, .featured-image img"
    )
    if image_node and image_node.get("src"):
        image = urljoin(url, image_node["src"])

    return _validate({
        "title": title,
        "text": text,
        "canonical_link": url,
        "image": image,
        "publish": "",
    })


def get_article_from_source(url, mode=1, max_retries=4, total_timeout=TOTAL_TIMEOUT):
    """Extrait un article avec des replis ordonnés et un budget global.

    ``mode`` et ``max_retries`` restent acceptés pour compatibilité avec les
    anciens appels, mais les stratégies ne sont plus pilotées récursivement.
    """
    del mode, max_retries
    url = clean_url(url)
    deadline = time.monotonic() + total_timeout
    errors = []

    if is_shortener_url(url):
        try:
            url = resolve_redirects(url, timeout=_remaining(deadline))
        except Exception as error:
            errors.append(f"redirections: {error}")

    print(f"Extraction newspaper: {url}")
    try:
        return parse_with_newspaper(url, timeout=_remaining(deadline))
    except Exception as error:
        errors.append(f"newspaper: {error}")

    for name, fetcher in (("requests", _fetch_requests),
                          ("cloudscraper", _fetch_cloudscraper)):
        print(f"Repli {name}: {url}")
        try:
            html, final_url = fetcher(url, _remaining(deadline))
            return parse_with_newspaper(
                final_url, html=html, timeout=_remaining(deadline)
            )
        except Exception as error:
            errors.append(f"{name}: {error}")

    print(f"Repli Selenium: {url}")
    try:
        html, final_url = _selenium_html(url, _remaining(deadline, 25))
        try:
            return parse_with_newspaper(
                final_url, html=html, timeout=_remaining(deadline)
            )
        except Exception as error:
            errors.append(f"selenium/newspaper: {error}")
            return selenium_manual_fallback(html, final_url)
    except Exception as error:
        errors.append(f"selenium: {error}")

    print(f"Échec définitif pour {url}: {' | '.join(errors)}")
    return None


if __name__ == "__main__":
    test_url = (
        "https://www.joanwestenberg.com/p/"
        "why-stories-make-you-smarter-than-self-help-books"
    )
    # print(get_article_from_source(test_url))
