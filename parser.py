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

class VKtoTGParser:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'
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
        except Exception as e:
            self.log(f"Ошибка сохранения: {e}", "ERROR")
    
    def get_vk_posts(self):
        """Парсит посты из ВК с улучшенным поиском"""
        self.log(f"Парсинг ВК: https://vk.com/{VK_GROUP}")
        posts = []
        
        try:
            # Пробуем разные варианты URL
            urls = [
                f"https://vk.com/{VK_GROUP}",
                f"https://m.vk.com/{VK_GROUP}",  # мобильная версия
                f"https://vk.com/public{VK_GROUP}" if VK_GROUP.isdigit() else None
            ]
            
            html = None
            for url in urls:
                if not url: continue
                try:
                    self.log(f"Пробуем: {url}")
                    response = self.session.get(url, timeout=10)
                    if response.status_code == 200:
                        html = response.text
                        self.log(f"✅ Загружено: {url}")
                        break
                except:
                    continue
            
            if not html:
                self.log("❌ Не удалось загрузить страницу", "ERROR")
                return []
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Разные селекторы для поиска постов
            selectors = [
                'div.post',
                'div[data-post-id]',
                'div.wall_post',
                'div._post_content',
                'div.page_block'
            ]
            
            post_elements = []
            for selector in selectors:
                post_elements = soup.select(selector)
                if post_elements:
                    self.log(f"✅ Найдено постов по селектору '{selector}': {len(post_elements)}")
                    break
            
            if not post_elements:
                self.log("❌ Посты не найдены", "ERROR")
                # Сохраняем HTML для отладки
                with open('debug.html', 'w', encoding='utf-8') as f:
                    f.write(html)
                self.log("📁 HTML сохранен в debug.html для анализа")
                return []
            
            for post in post_elements[:20]:
                try:
                    post_data = self.parse_post(post)
                    if post_data:
                        posts.append(post_data)
                except Exception as e:
                    continue
            
            # Сортируем по ID
            posts.sort(key=lambda x: x['id'], reverse=True)
            self.log(f"📦 Всего постов: {len(posts)}")
            
            if posts:
                self.log(f"📌 Последний ID: {posts[0]['id']}")
                self.log(f"📌 Последний текст: {posts[0]['text'][:50]}...")
            
        except Exception as e:
            self.log(f"❌ Ошибка: {e}", "ERROR")
        
        return posts
    
    def parse_post(self, post_element):
        """Парсит один пост"""
        # ID поста
        post_id = None
        
        # Из data-post-id
        if post_element.get('data-post-id'):
            post_id = post_element.get('data-post-id')
        
        # Из ссылки
        if not post_id:
            link = post_element.find('a', {'class': 'post_link'})
            if link and link.get('href'):
                match = re.search(r'wall(-?\d+_\d+)', link['href'])
                if match:
                    post_id = match.group(1)
        
        # Из id элемента
        if not post_id and post_element.get('id'):
            match = re.search(r'post(\d+)_(\d+)', post_element.get('id'))
            if match:
                post_id = f"{match.group(1)}_{match.group(2)}"
        
        if not post_id:
            return None
        
        # Текст
        text = ""
        text_selectors = ['div.wall_post_text', 'div.post_text', 'div._post_content']
        for selector in text_selectors:
            text_elem = post_element.select_one(selector)
            if text_elem:
                text = text_elem.get_text(strip=True)
                break
        
        # Фото
        photos = []
        for img in post_element.find_all('img'):
            src = img.get('src', '')
            if 'vk.com' in src or 'userapi.com' in src:
                clean_url = src.split('?')[0]
                if clean_url not in photos:
                    photos.append(clean_url)
        
        return {
            'id': post_id,
            'text': text,
            'photos': photos[:10],
            'url': f"https://vk.com/wall{post_id}"
        }
    
    def send_to_telegram(self, post):
        """Отправляет пост в Telegram"""
        self.log(f"Отправка поста {post['id']}")
        
        try:
            if post['photos']:
                media = []
                for i, photo in enumerate(post['photos']):
                    media.append({
                        'type': 'photo',
                        'media': photo
                    })
                
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMediaGroup"
                data = {
                    'chat_id': TG_CHANNEL,
                    'media': json.dumps(media)
                }
                response = requests.post(url, data=data, timeout=30)
                
                if response.status_code == 200:
                    self.log(f"✅ Отправлено {len(post['photos'])} фото")
                    return True
                else:
                    self.log(f"❌ Ошибка фото: {response.status_code}")
            
            if post['text']:
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
                data = {
                    'chat_id': TG_CHANNEL,
                    'text': post['text'][:4096]
                }
                response = requests.post(url, json=data, timeout=30)
                
                if response.status_code == 200:
                    self.log(f"✅ Текст отправлен")
                    return True
                else:
                    self.log(f"❌ Ошибка текста: {response.status_code}")
            
            return False
            
        except Exception as e:
            self.log(f"❌ Ошибка: {e}", "ERROR")
            return False
    
    def check_new_posts(self):
        """Проверяет новые посты"""
        self.log("=" * 50)
        self.log("ПРОВЕРКА НОВЫХ ПОСТОВ")
        
        state = self.load_state()
        self.log(f"Состояние: last_id={state['last_post_id']}")
        
        posts = self.get_vk_posts()
        if not posts:
            self.log("❌ Нет постов")
            return 0
        
        new_posts = []
        if state.get('first_run', True) or not state['last_post_id']:
            self.log("🆕 Первый запуск - отправляем последний пост")
            new_posts = [posts[0]] if posts else []
        else:
            for post in posts:
                if post['id'] == state['last_post_id']:
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
    
    def catch_up_posts(self):
        """Догоняет пропущенные"""
        self.log("=" * 50)
        self.log("ДОГОН ПРОПУЩЕННЫХ")
        
        posts = self.get_vk_posts()
        if not posts:
            self.log("❌ Нет постов")
            return 0
        
        self.log(f"📦 Всего постов: {len(posts)}")
        
        sent = 0
        for post in reversed(posts[:10]):
            if self.send_to_telegram(post):
                sent += 1
                self.save_state(post['id'])
                time.sleep(2)
        
        self.log(f"✅ Отправлено: {sent}")
        return sent
    
    def reset_state(self):
        """Сброс состояния"""
        self.save_state(None)
        self.log("🔄 Состояние сброшено")
    
    def test_telegram(self):
        """Тест Telegram"""
        self.log("🔍 ТЕСТ TELEGRAM")
        
        test_text = f"✅ Тест от парсера VK→TG\n\nВремя: {datetime.now().strftime('%H:%M:%S')}\nГруппа: {VK_GROUP}"
        
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        data = {'chat_id': TG_CHANNEL, 'text': test_text}
        
        try:
            response = requests.post(url, json=data, timeout=10)
            if response.status_code == 200:
                self.log("✅ Тест успешен")
                return True
            else:
                self.log(f"❌ Ошибка: {response.status_code}")
                return False
        except Exception as e:
            self.log(f"❌ Ошибка: {e}")
            return False

# ============================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================
def main():
    parser = VKtoTGParser()
    
    if not TG_TOKEN:
        parser.log("❌ Нет TG_TOKEN", "ERROR")
        return
    
    parser.log(f"✅ Парсер запущен")
    parser.log(f"📌 VK_GROUP: {VK_GROUP}")
    parser.log(f"📌 TG_CHANNEL: {TG_CHANNEL}")
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1].replace('--', '')
        parser.log(f"📌 Команда: {cmd}")
        
        if cmd == 'check':
            parser.check_new_posts()
        elif cmd == 'catchup':
            parser.catch_up_posts()
        elif cmd == 'reset':
            parser.reset_state()
        elif cmd == 'test':
            parser.test_telegram()
        else:
            parser.log(f"❌ Неизвестная команда: {cmd}")
    else:
        parser.check_new_posts()

if __name__ == "__main__":
    main()
