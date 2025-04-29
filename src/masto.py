import requests, os, re, json, sys
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import csv
import time


class Masto:

    def __init__(self, config):

        self.masdodon_instance = config['masdodon_instance']
        self.access_token = config['mastodon_token']

        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.media = os.path.join(script_dir,"_masto_media")

        self.sources_dir = config['obsidian']

        self.headers = {
            'Authorization': f'Bearer {self.access_token}'
        }

        self.calls_count = 0
        self.wait = 2.5 * 60


    def test_limits(self):
        try:
            if self.calls_count == 0:
                limits = self.get_limits()
                self.calls_count = limits['remaining']
                if self.calls_count < 50:
                    time.sleep(self.wait)
                    self.test_limits()
            self.calls_count -= 1
        except Exception as e:
            print(f"Erreur lors de la vérification des limites: {e}")
            time.sleep(self.wait)  # Pause de sécurité


    def get_user_posts(self, user_id, start_date, end_date):
        url = f"{self.masdodon_instance}/api/v1/accounts/{user_id}/statuses"
        params = {
            'limit': 40,  # Adjust as needed
            'since': start_date,
            'until': end_date
        }
        self.test_limits()
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()


    def extract_message_and_links(self, post_content):
        # Parse the HTML content
        soup = BeautifulSoup(post_content, 'html.parser')
    
        # Extract the text content
        message = soup.get_text()

        # Extract URLs, excluding user mentions
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']

            if "tcrouzet.com" in href or "tcrouzet.substack.com" in href:
                return None, None

            # Exclude links that are mentions (contain '/@')
            if '/@' not in href and '/tags/' not in href:
                links.append(href)
            message = message.replace(href, ' ')

        if links:
            return message, links
        return message, None


    def dump(self, data, filename="dump.txt"):
        """Dump une variable dans un fichier texte."""
        with open(filename, "a", encoding="utf-8") as f:
            formatted_json = json.dumps(data, indent=4, ensure_ascii=False)
            f.write(formatted_json + "\n")


    def all_extract(self, posts):
        bookmarks = []
        for post in posts:

            if post.get('in_reply_to_id'):
                continue

            self.dump(post)
    
            # Check if the post is a boost
            if post.get('reblog') is not None:
                # Extract content from the original post
                original_content = post['reblog']['content']
                # print(original_content)
                message, links = self.extract_message_and_links(original_content)
                post_date = post['reblog']['created_at']
                post_crouzet = f"[{post['reblog']['account']['display_name']}]({post['reblog']['account']['url']})"

            else:
                # Extract content from the current post
                message, links = self.extract_message_and_links(post['content'])
                post_date = post['created_at']
                post_crouzet = "crouzet"

            if links:
                bookmarks.append({
                    'title': message,
                    'url': links[0],
                    'date': post_date,
                    'source': post_crouzet
                })
        return bookmarks

    def get_posts(self, user_id, start_date, end_date):
        posts = self.get_user_posts(user_id, start_date, end_date)
        return self.all_extract(posts)

    def get_limits(self):
        # First, make a lightweight request to check rate limits
        # We'll use the verify_credentials endpoint which is typically lightweight
        check_url = f"{self.masdodon_instance}/api/v1/accounts/verify_credentials"
        try:
            check_response = requests.get(check_url, headers=self.headers)
            check_response.raise_for_status()
            
            # Extract rate limit headers
            limit = check_response.headers.get('X-RateLimit-Limit', 'unknown')
            remaining = check_response.headers.get('X-RateLimit-Remaining', 'unknown')
            reset_str = check_response.headers.get('X-RateLimit-Reset', 'unknown')
            
            # Convert limit and remaining to integers if possible
            try:
                limit = int(limit)
            except (ValueError, TypeError):
                limit = 'unknown'
                
            try:
                remaining = int(remaining)
            except (ValueError, TypeError):
                remaining = 'unknown'
            
            # Parse reset time (ISO 8601 format)
            reset_time = None
            seconds_until_reset = None
            
            if reset_str != 'unknown':
                try:
                    # Parse ISO 8601 date string
                    reset_time = datetime.fromisoformat(reset_str.replace('Z', '+00:00'))
                    
                    # Calculate seconds until reset
                    now = datetime.now(reset_time.tzinfo)
                    seconds_until_reset = max(0, int((reset_time - now).total_seconds()))
                except (ValueError, TypeError):
                    reset_time = reset_str
            
            rate_limit = {
                'limit': limit,
                'remaining': remaining,
                'reset_str': reset_str,
                'reset_time': reset_time,
                'seconds_until_reset': seconds_until_reset
            }

            return rate_limit
            
        except requests.exceptions.HTTPError as e:
            print(e)
            sys.exit("Limits problem")


    def find_user_id(self, handle):
        # Parse the handle
        if not handle.startswith('@'):
            handle = '@' + handle
            
        # Extract username and instance
        match = re.match(r'@([^@]+)@(.+)', handle)
        if not match:
            return {"error": "Invalid handle format. Expected @username@instance"}
        
        username, instance = match.groups()

         # Search for the user
        search_url = f"{self.masdodon_instance}/api/v1/accounts/search"
        params = {
            'q': f"{username}@{instance}",
            'limit': 1
        }
        
        self.test_limits()
        search_response = requests.get(search_url, headers=self.headers, params=params)
        search_response.raise_for_status()
        search_results = search_response.json()
        
        if not search_results:
            return {"error": f"User {handle} not found"}
        
        user_id = search_results[0]['id']
        return user_id, username, instance


    def follow_user_by_handle(self, handle):
        
        user_id, _, _ = self.find_user_id(handle)
        # print(user_id)
        
        # Check if already following
        relationships_url = f"{self.masdodon_instance}/api/v1/accounts/relationships"
        relationship_params = {
            'id[]': user_id
        }
        
        self.test_limits()
        relationship_response = requests.get(relationships_url, headers=self.headers, params=relationship_params)
        relationship_response.raise_for_status()
        relationships = relationship_response.json()
        # print(relationships)
        
        if relationships and relationships[0].get('following'):
            return {
                "status": 0,
                "message": f"Already following {handle} (ID: {user_id})"
            }
        
        # If not following, follow the user
        try:

            follow_url = f"{self.masdodon_instance}/api/v1/accounts/{user_id}/follow"
            self.test_limits()
            follow_response = requests.post(follow_url, headers=self.headers)
            follow_response.raise_for_status()
            
            result = follow_response.json()
            return {
                "status": 1,
                "message": f"Successfully followed {handle} (ID: {user_id})",
                "details": result
            }
        
        except Exception as e:
            return {
                "status": -1,
                "message": f"Failed to follow {handle} (ID: {user_id})",
                "details": str(e)
            }

    def remove_account_csv(self, data_rows, account):
        """
        Supprime un compte de data_rows.
        
        Args:
            data_rows: Liste des lignes de données
            account: Compte à supprimer
        
        Returns:
            list: data_rows mis à jour
        """
        for i, row in enumerate(data_rows[:]):  # Créer une copie pour itérer
            if len(row) >= 2 and row[1].strip() == account:
                data_rows.remove(row)
                break
        
        return data_rows


    def save_csv(self, data_rows, csv_file_path):        
        # Écrire le fichier mis à jour
        with open(csv_file_path, 'w', newline='', encoding='utf-8') as file:
            csv_writer = csv.writer(file)
            csv_writer.writerows(data_rows)


    def follow_accounts_from_csv(self, csv_file_path):
        """
        Lit un fichier CSV avec deux colonnes (liste, compte) et suit chaque compte,
        en attendant un nombre spécifié de minutes entre chaque suivi réussi.
        
        Args:
            csv_file_path (str): Chemin vers le fichier CSV
            wait_minutes (int): Minutes à attendre entre chaque suivi réussi
        """

        # Lire tout le contenu du CSV dans une liste
        all_rows = []
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            all_rows = list(csv_reader)

        # Déterminer si la première ligne est un en-tête
        if all_rows and all_rows[0][0].lower() in ['liste', 'list', 'nom_liste']:
            data_rows = all_rows[1:]  # Toutes les lignes sauf la première
            print("En-tête détecté, première ligne ignorée")
        else:
            data_rows = all_rows  # Toutes les lignes

        data_rows_saved = data_rows

        for row in data_rows:
            if len(row) < 2 or not row[1].strip():
                print(f"Ligne invalide ignorée: {row}")
                continue
            
            liste = row[0].strip()
            compte = row[1].strip()
            
            print(f"\nTraitement de {compte}")

            result = self.follow_user_by_handle(compte)
            print(result['message'])
            if result["status"] == -1:
                continue

            data_rows_saved = self.remove_account_csv(data_rows_saved, compte)
            self.save_csv(data_rows_saved, csv_file_path)

            if result["status"] == 1:
                time.sleep(self.wait)
        
        sys.exit("End CSV")


    def get_notifications_with_media(self, start_date, end_date):
        """
        Récupère toutes les notifications (mentions et messages directs) adressées à l'utilisateur
        sur une période donnée et sauvegarde les images associées.
        
        Args:
            start_date (str): Date de début au format ISO 8601
            end_date (str): Date de fin au format ISO 8601
            save_dir (str, optional): Répertoire où sauvegarder les images et les métadonnées
                                    Par défaut, utilise le répertoire sources_dir
        
        Returns:
            list: Liste des notifications avec leurs métadonnées
        """
        
        os.makedirs(self.media, exist_ok=True)
        
        # Fichier pour enregistrer les métadonnées
        metadata_file = os.path.join(self.media, "notifications_metadata.json")

        params = {
            'types[]': ['mention', 'direct'],  # Mentions et messages directs
            'limit': 300,  # Ajuster selon les besoins
            'since': start_date,
            'until': end_date,
            'since_id': None,
            'max_id': None
        }

        if os.path.exists(metadata_file):
            with open(metadata_file, 'r', encoding='utf-8') as f:
                all_notifications = json.load(f)

                all_notifications.sort(key=lambda x: int(x['id']), reverse=True)
                since_id = all_notifications[0]['id']
                if since_id:
                    params['since_id'] = since_id

        else:
            all_notifications = []
        
        # Récupérer les notifications
        url = f"{self.masdodon_instance}/api/v1/notifications"
        
        max_id = None
        
        while True:
            self.test_limits()
            
            if max_id:
                params['max_id'] = max_id
            
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            notifications = response.json()
            
            if not notifications:
                break
            
            # Traiter chaque notification
            for notification in notifications:
                status = notification.get('status', {})
                if not status:
                    continue
                
                # Extraire les informations pertinentes
                notification_data = {
                    'id': notification['id'],
                    'type': notification['type'],
                    'created_at': notification['created_at'],
                    'account': {
                        'id': notification['account']['id'],
                        'username': notification['account']['username'],
                        'display_name': notification['account']['display_name'],
                        'url': notification['account']['url']
                    },
                    'status': {
                        'id': status.get('id'),
                        'content': status.get('content'),
                        'url': status.get('url'),
                        'media_attachments': []
                    }
                }
                
                # Traiter les médias attachés
                media_attachments = status.get('media_attachments', [])
                for media in media_attachments:
                    if media.get('type') == 'image':
                        media_url = media.get('url')
                        if media_url:
                            # Générer un nom de fichier unique
                            media_filename = f"{notification['id']}_{media['id']}.jpg"
                            media_path = os.path.join(self.media, media_filename)
                            
                            # Télécharger l'image
                            try:
                                self.test_limits()
                                media_response = requests.get(media_url)
                                media_response.raise_for_status()
                                
                                with open(media_path, 'wb') as f:
                                    f.write(media_response.content)
                                
                                # Ajouter les informations du média à la notification
                                notification_data['status']['media_attachments'].append({
                                    'id': media['id'],
                                    'type': media['type'],
                                    'url': media_url,
                                    'local_path': media_path,
                                    'description': media.get('description')
                                })
                                
                                print(f"Image sauvegardée: {media_path}")
                            except Exception as e:
                                print(f"Erreur lors du téléchargement de l'image {media_url}: {e}")
                
                all_notifications.append(notification_data)
            
            # Préparer pour la prochaine page
            max_id = notifications[-1]['id']
        
        # Sauvegarder les métadonnées
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(all_notifications, f, ensure_ascii=False, indent=4)
        
        print(f"Métadonnées sauvegardées dans {metadata_file}")
        return all_notifications
