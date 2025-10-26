# python3 src/articles.py

import requests
from urllib.parse import urljoin, urlparse
from newspaper import Article
import time
import random
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import cloudscraper
import urllib3
import ssl
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode


def resolve_redirects(url, max_redirects=10):
    """Résout les redirections manuellement pour gérer les liens comme flip.it"""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    })
    
    current_url = url
    redirect_count = 0
    
    try:
        while redirect_count < max_redirects:
            print(f"Résolution redirect {redirect_count + 1}: {current_url}")
            
            response = session.head(current_url, allow_redirects=False, timeout=10)
            
            if response.status_code not in (301, 302, 303, 307, 308):
                break
                
            location = response.headers.get('Location')
            if not location:
                break
                
            current_url = urljoin(current_url, location)
            redirect_count += 1
            time.sleep(0.5)
            
        print(f"URL finale après redirections: {current_url}")
        current_url = clean_url(current_url)
        print(f"URL ckleaning après redirections: {current_url}")
        return current_url
        
    except Exception as e:
        print(f"Erreur lors de la résolution des redirections: {e}")
        return url


def is_shortener_url(url):
    """Détecte si l'URL est un raccourcisseur connu"""
    shortener_domains = [
        'flip.it', 'bit.ly', 't.co', 'tinyurl.com', 'goo.gl', 
        'ow.ly', 'short.link', 'buff.ly', 'is.gd', 'v.gd',
        'cutt.ly', 'rebrand.ly', 'tiny.cc'
    ]
    
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    return any(shortener in domain for shortener in shortener_domains)


