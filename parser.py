import requests
from bs4 import BeautifulSoup
import json
import os
import sys
import time
import re
from datetime import datetime

# ============================================
# НАСТРОЙКИ
# ============================================
VK_GROUP = os.environ.get('VK_GROUP', 'rddmnt')
TG_TOKEN = os.environ.get('TG_TOKEN', '')
TG_CHANNEL = os.environ.get('TG_CHANNEL', '-1003761499584')

class VKParser:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.state_file = 'vk_parser_state.json'
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] [{level}] {message}")
    
    def load_state(self):
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return {'last_post_id': None, 'first_run': True}
    
    def save_state(self, post_id):
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump({'last_post_id': post_id, 'first_run': False}, f)
        except:
            pass
    
    def get_vk_posts(self):
        """Парсит посты из новой верстки ВК"""
        self.log(f"Парсинг ВК: https://vk.com/{VK_GROUP}")
        posts = []
        
        try:
            url = f"https://vk.com/{VK_GROUP}"
            response = self.session.get(url, timeout=15)
            
            if response.status_code != 200:
                self.log(f"Ошибка загрузки: {response.status_code}", "ERROR")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Ищем посты по data-post-id (новый способ)
            post_elements = soup.find_all('div', {'data-post-id': True})
            self.log(f"Найдено постов с data-post-id: {len(post_elements)}")
            
            for post in post_elements[:30]:
                try:
                    post_id = post.get('data-post-id')
                    
                    # Текст поста
                    text = ""
                    text_elem = post.find('div', class_=re.compile(r'text|Text'))
                    if text_elem:
                        text = text_elem.get_text(strip=True)
                    
                    # Фото
                    photos = []
                    for img in post.find_all('img'):
                        src = img.get('src', '')
                        if 'vk.com' in src or 'userapi.com' in src:
                            clean_url = src.split('?')[0]
                            if clean_url not in photos:
                                photos.append(clean_url)
                    
                    posts.append({
                        'id': post_id,
                        'text': text,
                        'photos': photos[:10]
                    })
                    self.log(f"✅ Пост {post_id}: фото={len(photos)}")
                    
                except Exception as e:
                    continue
            
            self.log(f"✅ Всего постов: {len(posts)}")
            
        except Exception as e:
            self.log(f"❌ Ошибка: {e}", "ERROR")
        
        return posts
    
    def send_to_telegram(self, post):
        """Отправляет пост в Telegram"""
        try:
            if post['photos']:
                media = []
                for i, photo in enumerate(post['photos'][:10]):
                    media_item = {
                        'type': 'photo',
                        'media': photo
                    }
                    if i == 0 and post['text']:
                        media_item['caption'] = post['text'][:1024]
                    media.append(media_item)
                
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMediaGroup"
                data = {
                    'chat_id': TG_CHANNEL,
                    'media': json.dumps(media)
                }
                response = requests.post(url, data=data, timeout=30)
                return response.status_code == 200
            
            if post['text']:
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
                data = {
                    'chat_id': TG_CHANNEL,
                    'text': post['text'][:4096]
                }
                response = requests.post(url, json=data, timeout=30)
                return response.status_code == 200
            
            return False
        except:
            return False
    
    def catch_up_posts(self):
        """Догоняет пропущенные"""
        self.log("=" * 50)
        self.log("ДОГОН ПРОПУЩЕННЫХ")
        
        posts = self.get_vk_posts()
        if not posts:
            self.log("❌ Нет постов")
            return 0
        
        self.log(f"📦 Найдено постов: {len(posts)}")
        
        sent = 0
        for post in posts[:10]:
            if self.send_to_telegram(post):
                sent += 1
                self.log(f"✅ Отправлен {post['id']}")
            time.sleep(2)
        
        self.log(f"✅ Отправлено: {sent}")
        return sent

# ============================================
# ЗАПУСК
# ============================================
if __name__ == "__main__":
    parser = VKParser()
    parser.log("🚀 ПАРСЕР ЗАПУЩЕН")
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1].replace('--', '')
        if cmd == 'catchup':
            parser.catch_up_posts()
        elif cmd == 'test':
            parser.test_telegram()
