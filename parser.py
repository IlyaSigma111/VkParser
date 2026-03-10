import requests
import os
import sys
import time
import json
from datetime import datetime

# ============================================
# НАСТРОЙКИ
# ============================================
VK_TOKEN = "vk1.a.khnFXow17S6vjHNn8_Za-VOcTV7GHFWBSAHG6Ehh52dNZZ2Tb4LncLZYPDmV2N9t_DO00n1pWS5cnrzaVdqGuhmKrxeWbL0FwUFCvrsset1HIRqpkxihvvwhxKKpVCN0oPXMPh19kxDbRjc9jS8EZA2-kEf5Zq5LVSGSjUh5w5l4_UegC0XZ1yI_XpMXcN9fjOs4XyeDlEfptx5MQMUecQ"
VK_GROUP = os.environ.get('VK_GROUP', '236551315')  # Твоя группа
TG_TOKEN = os.environ.get('TG_TOKEN', '')
TG_CHANNEL = os.environ.get('TG_CHANNEL', '-1003761499584')

class VKTokenParser:
    def __init__(self):
        self.api_url = "https://api.vk.com/method/"
        self.vk_token = VK_TOKEN
        self.version = "5.131"
        self.state_file = 'vk_state.json'
        
    def log(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    
    def load_state(self):
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except:
            return {'last_post_id': None}
    
    def save_state(self, post_id):
        with open(self.state_file, 'w') as f:
            json.dump({'last_post_id': post_id}, f)
    
    def get_posts(self):
        """Получает посты через API ВК с токеном"""
        self.log(f"Запрос постов для группы {VK_GROUP}")
        
        # Определяем owner_id (для групп нужно с минусом)
        if VK_GROUP.isdigit():
            owner_id = f"-{VK_GROUP}"
        else:
            owner_id = VK_GROUP
        
        params = {
            'owner_id': owner_id,
            'count': 10,
            'access_token': self.vk_token,
            'v': self.version
        }
        
        try:
            response = requests.get(self.api_url + "wall.get", params=params, timeout=10)
            data = response.json()
            
            if 'error' in data:
                self.log(f"❌ Ошибка API: {data['error']['error_msg']}")
                return []
            
            posts = data['response']['items']
            self.log(f"✅ Получено постов: {len(posts)}")
            
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
                            # Берем максимальное фото
                            max_size = max(sizes, key=lambda x: x.get('width', 0))
                            photos.append(max_size['url'])
                
                formatted_posts.append({
                    'id': post['id'],
                    'date': post['date'],
                    'text': text,
                    'photos': photos[:10]
                })
            
            return formatted_posts
            
        except Exception as e:
            self.log(f"❌ Ошибка: {e}")
            return []
    
    def send_to_telegram(self, post):
        """Отправляет пост в Telegram"""
        try:
            # Форматируем дату
            date_str = datetime.fromtimestamp(post['date']).strftime('%d.%m.%Y %H:%M')
            text = f"📅 {date_str}\n\n{post['text']}"
            
            if post['photos']:
                media = []
                for i, photo in enumerate(post['photos'][:10]):
                    media_item = {
                        'type': 'photo',
                        'media': photo
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
                return response.status_code == 200
            
            if text:
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
                data = {
                    'chat_id': TG_CHANNEL,
                    'text': text[:4096]
                }
                response = requests.post(url, json=data, timeout=30)
                return response.status_code == 200
            
            return False
        except Exception as e:
            self.log(f"Ошибка отправки: {e}")
            return False
    
    def catch_up(self):
        """Догон постов"""
        self.log("=" * 50)
        self.log("🚀 ДОГОН ПОСТОВ ЧЕРЕЗ API С ТОКЕНОМ")
        
        posts = self.get_posts()
        if not posts:
            self.log("❌ Нет постов")
            return
        
        state = self.load_state()
        self.log(f"Последний сохраненный пост: {state['last_post_id']}")
        
        sent = 0
        for post in posts[:10]:
            if self.send_to_telegram(post):
                sent += 1
                self.save_state(post['id'])
                self.log(f"✅ Отправлен пост {post['id']}")
                time.sleep(2)
        
        self.log(f"✅ Отправлено: {sent}")
    
    def test(self):
        """Тест подключения"""
        self.log("🔍 ТЕСТ ПОДКЛЮЧЕНИЯ")
        posts = self.get_posts()
        if posts:
            self.log(f"✅ API работает! Найдено {len(posts)} постов")
            return True
        return False

if __name__ == "__main__":
    parser = VKTokenParser()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1].replace('--', '')
        if cmd == 'catchup':
            parser.catch_up()
        elif cmd == 'test':
            parser.test()
    else:
        parser.catch_up()