def get_article_from_source(url, mode=1, max_retries=4):
    """
    Extracteur d'article autonome avec plusieurs méthodes alternatives et une meilleure gestion des erreurs
    
    Args:
        url: L'URL à extraire
        mode: Mode d'extraction initial (1-4)
        max_retries: Nombre maximum de tentatives
    
    Returns:
        Article analysé ou dictionnaire avec informations minimales
    """
    
    if is_shortener_url(url):
        resolved_url = resolve_redirects(url)
        if resolved_url != url:
            url = resolved_url

    try:
        article = Article(url)
        
        # Différentes empreintes de navigateur à essayer
        if mode == 3:
            print(f"Get Article try {mode}")
            article.config.headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': '*',
                'Accept-Encoding': 'gzip;q=1.0, deflate;q=0.9, br;q=0.8, identity;q=0.7, *;q=0.1',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        elif mode == 2:
            print(f"Get Article try {mode}")
            article.config.headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': '*',
                'Accept-Encoding': 'gzip;q=1.0, deflate;q=0.9, br;q=0.8, identity;q=0.7, *;q=0.1',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
            }
        elif mode == 4:
            print(f"Get Article try {mode}")
            article.config.headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': '*',
                'Accept-Encoding': 'gzip;q=1.0, deflate;q=0.9, br;q=0.8, identity;q=0.7, *;q=0.1',
                'Referer': 'https://www.google.com/',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'cross-site',
                'Sec-Fetch-User': '?1',
            }
        elif mode == 5:
            print(f"Get Article try {mode}")
            # Essayer avec un navigateur plus moderne et une langue différente
            article.config.headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': '*',
                'Accept-Encoding': 'gzip;q=1.0, deflate;q=0.9, br;q=0.8, identity;q=0.7, *;q=0.1',
                'Referer': 'https://www.bing.com/',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Pragma': 'no-cache',
            }

        elif mode == 1:
            print(f"Get Article try {mode}")
            # Essayer avec requests directement avec SSL désactivé
            try:
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                
                session = requests.Session()
                session.verify = False  # Désactiver la vérification SSL
                
                response = session.get(url, 
                    headers={
                        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Connection': 'keep-alive',
                    },
                    timeout=15,
                    allow_redirects=True,
                    verify=False  # Désactiver SSL
                )
                
                if response.status_code == 200:
                    article.set_html(response.content)
                    article.parse()
                    
                    result = {
                        'title': article.title or "No Title",
                        'text': article.text or "No Text",
                        'canonical_link': response.url,
                        'image': article.top_image or "",
                        'publish': article.publish_date or ""
                    }
                    
                    if result['text'] != "No Text" and len(result['text']) > 100:
                        return result
                        
            except Exception as requests_error:
                print(f"Échec avec requests direct: {requests_error}")
                # Continuer avec newspaper3k standard
                pass
        
        # Ajouter un petit délai pour éviter de ressembler à un bot
        time.sleep(random.uniform(1, 3))
        
        # Tentative de téléchargement de l'article
        article.download()
        article.parse()
        
        # Extraire les informations essentielles
        result = {
            'title': article.title or "No Title",
            'text': article.text or "No Text",
            'canonical_link': article.canonical_link or url,
            'image': article.top_image or "",
            'publish': article.publish_date or ""
        }
        
        # Ne retourner que si nous avons un contenu significatif
        if result['text'] != "No Text" and len(result['text']) > 100:
            return result
        else:
            # Si le texte est trop court, essayer une autre méthode
            raise Exception("Contenu extrait insuffisant")
            
    except Exception as e:
        print(f"Erreur d'extraction en mode {mode}: {e}")
        
        # Essayer des méthodes alternatives si nous n'avons pas atteint le nombre max de tentatives
        if mode < max_retries:
            return get_article_from_source(url, mode + 1, max_retries)
        
        # Si toutes les méthodes régulières échouent, essayer selenium comme solution de repli
        try:
            cloudscraper_result = try_cloudscraper(url)
            if cloudscraper_result and cloudscraper_result['text'] != "No Text":
                return cloudscraper_result

            return get_article_with_selenium(url)
        except Exception as selenium_error:
            print(f"Échec de la solution de repli Selenium: {selenium_error}")
            
            # Essayer d'extraire l'URL pertinente s'il y a une redirection
            error_url = extract_first_url(str(e))
            if error_url and error_url != url:
                print(f"URL de redirection trouvée: {error_url}")
                try:
                    # Essayer une fois de plus avec l'URL d'erreur
                    return get_article_from_source(error_url, 1, 2)
                except:
                    pass
            
            # Retourner des informations minimales en dernier recours
            return {
                'title': "No Title",
                'text': "No Text",
                'canonical_link': error_url or url,
                'image': "",
                'publish': ""
            }

def clean_url(url: str) -> str:
    """
    Supprime les paramètres de tracking de type utm_* d'une URL.
    - Conserve l'ordre et les autres paramètres éventuels.
    - Nettoie aussi les utm_* éventuels présents dans le fragment (#...).

    ?utm_source=flipboard&utm_content=user/popularmechanics
    ?utm_source=flipboard&utm_content=topic/science
    """
    if not url:
        return url

    try:
        parsed = urlparse(url)

        # Filtrage de la query
        query_params = parse_qsl(parsed.query, keep_blank_values=True)
        filtered_query = [(k, v) for (k, v) in query_params if not k.lower().startswith("utm_")]

        # Filtrage (optionnel) du fragment si c'est une pseudo-query (cas rare mais rencontré)
        frag = parsed.fragment
        if frag and ("=" in frag or "&" in frag):
            frag_params = parse_qsl(frag, keep_blank_values=True)
            filtered_frag = [(k, v) for (k, v) in frag_params if not k.lower().startswith("utm_")]
            new_fragment = urlencode(filtered_frag, doseq=True) if filtered_frag else ""
        else:
            new_fragment = frag  # conserver tel quel si ce n'est pas une pseudo-query

        cleaned = parsed._replace(
            query=urlencode(filtered_query),
            fragment=new_fragment
        )
        return urlunparse(cleaned)

    except Exception:
        # En cas d'URL non parseable, on renvoie l'entrée d'origine
        return url
        
