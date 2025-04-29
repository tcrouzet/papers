from flask import Flask, render_template, request, jsonify
import os
import markdown
from papers import Bookmarks

import tools

config = tools.site_yml('_param.yml')

os.system('clear')
book = Bookmarks(config)

app = Flask(__name__)


def parse_yaml_from_content(content):
    yaml_data = {}
    
    # Trouver les délimiteurs YAML
    yaml_start = content.find('---')
    yaml_end = content.find('---', yaml_start + 3)
    
    if yaml_start != -1 and yaml_end != -1:
        # Extraire le contenu du YAML
        yaml_content = content[yaml_start+3:yaml_end].strip()
        
        # Traiter chaque ligne
        for line in yaml_content.splitlines():
            if ':' in line:
                key, value = line.split(':', 1)
                yaml_data[key.strip()] = value.strip()
    
    return yaml_data
    

def extract_main_text(content):
    # Chercher la première occurrence d'un titre de niveau 1
    title_start = content.find('# ')
    if title_start != -1:
        # Trouver la fin de la ligne du titre
        title_end = content.find('\n', title_start)
        if title_end != -1:
            # Récupérer le texte principal après le titre
            main_text = content[title_end+1:].strip()
            return main_text

    return ""

def load_bookmarks_from_markdown():
    bookmarks = []
        
    files = [filename for filename in os.listdir(book.sources_dir) if filename.endswith('.md')]
    files.sort(reverse=True)

    for filename in files:
        if filename.endswith('.md'):
            content= book.read_markdown(filename)
            if content:
                meta = parse_yaml_from_content(content)
                bookmark = {
                    'id': filename.replace('.md', ''),
                    'title': meta.get('title', 'Titre non disponible'),
                    'link': meta.get('url', 'URL non disponible'),
                    'created': meta.get('created', 'Date non disponible'),
                    'text': markdown.markdown(extract_main_text(content)),
                    'image': meta.get('image', None),
                    'publish':meta.get('publish', None)
                }
                bookmarks.append(bookmark)
    return bookmarks

bookmarks = load_bookmarks_from_markdown()
print("Ouvrez http://127.0.0.1:5000/ dans votre navigateur.")

@app.route('/')
def index():
    print("Route / appelée")
    return render_template('index.html')

@app.route('/api/bookmarks')
def api_bookmarks():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    start = (page - 1) * per_page
    end = start + per_page
    data = bookmarks[start:end]
    return jsonify(data)

@app.route('/article/<article_id>')
def article(article_id):
    print(f"Route /article/{article_id} appelée")
    article_data = next((item for item in bookmarks if item["id"] == article_id), None)
    if article_data:
        return render_template('article.html', article=article_data, content=article_data["text"])
    else:
        print(f"Erreur : Article {article_id} non trouvé.")
        return "Article not found", 404

if __name__ == '__main__':
    app.run(debug=True)