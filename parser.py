import requests
import os
import sys
import time
import json
from datetime import datetime

# ============================================
# НАСТРОЙКИ
# ============================================
VK_GROUP = os.environ.get('VK_GROUP', 'rddmnt')
TG_TOKEN = os.environ.get('TG_TOKEN', '')
TG_CHANNEL = os.environ.get('TG_CHANNEL', '-1003761499584')

class VKApiParser:
    def __init__(self):
        self.state_file = 'vk_api_state.json'
        self.vk_api_url = "https://api.vk.com/method/wall.get"
        self.vk_version = "5.131"
        
    def log(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    
    def load_state(self):
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except:
            return {'last_post_id': None, 'first_run': True}
    
    def save_state(self, post_id):
        with open(self.state_file, 'w') as f:
            json.dump({'last_post_id': post_id, 'first_run': False}, f)
    
    def get_vk_posts_api(self):
        """Получает посты через официальный API ВК (без токена)"""
        self.log(f"Запрос к API ВК для группы: {VK_GROUP}")
        
        try:
            # Определяем owner_id
            if VK_GROUP.isdigit():
                owner_id = f"-{VK_GROUP}"  # Для групп нужно с минусом
                params = {
                    'owner_id': owner_id,
                    'count': 10,
                    'v': self.vk_version
                }
            else:
                # По короткому имени
                params = {
                    'domain': VK_GROUP,
                    'count': 10,
                    'v': self.vk_version
                }
            
            self.log(f"Параметры запроса: {params}")
            
            response = requests.get(self.vk_api_url, params=params, timeout=10)
            data = response.json()
            
            self.log(f"Статус ответа: {response.status_code}")
            
            if 'error' in data:
                self.log(f"❌ Ошибка API: {data['error']['error_msg']}")
                return []
            
            if 'response' in data and 'items' in data['response']:
                posts = data['response']['items']
                self.log(f"✅ Найдено постов через API: {len(posts)}")
                
                # Преобразуем в нужный формат
                formatted_posts = []
                for post in posts:
                    # Текст
                    text = post.get('text', '')
                    
                    # Фото
                    photos = []
                    if 'attachments' in post:
                        for attach in post['attachments']:
                            if attach['type'] == 'photo':
                                sizes = attach['photo']['sizes']
                                # Берем максимальный размер
                                max_size = max(sizes, key=lambda x: x.get('width', 0))
                                photos.append(max_size['url'])
                    
                    formatted_posts.append({
                        'id': post['id'],
                        'date': post['date'],
                        'text': text,
                        'photos': photos[:10]
                    })
                
                return formatted_posts
            else:
                self.log(f"❌ Странный ответ: {data}")
                return []
                
        except Exception as e:
            self.log(f"❌ Ошибка: {e}")
            return []
    
    def send_to_telegram(self, post):
        """Отправляет пост в Telegram"""
        self.log(f"Отправка поста {post['id']}")
        
        try:
            # Формируем текст
            text = post['text']
            if len(text) > 1024:
                text = text[:1021] + "..."
            
            # Добавляем дату
            date_str = datetime.fromtimestamp(post['date']).strftime('%d.%m.%Y %H:%M')
            text = f"📅 {date_str}\n\n{text}"
            
            # Если есть фото
            if post['photos']:
                media = []
                for i, photo_url in enumerate(post['photos'][:10]):
                    media_item = {
                        'type': 'photo',
                        'media': photo_url
                    }
                    if i == 0 and text:
                        media_item['caption'] = text[:1024]
                    media.append(media_item)
                
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
            
            # Только текст
            if text:
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
                data = {
                    'chat_id': TG_CHANNEL,
                    'text': text[:4096],
                    'disable_web_page_preview': False
                }
                response = requests.post(url, json=data, timeout=30)
                
                if response.status_code == 200:
                    self.log(f"✅ Текст отправлен")
                    return True
                else:
                    self.log(f"❌ Ошибка текста: {response.status_code}")
            
            return False
            
        except Exception as e:
            self.log(f"❌ Ошибка отправки: {e}")
            return False
    
    def catch_up_posts(self):
        """Догоняет пропущенные посты"""
        self.log("=" * 50)
        self.log("🚀 ДОГОН ПРОПУЩЕННЫХ ЧЕРЕЗ API")
        
        posts = self.get_vk_posts_api()
        
        if not posts:
            self.log("❌ Нет постов")
            return 0
        
        self.log(f"📦 Получено постов: {len(posts)}")
        
        # Сортируем по дате (новые сверху)
        posts.sort(key=lambda x: x['date'], reverse=True)
        
        # Показываем первые 3
        for i, post in enumerate(posts[:3]):
            self.log(f"📌 Пост {i+1}: {post['id']} - {post['text'][:50]}...")
        
        # Отправляем последние 10
        sent = 0
        for post in reversed(posts[:10]):
            if self.send_to_telegram(post):
                sent += 1
                self.save_state(post['id'])
                time.sleep(2)
        
        self.log(f"✅ Отправлено: {sent}")
        return sent
    
    def test_api(self):
        """Тест API"""
        self.log("🔍 ТЕСТ API ВК")
        posts = self.get_vk_posts_api()
        if posts:
            self.log(f"✅ API РАБОТАЕТ! Найдено {len(posts)} постов")
            return True
        else:
            self.log("❌ API НЕ РАБОТАЕТ")
            return False
    
    def test_telegram(self):
        """Тест Telegram"""
        self.log("🔍 ТЕСТ TELEGRAM")
        
        test_text = f"✅ ТЕСТ ЧЕРЕЗ API\nВремя: {datetime.now().strftime('%H:%M:%S')}"
        
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        data = {
            'chat_id': TG_CHANNEL,
            'text': test_text
        }
        
        try:
            response = requests.post(url, json=data, timeout=10)
            if response.status_code == 200:
                self.log("✅ TELEGRAM РАБОТАЕТ")
                return True
            else:
                self.log(f"❌ Ошибка: {response.status_code}")
                return False
        except Exception as e:
            self.log(f"❌ Ошибка: {e}")
            return False

# ============================================
# ЗАПУСК
# ============================================
if __name__ == "__main__":
    parser = VKApiParser()
    
    print("=" * 60)
    print("🚀 ПАРСЕР ЧЕРЕЗ API ВК (БЕЗ ТОКЕНА)")
    print("=" * 60)
    
    if not TG_TOKEN:
        print("❌ НЕТ TG_TOKEN")
        sys.exit(1)
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1].replace('--', '')
        print(f"📌 КОМАНДА: {cmd}")
        
        if cmd == 'catchup':
            parser.catch_up_posts()
        elif cmd == 'test':
            parser.test_telegram()
            parser.test_api()
        elif cmd == 'api':
            parser.test_api()
    else:
        parser.catch_up_posts()
