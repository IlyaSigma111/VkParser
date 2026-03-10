import requests
import os
import sys
import time
import json
import re
from datetime import datetime

# ============================================
# НАСТРОЙКИ
# ============================================
VK_TOKEN = "vk1.a.khnFXow17S6vjHNn8_Za-VOcTV7GHFWBSAHG6Ehh52dNZZ2Tb4LncLZYPDmV2N9t_DO00n1pWS5cnrzaVdqGuhmKrxeWbL0FwUFCvrsset1HIRqpkxihvvwhxKKpVCN0oPXMPh19kxDbRjc9jS8EZA2-kEf5Zq5LVSGSjUh5w5l4_UegC0XZ1yI_XpMXcN9fjOs4XyeDlEfptx5MQMUecQ"
VK_GROUP = "rddmnt"  # Движение Первых
TG_TOKEN = os.environ.get('TG_TOKEN', '8773397643:AAHOe2bn7XrzPeZ3uzNgmgBh1R0knyYccJ4')
TG_CHANNEL = os.environ.get('TG_CHANNEL', '-1003761499584')

class VKParser:
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
            return {'last_post_id': None, 'first_run': True}
    
    def save_state(self, post_id):
        with open(self.state_file, 'w') as f:
            json.dump({'last_post_id': post_id, 'first_run': False}, f)
    
    def clean_vk_links(self, text):
        """Преобразует ссылки вида [id123|Имя] в обычный текст"""
        if not text:
            return text
            
        # Паттерн для [id123|Текст]
        pattern = r'\[(id\d+)\|([^\]]+)\]'
        text = re.sub(pattern, r'\2 (id\1)', text)
        
        # Паттерн для [club123|Название]
        pattern_club = r'\[(club\d+)\|([^\]]+)\]'
        text = re.sub(pattern_club, r'\2', text)
        
        return text
    
    def get_video_info(self, owner_id, video_id):
        """Получает информацию о видео"""
        try:
            params = {
                'videos': f"{owner_id}_{video_id}",
                'access_token': self.vk_token,
                'v': self.version
            }
            response = requests.get(self.api_url + "video.get", params=params, timeout=10)
            data = response.json()
            
            if 'response' in data and data['response']['items']:
                video = data['response']['items'][0]
                return {
                    'title': video.get('title', 'Видео'),
                    'player': video.get('player', ''),
                    'duration': video.get('duration', 0)
                }
        except:
            pass
        return None
    
    def format_duration(self, seconds):
        """Форматирует длительность видео"""
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"
    
    def get_posts(self, count=20):
        """Получает посты через API ВК"""
        self.log(f"Запрос постов для группы {VK_GROUP}")
        
        # Определяем owner_id
        if str(VK_GROUP).isdigit():
            owner_id = f"-{VK_GROUP}"
        else:
            owner_id = VK_GROUP
        
        params = {
            'owner_id': owner_id,
            'count': count,
            'access_token': self.vk_token,
            'v': self.version,
            'extended': 1
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
                # Текст с очисткой ссылок
                text = post.get('text', '')
                text = self.clean_vk_links(text)
                
                # Медиа файлы
                photos = []
                videos = []
                links = []
                docs = []
                
                if 'attachments' in post:
                    for attach in post['attachments']:
                        if attach['type'] == 'photo':
                            sizes = attach['photo']['sizes']
                            max_size = max(sizes, key=lambda x: x.get('width', 0))
                            photos.append(max_size['url'])
                        
                        elif attach['type'] == 'video':
                            video = attach['video']
                            video_id = video['id']
                            video_owner = video['owner_id']
                            
                            # Получаем доп инфо о видео
                            video_info = self.get_video_info(video_owner, video_id)
                            
                            if video_info:
                                title = video_info['title']
                                player = video_info['player']
                                duration = video_info['duration']
                                duration_str = self.format_duration(duration)
                                
                                # Формируем ссылку на видео
                                video_url = f"https://vk.com/video{video_owner}_{video_id}"
                                
                                videos.append({
                                    'title': title,
                                    'url': video_url,
                                    'player': player,
                                    'duration': duration_str,
                                    'owner_id': video_owner,
                                    'id': video_id
                                })
                            else:
                                # Если не получили инфо, хотя бы ссылку дадим
                                video_url = f"https://vk.com/video{video_owner}_{video_id}"
                                title = video.get('title', 'Видео')
                                videos.append({
                                    'title': title,
                                    'url': video_url,
                                    'player': '',
                                    'duration': '??:??',
                                    'owner_id': video_owner,
                                    'id': video_id
                                })
                        
                        elif attach['type'] == 'link':
                            link = attach['link']
                            link_title = link.get('title', 'Ссылка')
                            link_url = link.get('url', '')
                            links.append(f"🔗 {link_title}: {link_url}")
                        
                        elif attach['type'] == 'doc':
                            doc = attach['doc']
                            doc_title = doc.get('title', 'Документ')
                            doc_url = doc.get('url', '')
                            docs.append(f"📎 {doc_title}: {doc_url}")
                
                # Формируем пост
                post_data = {
                    'id': post['id'],
                    'date': post['date'],
                    'text': text,
                    'photos': photos[:10],
                    'videos': videos,
                    'links': links,
                    'docs': docs
                }
                
                formatted_posts.append(post_data)
                
                # Логируем найденные медиа
                media_info = []
                if photos: media_info.append(f"📸 {len(photos)}")
                if videos: media_info.append(f"🎬 {len(videos)}")
                if links: media_info.append(f"🔗 {len(links)}")
                if docs: media_info.append(f"📎 {len(docs)}")
                
                if media_info:
                    self.log(f"📦 Пост {post['id']}: {' '.join(media_info)}")
            
            return formatted_posts
            
        except Exception as e:
            self.log(f"❌ Ошибка: {e}")
            return []
    
    def send_to_telegram(self, post):
        """Отправляет пост в Telegram с полной поддержкой видео"""
        try:
            # Форматируем дату
            date_str = datetime.fromtimestamp(post['date']).strftime('%d.%m.%Y %H:%M')
            
            # Собираем текст
            text_parts = [f"📅 {date_str}"]
            
            if post['text']:
                text_parts.append(post['text'])
            
            # Добавляем видео
            if post['videos']:
                text_parts.append("\n🎬 **Видео:**")
                for video in post['videos']:
                    duration = video.get('duration', '??:??')
                    title = video.get('title', 'Видео')
                    url = video.get('url', '')
                    text_parts.append(f"• {title} ({duration})\n  {url}")
            
            # Добавляем ссылки
            if post['links']:
                text_parts.append("\n🔗 **Ссылки:**")
                text_parts.extend(post['links'])
            
            # Добавляем документы
            if post['docs']:
                text_parts.append("\n📎 **Документы:**")
                text_parts.extend(post['docs'])
            
            full_text = "\n\n".join(text_parts)
            
            # Если есть фото
            if post['photos']:
                media = []
                for i, photo in enumerate(post['photos'][:10]):
                    media_item = {
                        'type': 'photo',
                        'media': photo
                    }
                    # Подпись только к первому фото
                    if i == 0:
                        caption = full_text[:1024]
                        media_item['caption'] = caption
                    media.append(media_item)
                
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMediaGroup"
                data = {
                    'chat_id': TG_CHANNEL,
                    'media': json.dumps(media)
                }
                
                response = requests.post(url, data=data, timeout=30)
                
                if response.status_code == 200:
                    self.log(f"✅ Отправлено {len(post['photos'])} фото и медиа")
                    
                    # Если есть еще текст после фото, отправляем отдельно
                    if len(full_text) > 1024:
                        time.sleep(2)
                        remaining_text = full_text[1024:]
                        self.send_text_only(remaining_text)
                    
                    return True
                else:
                    self.log(f"❌ Ошибка фото: {response.status_code}")
                    # Пробуем отправить как текст
                    return self.send_text_only(full_text)
            
            # Только текст (или видео без фото)
            return self.send_text_only(full_text)
            
        except Exception as e:
            self.log(f"❌ Ошибка отправки: {e}")
            return False
    
    def send_text_only(self, text):
        """Отправляет только текст с разбивкой"""
        try:
            url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
            
            # Разбиваем длинный текст
            if len(text) > 4096:
                parts = [text[i:i+4096] for i in range(0, len(text), 4096)]
                for i, part in enumerate(parts):
                    data = {'chat_id': TG_CHANNEL, 'text': part}
                    response = requests.post(url, json=data, timeout=30)
                    self.log(f"📤 Часть {i+1}/{len(parts)}: {response.status_code}")
                    time.sleep(1)
                return True
            else:
                data = {'chat_id': TG_CHANNEL, 'text': text}
                response = requests.post(url, json=data, timeout=30)
                return response.status_code == 200
                
        except Exception as e:
            self.log(f"❌ Ошибка отправки текста: {e}")
            return False
    
    def catch_up(self, limit=20):
        """Догон постов"""
        self.log("=" * 60)
        self.log("🚀 ДОГОН ПОСТОВ")
        self.log(f"📌 Группа: {VK_GROUP}")
        self.log("=" * 60)
        
        posts = self.get_posts(limit)
        if not posts:
            self.log("❌ Нет постов")
            return
        
        state = self.load_state()
        self.log(f"💾 Последний сохраненный пост: {state['last_post_id']}")
        
        # Определяем новые посты
        new_posts = []
        if state.get('first_run') or not state['last_post_id']:
            new_posts = posts[:5]  # При первом запуске берем 5 последних
            self.log("🆕 Первый запуск - беру 5 последних")
        else:
            for post in posts:
                if str(post['id']) == str(state['last_post_id']):
                    break
                new_posts.append(post)
        
        self.log(f"📦 Новых постов для отправки: {len(new_posts)}")
        
        if not new_posts:
            self.log("✨ Нет новых постов")
            return
        
        # Статистика по медиа
        total_photos = sum(len(p['photos']) for p in new_posts)
        total_videos = sum(len(p['videos']) for p in new_posts)
        total_links = sum(len(p['links']) for p in new_posts)
        
        self.log(f"📊 Статистика: 📸 {total_photos} фото, 🎬 {total_videos} видео, 🔗 {total_links} ссылок")
        
        # Отправляем в хронологическом порядке
        sent = 0
        for i, post in enumerate(reversed(new_posts), 1):
            post_date = datetime.fromtimestamp(post['date']).strftime('%d.%m.%Y %H:%M')
            self.log(f"📤 [{i}/{len(new_posts)}] Отправка поста от {post_date}")
            
            if self.send_to_telegram(post):
                sent += 1
                self.save_state(post['id'])
                self.log(f"✅ Отправлен пост {post['id']}")
            else:
                self.log(f"❌ Ошибка отправки поста {post['id']}")
            
            if i < len(new_posts):
                time.sleep(3)  # Пауза между постами
        
        self.log(f"✅ Отправлено: {sent} из {len(new_posts)}")
    
    def test(self):
        """Тест подключения"""
        self.log("🔍 ТЕСТ ПОДКЛЮЧЕНИЯ")
        posts = self.get_posts(1)
        if posts:
            self.log(f"✅ API работает!")
            post = posts[0]
            post_date = datetime.fromtimestamp(post['date']).strftime('%d.%m.%Y')
            self.log(f"📝 Пример поста от {post_date}:")
            self.log(f"   {post['text'][:100]}...")
            self.log(f"   📸 Фото: {len(post['photos'])}, 🎬 Видео: {len(post['videos'])}")
            return True
        return False

if __name__ == "__main__":
    parser = VKParser()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1].replace('--', '')
        if cmd == 'catchup':
            parser.catch_up(20)  # Догон 20 постов
        elif cmd == 'test':
            parser.test()
        else:
            print("Команды: --catchup, --test")
    else:
        parser.catch_up(10)
