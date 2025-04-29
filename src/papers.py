"""Remplace les daily notes dans Obsidian par leur contenu"""

import os, re
from datetime import datetime, timezone  
from dateutil import parser

import tools
import articles

class Bookmarks:

    def __init__(self, config):
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.parent_dir = os.path.dirname(script_dir) + os.sep
        script_dir = self.parent_dir

        self.sources_dir = config['obsidian']

    def file_path(self, file):
        return os.path.join(self.sources_dir, file)

    def read_markdown(self, file_path):
        """Retourne contenu d'un fichier MD."""
        try:
            with open(os.path.join(self.sources_dir, file_path), 'r', encoding='utf-8', errors='ignore') as file:
                return file.read()
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
        return None

    def save_markdown(self, file_path, content):
        """Remplace le contenu existant d'un fichier MD par le nouveau contenu."""
        with open(os.path.join(self.sources_dir, file_path), 'w', encoding='utf-8') as file:
            file.write(content)
            return True
        return False

    def extract_first_url(self, error_message):
        # Utiliser une expression régulière pour trouver les URLs
        urls = re.findall(r'(https?://[^\s]+)', error_message)
        if urls:
            return urls[0]  # Retourne le premier URL trouvé
        return None
    
    def get_bookmark_created(self, file):
        """ Retourne date de bookmark en utilisant dateutil.parser pour plus de flexibilité """
        if file.endswith('.md'):
            try:
                # Extrait la partie date du nom de fichier
                date_str = file.replace(".md", "")
                
                # Gère le cas des fichiers avec suffixe comme 2025-02-25-1302_2.md
                if "_" in date_str:
                    date_str = date_str.split("_")[0]

                date_str = date_str.replace("-masto", "")
                    
                # Convertit le format de nom de fichier en format ISO
                parts = date_str.split("-")
                if len(parts) == 4 and len(parts[3]) == 4:  # Format YYYY-MM-DD-HHMM
                    # Reformate en YYYY-MM-DDTHH:MM:00
                    date_str = f"{parts[0]}-{parts[1]}-{parts[2]}T{parts[3][:2]}:{parts[3][2:]}:00"
                    
                # Parse avec dateutil pour plus de flexibilité
                dt = parser.parse(date_str)
                
                # Assure que la date est timezone-aware
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                    
                return dt
                
            except Exception as e:
                print(f"Erreur de parsing de date pour {file}: {e}")
                exit()
        return None

    def has_yaml_header(self, content):
        # Diviser le contenu en lignes
        lines = content.splitlines()

        # Vérifier si le contenu commence par un en-tête YAML
        if len(lines) > 0 and lines[0].strip() == '---':
            # Chercher la fin de l'en-tête YAML
            for line in lines[1:]:
                if line.strip() == '---':
                    return True
        return False
    
    def extract_yaml_header(self, content):
        """Extrait l'en-tête YAML d'un contenu markdown."""
        header = {}
        if self.has_yaml_header(content):
            # Extract the YAML front matter
            yaml_content = content.split('---')[1].strip()
            for line in yaml_content.splitlines():
                # print(line)

                if ':' in line:
                    key, value = line.split(':', 1)
                    header[key.strip()] = value.strip().strip('"')
                    # if key=="public":
                    #     print("PUBLIC")
                    #     print(header[key.strip()])

        return header

    def get_first_para(self, content):
        content_parts = content.split('---', 2)
        if len(content_parts) >= 3:
            main_content = content_parts[2].strip()
            
            # Ignore le titre (première ligne commençant par #)
            content_lines = main_content.split('\n')
            content_without_title = '\n'.join(line for line in content_lines if not line.strip().startswith('#'))
            
            # Ignore la ligne d'image si elle existe
            content_without_image = '\n'.join(line for line in content_without_title.split('\n') if not line.strip().startswith('!['))
            
            # Récupère le premier paragraphe non vide
            paragraphs = [p.strip() for p in content_without_image.split('\n\n')]
            first_paragraph = next((p for p in paragraphs if p), '')

            return first_paragraph

        return ""


    def get_article(self, new_source, created):
        if isinstance(new_source, dict):
            image = new_source['image']
            publish = new_source.get('publish', created)
            title = new_source['title']
            text = new_source.get('text', "")
            canonical_link = new_source.get('canonical_link', "")
        else:
            title = new_source.title
            text = new_source.text
            canonical_link = new_source.canonical_link
            image = new_source.top_image if new_source.top_image else None
            publish = new_source.publish_date.isoformat() if new_source.publish_date else None
            if not publish:
                publish = created
        title = title.replace('"', "'")
        return title, text, canonical_link, image, publish


    def format_article(self, new_source, url, created, comment="", source=""):

        title, text, canonical_link, image, publish = self.get_article(new_source, created)
        comment= comment.replace('"', "'")

        if canonical_link == "":
            canonical_link = url

        if image:
            text = f"![image]({image})\n\n{text}"

        header = f"---\ntitle: \"{title}\"\ndate: {publish}\nurl: {canonical_link}\nimage: {image}\nadd: {created}\nadd_source: {url}\ncomment: \"{comment}\"\nsource: \"{source}\"\npublic: True\n---\n\n"
        content = f"{header}# {title}\n\n{text}"
        return content


    def save_bookmark(self, article, file, url, created, comment="", source=""):
        if article:
            new_content = self.format_article(article, url, created, comment, source)
            if self.save_markdown(file, new_content):
                return True
        print("Save_bookmark bug",url)
        return False


    def extract_comment_from_content(self, content):
        """
        Extrait le texte de commentaire du contenu.
        Le commentaire est tout le texte qui n'est pas une URL.
        Suppose qu'il n'y a qu'un seul bloc de commentaire par fichier.
        Nettoie les sauts de ligne et les espaces superflus.
        """
        # Identifie toutes les URLs dans le contenu
        url_pattern = re.compile(r'https?://\S+')
        urls = url_pattern.findall(content)
        
        # Retire toutes les URLs du contenu
        comment_text = content
        for url in urls:
            comment_text = comment_text.replace(url, '')
        
        # Remplace d'abord les sauts de ligne par des espaces
        comment_text = comment_text.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
        
        # Nettoie les espaces multiples et les espaces en début/fin de chaîne
        comment_text = re.sub(r'\s+', ' ', comment_text).strip()
        
        return comment_text if comment_text else ""


    def get_new_bookmarks(self):
        """ Parcours tous les fichiers MD dans sources_dir """
        url_pattern = re.compile(r'http[s]?://\S+')

        for root, dirs, files in os.walk(self.sources_dir):
            for file in files:

                created = self.get_bookmark_created(file)
                if not created:
                    continue
                
                content = self.read_markdown(file)
                if not content:
                    continue
                
                if self.has_yaml_header(content):
                    continue

                print(created)

                # Find all URLs
                urls = url_pattern.findall(content)
                urls_index = 0
                for url in urls:
                    if urls_index == 0:
                        file_save = file
                    else:
                        file_save = file.replace(".md", f"_{urls_index}.md")
                    article = articles.get_article_from_source(url)
                    com = self.extract_comment_from_content(content)
                    self.save_bookmark(article, file_save, url, created, com)
                    urls_index += 1

    def get_content(self,content):
        article_content = ""
        content_parts = content.split('---', 2)
        
        if len(content_parts) >= 3:
            main_content = content_parts[2].strip()
            
            # Trouvons le titre (première ligne commençant par #)
            lines = main_content.split('\n')
            title_index = -1
            
            for i, line in enumerate(lines):
                if line.strip().startswith('#'):
                    title_index = i
                    break
            
            # Si on a trouvé un titre, on prend tout ce qui est après
            if title_index != -1:
                article_content = '\n'.join(lines[title_index+1:]).strip()

        return article_content

    
    def get_bookmarks(self, start_date, end_date):
        """Retourne les bookmarks entre deux dates avec titre et URL."""
        bookmarks = []
        for root, dirs, files in os.walk(self.sources_dir):
            sorted_files = sorted(files, reverse=True)
            for file in sorted_files:

                if file.startswith("."):
                    continue

                content = self.read_markdown(file)
                if not content:
                    print(f"No makdown {file}")
                    continue

                yaml_header = self.extract_yaml_header(content)
                if not yaml_header:
                    print(f"No YALM header {file}")
                    continue

                if yaml_header.get('public','true').lower() == 'false':
                    continue

                publish_date = self.get_bookmark_created(file)

                if start_date <= publish_date <= end_date:
                    # print(start_date, publish_date, end_date, file)
                    print(file)
                    
                    bookmarks.append({
                        'title': yaml_header.get('title'),
                        'url': yaml_header.get('url'),
                        'date': publish_date.isoformat(),
                        'source': yaml_header.get('source',''),
                        'comment': yaml_header.get('comment', "").strip(),
                        'text': self.get_content(content)
                    })
        return bookmarks

    #Once a time
    def modify_bookmarks(self):
        bookmarks = self.load_json_file(self.bookmarks)
        for i, source in enumerate(bookmarks):
            article = self.get_article(source['id'])
            bookmarks[i]['image'] = article['image']
        self.save_json(self.bookmarks, bookmarks)



if __name__ == '__main__':
    os.system('clear')

    config = tools.site_yml('_param.yml')

    bookmarks = Bookmarks(config)

    if False:
        # Test Get Article
        test_url ="https://www.techrepublic.com/article/news-prompt-engineering-ai-jobs-obsolete/?utm_source=flipboard&utm_content=user/TechRepublic"
        # print( articles.get_article(test_url))
        print( bookmarks.get_article_from_source(test_url) )
    else:
        bookmarks.get_new_bookmarks()
