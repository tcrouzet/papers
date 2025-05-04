import os
import json
import locale
from datetime import datetime, timedelta, timezone

from masto  import Masto
from papers import Bookmarks
import articles
import tools

os.system('clear')
locale.setlocale(locale.LC_TIME, 'fr_FR')

config = tools.site_yml('_param.yml')

with open(config['news_json'], "r") as file:
    params = json.load(file)

os.makedirs("_output", exist_ok=True)

# Trouver l'ID avec la date la plus récente
latest_id = None
latest_date = None

latest_id = 0
for id_str, info in params.items():
    if int(id_str)>latest_id:
        latest_id = int(id_str)
        latest_date = info["last_date"]

latest_date = datetime.strptime(latest_date, "%Y-%m-%d %H:%M:%S")
latest_date = latest_date.replace(tzinfo=timezone.utc)
latest_date = latest_date + timedelta(hours=1)

end_date = datetime.now(timezone.utc)

bookmarks = Bookmarks(config)
bookmarks.get_new_bookmarks()

# Get bookmarks from Masotodon
masto = Masto(config)
posts_m = masto.get_posts( config['masto_user'], latest_date, end_date)

for post in posts_m:
    post_datetime = datetime.fromisoformat(post['date'])
    filename = post_datetime.strftime("%Y-%m-%d-%H%M") + "-masto.md"
    filepath = bookmarks.file_path(filename)

    if not os.path.exists(filepath):
        if "crouzet" in post['url']:
            continue
        article = articles.get_article_from_source(post['url'])
        if post['source'] == 'crouzet':
            comments = post['title']
            source = "mastodon"
        else:
            comments = ""
            source = post['source']
        bookmarks.save_bookmark(article, filename, post['url'], post_datetime, comments.strip(), source)

 
posts_b = bookmarks.get_bookmarks(latest_date, end_date)


current_date = datetime.now()
formatted_current_date = current_date.strftime("%d %B %Y")

new_id = latest_id + 1

xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<newsletter>
    <metadata>
        <title>De ma terrasse #{new_id}</title>
        <subtitle>Ma sélection du dimanche : **{len(posts_b)}** liens et une photo prise depuis ma terrasse.</subtitle>
        <publication_date>{formatted_current_date}</publication_date>
        <links_number>{len(posts_b)}</links_number>
    </metadata>
        <links>"""


last_date = None
id = 1

for post in posts_b:

    post_date = datetime.fromisoformat(post['date']).date()
    formatted_date = post_date.strftime("%d %B %Y")
    source = post.get('source', '')

    comment = post.get('comment', '').strip()
    if comment == "None" or comment == "":
        print("No comment found for post")
        comment = post.get('text','').strip()

    comment = comment.replace("&", "&amp;")
    comment = comment.replace("\n", " ")    

    xml +=f"""
        <link id="{id}">
            <title>{post['title'].strip()}</title>
            <url>{post['url']}</url>
            <publication_date>{post_date}</publication_date>
            <comment>{comment}</comment>
            <source>{source.strip()}</source>
        </link>"""
    
    id += 1

xml += """
    </links>
</newsletter>"""

with open(os.path.join("_output", "test.xml"), 'w', encoding='utf-8') as file:
    file.write(xml)

params[str(new_id)] = {"last_date": end_date.strftime("%Y-%m-%d %H:%M:%S")}
print(params)

# Sauvegarder dans un fichier JSON
with open(config['news_json'], "w") as file:
    json.dump(params, file, indent=4)