def get_article_with_seleniumOld(url):
    """
    Méthode alternative utilisant Selenium pour les sites avec beaucoup de JavaScript
    ou des protections anti-scraping plus fortes
    """
    try:
        
        print(f"Selenium: {url}")
        
        # Configurer le navigateur headless
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
        
        # Initialiser le driver
        driver = webdriver.Chrome(options=options)
        
        # Ajouter l'automatisation du consentement aux cookies
        driver.get(url)
        time.sleep(5)  # Attendre que la page se charge complètement
        
        # Essayer de gérer les modèles courants de consentement aux cookies
        try:
            # Chercher des boutons de consentement aux cookies courants
            consent_buttons = driver.find_elements(By.XPATH, 
                "//button[contains(text(), 'Accept') or contains(text(), 'I agree') or contains(text(), 'Agree') or contains(text(), 'Accept All') or contains(@id, 'accept') or contains(@class, 'accept')]")
            
            if consent_buttons:
                consent_buttons[0].click()
                time.sleep(2)  # Attendre que les cookies soient acceptés
        except:
            pass
        
        # Obtenir le code source de la page après l'exécution de JavaScript
        html_content = driver.page_source
        
        # Analyser avec BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extraire le titre
        title = soup.title.text if soup.title else "No Title"
        
        # Extraction de contenu de base - cibler le contenu de l'article
        # Ajuster ces sélecteurs en fonction de la structure spécifique du site
        article_selectors = [
            "article", 
            ".article-content", 
            ".entry-content",
            ".post-content",
            "main",
            "#content"
        ]
        
        article_content = None
        for selector in article_selectors:
            content = soup.select_one(selector)
            if content and len(content.text.strip()) > 200:
                article_content = content
                break
        
        text = article_content.text.strip() if article_content else "No Text"
        
        # Extraire l'image principale
        image = ""
        img_tag = soup.select_one("article img, .article-content img, .featured-image img")
        if img_tag and img_tag.get('src'):
            image = img_tag['src']
            # Convertir les URL relatives en absolues
            if image.startswith('/'):
                from urllib.parse import urlparse
                parsed_url = urlparse(url)
                image = f"{parsed_url.scheme}://{parsed_url.netloc}{image}"
                
        # Fermer le navigateur
        driver.quit()
        
        return {
            'title': title,
            'text': text,
            'canonical_link': url,
            'image': image,
            'publish': ""  # L'extraction de date est plus complexe et spécifique au site
        }
        
    except Exception as e:
        print(f"Échec de l'extraction avec Selenium: {e}")
        raise e

def extract_first_url(text):
    """Extraire la première URL du texte, amélioré pour gérer plus de formats d'URL"""
    
    # Motif de reconnaissance d'URL amélioré
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
    urls = re.findall(url_pattern, text)
    
    if urls:
        # Nettoyer l'URL - supprimer la ponctuation finale ou les guillemets
        url = urls[0].rstrip('.,;:\'\"')
        return url
    
    return None

