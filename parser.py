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
        """Парсит посты из ВК"""
        self.log(f"Парсинг ВК: https://vk.com/{VK_GROUP}")
        posts = []
        
        try:
            url = f"https://vk.com/{VK_GROUP}"
            response = self.session.get(url, timeout=15)
            
            if response.status_code != 200:
                self.log(f"Ошибка загрузки: {response.status_code}", "ERROR")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Ищем посты
            post_elements = soup.find_all('div', {'data-post-id': True})
            self.log(f"Найдено постов: {len(post_elements)}")
            
            for post in post_elements[:20]:
                try:
                    post_id = post.get('data-post-id')
                    
                    # Текст
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
                    
                except:
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
        except Exception as e:
            self.log(f"Ошибка отправки: {e}", "ERROR")
            return False
    
    def test_telegram(self):
        """Тест подключения к Telegram"""
        self.log("🔍 ТЕСТ TELEGRAM")
        
        test_text = f"✅ ТЕСТ ОТ ПАРСЕРА\nВремя: {datetime.now().strftime('%H:%M:%S')}"
        
        try:
            url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
            data = {
                'chat_id': TG_CHANNEL,
                'text': test_text
            }
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                self.log("✅ ТЕСТ УСПЕШЕН")
                return True
            else:
                self.log(f"❌ Ошибка: {response.status_code}")
                return False
        except Exception as e:
            self.log(f"❌ Ошибка: {e}", "ERROR")
            return False
    
    def catch_up_posts(self):
        """Догоняет пропущенные посты"""
        self.log("=" * 50)
        self.log("ДОГОН ПРОПУЩЕННЫХ ПОСТОВ")
        
        posts = self.get_vk_posts()
        if not posts:
            self.log("❌ Нет постов")
            return 0
        
        self.log(f"📦 Найдено постов: {len(posts)}")
        
        sent = 0
        for post in posts[:10]:
            if self.send_to_telegram(post):
                sent += 1
                self.save_state(post['id'])
                self.log(f"✅ Отправлен {post['id']}")
                time.sleep(2)
        
        self.log(f"✅ Отправлено: {sent}")
        return sent
    
    def check_new_posts(self):
        """Проверяет новые посты"""
        self.log("=" * 50)
        self.log("ПРОВЕРКА НОВЫХ ПОСТОВ")
        
        state = self.load_state()
        posts = self.get_vk_posts()
        
        if not posts:
            self.log("❌ Нет постов")
            return 0
        
        new_posts = []
        if state.get('first_run'):
            new_posts = [posts[0]]
        else:
            for post in posts:
                if post['id'] == state.get('last_post_id'):
                    break
                new_posts.append(post)
        
        self.log(f"📦 Новых постов: {len(new_posts)}")
        
        sent = 0
        for post in reversed(new_posts):
            if self.send_to_telegram(post):
                sent += 1
                self.save_state(post['id'])
                time.sleep(2)
        
        self.log(f"✅ Отправлено: {sent}")
        return sent
    
    def reset_state(self):
        """Сбрасывает состояние"""
        self.save_state(None)
        self.log("🔄 Состояние сброшено")

# ============================================
# ЗАПУСК
# ============================================
if __name__ == "__main__":
    parser = VKParser()
    parser.log("=" * 50)
    parser.log("🚀 ПАРСЕР ЗАПУЩЕН")
    parser.log("=" * 50)
    
    if not TG_TOKEN:
        parser.log("❌ НЕТ TG_TOKEN", "ERROR")
        sys.exit(1)
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1].replace('--', '')
        parser.log(f"📌 КОМАНДА: {cmd}")
        
        if cmd == 'catchup':
            parser.catch_up_posts()
        elif cmd == 'check':
            parser.check_new_posts()
        elif cmd == 'test':
            parser.test_telegram()
        elif cmd == 'reset':
            parser.reset_state()
        else:
            parser.log(f"❌ Неизвестная команда: {cmd}")
    else:
        parser.check_new_posts()