def try_cloudscraper(url):
    """Tentative avec cloudscraper pour contourner Cloudflare"""
    try:
        # import cloudscraper
        # import ssl
        
        # Créer un contexte SSL qui ignore la vérification
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Créer le scraper avec des options SSL désactivées
        scraper = cloudscraper.create_scraper(
            ssl_context=ssl_context,
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        
        # Désactiver les warnings SSL
        # import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        response = scraper.get(url, timeout=15, verify=False)
        
        if response.status_code == 200:
            article = Article('')
            article.set_html(response.content)
            article.parse()
            
            result = {
                'title': article.title or "No Title",
                'text': article.text or "No Text", 
                'canonical_link': url,
                'image': article.top_image or "",
                'publish': article.publish_date or ""
            }
            
            # Vérifier si on a du contenu utile
            if result['text'] != "No Text" and len(result['text']) > 100:
                print(f"Cloudscraper réussi: {len(result['text'])} caractères")
                return result
                
    except Exception as e:
        print(f"Cloudscraper a échoué: {e}")
        return None

def get_article_with_selenium(url):
    """
    Méthode alternative utilisant Selenium pour les sites avec beaucoup de JavaScript
    ou des protections anti-scraping plus fortes - utilise Article pour l'extraction
    """
    try:
        print(f"Selenium: {url}")
        
        # Configurer le navigateur headless
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
        
        # Initialiser le driver
        driver = webdriver.Chrome(options=options)
        
        # Ajouter l'automatisation du consentement aux cookies
        driver.get(url)
        time.sleep(5)  # Attendre que la page se charge complètement
        
        # Essayer de gérer les modèles courants de consentement aux cookies
        try:
            consent_buttons = driver.find_elements(By.XPATH, 
                "//button[contains(text(), 'Accept') or contains(text(), 'I agree') or contains(text(), 'Agree') or contains(text(), 'Accept All') or contains(@id, 'accept') or contains(@class, 'accept')]")
            
            if consent_buttons:
                consent_buttons[0].click()
                time.sleep(2)  # Attendre que les cookies soient acceptés
        except:
            pass
        
        # Obtenir le code source de la page après l'exécution de JavaScript
        html_content = driver.page_source
        
        # Fermer le navigateur maintenant qu'on a le HTML
        driver.quit()
        
        # Utiliser Article pour parser le contenu récupéré par Selenium
        article = Article(url)
        article.set_html(html_content)
        article.parse()
        
        # Extraire les informations avec Article
        result = {
            'title': article.title or "No Title",
            'text': article.text or "No Text",
            'canonical_link': article.canonical_link or url,
            'image': article.top_image or "",
            'publish': article.publish_date or ""
        }
        
        # Vérifier si le contenu extrait est suffisant
        if result['text'] != "No Text" and len(result['text']) > 100:
            print(f"Selenium + Article réussi: {len(result['text'])} caractères")
            return result
        else:
            # Si Article n'a pas bien extrait, faire un fallback manuel
            print("Article n'a pas bien extrait, fallback manuel...")
            return selenium_manual_fallback(html_content, url)
        
    except Exception as e:
        print(f"Échec de l'extraction avec Selenium: {e}")
        try:
            driver.quit()
        except:
            pass
        raise e

def selenium_manual_fallback(html_content, url):
    """Fallback manuel si Article ne fonctionne pas avec le HTML de Selenium"""
    from urllib.parse import urlparse
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extraire le titre
    title_selectors = ['h1', 'title', '.article-title', '.entry-title', '.post-title']
    title = "No Title"
    for selector in title_selectors:
        title_elem = soup.select_one(selector)
        if title_elem and title_elem.text.strip():
            title = title_elem.text.strip()
            break
    
    # Extraction de contenu
    article_selectors = [
        "article", 
        ".article-content", 
        ".entry-content",
        ".post-content",
        "main",
        "#content"
    ]
    
    text = "No Text"
    for selector in article_selectors:
        content = soup.select_one(selector)
        if content and len(content.text.strip()) > 200:
            text = content.text.strip()
            break
    
    # Extraire l'image principale
    image = ""
    img_tag = soup.select_one("article img, .article-content img, .featured-image img")
    if img_tag and img_tag.get('src'):
        image = img_tag['src']
        # Convertir les URL relatives en absolues
        if image.startswith('/'):
            parsed_url = urlparse(url)
            image = f"{parsed_url.scheme}://{parsed_url.netloc}{image}"
    
    return {
        'title': title,
        'text': text,
        'canonical_link': url,
        'image': image,
        'publish': ""
    }

# Exemple d'utilisation
if __name__ == "__main__":
    test_url = "https://www.joanwestenberg.com/p/why-stories-make-you-smarter-than-self-help-books?utm_source=flipboard&utm_content=other"
    # result = get_article_from_source(test_url)
    # print(f"Titre: {result['title']}")
    # print(f"Début du texte: {result['text'][:150]}...")
    # print(f"URL canonique: {result['canonical_link']}")
    # print(f"Image: {result['image']}")