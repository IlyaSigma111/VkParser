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
VK_GROUP = "rddmnt"
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
                text = post.get('text', '')
                text = self.clean_vk_links(text)
                
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
                            
                            video_info = self.get_video_info(video_owner, video_id)
                            
                            if video_info:
                                title = video_info['title']
                                duration = video_info['duration']
                                duration_str = self.format_duration(duration)
                                video_url = f"https://vk.com/video{video_owner}_{video_id}"
                                
                                videos.append({
                                    'title': title,
                                    'url': video_url,
                                    'duration': duration_str
                                })
                            else:
                                video_url = f"https://vk.com/video{video_owner}_{video_id}"
                                title = video.get('title', 'Видео')
                                videos.append({
                                    'title': title,
                                    'url': video_url,
                                    'duration': '??:??'
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
                
                # Формируем полный текст поста
                full_text = text
                
                # Добавляем видео в текст
                if videos:
                    full_text += "\n\n🎬 **Видео:**\n"
                    for video in videos:
                        full_text += f"• {video['title']} ({video['duration']})\n{video['url']}\n\n"
                
                # Добавляем ссылки в текст
                if links:
                    full_text += "\n🔗 **Ссылки:**\n" + "\n".join(links) + "\n"
                
                # Добавляем документы в текст
                if docs:
                    full_text += "\n📎 **Документы:**\n" + "\n".join(docs) + "\n"
                
                post_data = {
                    'id': post['id'],
                    'date': post['date'],
                    'text': full_text.strip(),
                    'photos': photos[:10]
                }
                
                formatted_posts.append(post_data)
                
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
        """Отправляет пост в Telegram - ФОТО ВМЕСТЕ С ТЕКСТОМ"""
        try:
            # Форматируем дату
            date_str = datetime.fromtimestamp(post['date']).strftime('%d.%m.%Y %H:%M')
            
            # Полный текст с датой
            full_text = f"📅 {date_str}\n\n{post['text']}"
            
            # Если есть фото - отправляем альбомом с подписью
            if post['photos']:
                media = []
                for i, photo in enumerate(post['photos'][:10]):
                    media_item = {
                        'type': 'photo',
                        'media': photo
                    }
                    # Подпись ТОЛЬКО к первому фото и со ВСЕМ текстом
                    if i == 0:
                        # Если текст слишком длинный для подписи (лимит 1024)
                        if len(full_text) > 1024:
                            # Берем первую часть текста
                            caption = full_text[:1024]
                            media_item['caption'] = caption
                            
                            # Отправляем фото
                            url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMediaGroup"
                            data = {
                                'chat_id': TG_CHANNEL,
                                'media': json.dumps(media)
                            }
                            
                            response = requests.post(url, data=data, timeout=30)
                            
                            if response.status_code == 200:
                                self.log(f"✅ Отправлено {len(post['photos'])} фото с частью текста")
                                
                                # Отправляем остаток текста отдельно
                                remaining_text = full_text[1024:]
                                if remaining_text.strip():
                                    time.sleep(2)
                                    self.log("📤 Отправка остатка текста")
                                    return self.send_text_only(remaining_text)
                            else:
                                self.log(f"❌ Ошибка фото: {response.status_code}")
                                return self.send_text_only(full_text)
                        else:
                            # Текст помещается в подпись
                            media_item['caption'] = full_text
                            media.append(media_item)
                            
                            url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMediaGroup"
                            data = {
                                'chat_id': TG_CHANNEL,
                                'media': json.dumps(media)
                            }
                            
                            response = requests.post(url, data=data, timeout=30)
                            
                            if response.status_code == 200:
                                self.log(f"✅ Отправлено {len(post['photos'])} фото с полным текстом")
                                return True
                            else:
                                self.log(f"❌ Ошибка фото: {response.status_code}")
                                return self.send_text_only(full_text)
                    else:
                        media.append(media_item)
                
                return True
            
            # Если нет фото - просто текст
            return self.send_text_only(full_text)
            
        except Exception as e:
            self.log(f"❌ Ошибка отправки: {e}")
            return False
    
    def send_text_only(self, text):
        """Отправляет только текст"""
        try:
            url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
            
            # Проверяем длину
            text_len = len(text)
            
            # Если текст не превышает лимит - отправляем целиком
            if text_len <= 4096:
                data = {'chat_id': TG_CHANNEL, 'text': text}
                response = requests.post(url, json=data, timeout=30)
                if response.status_code == 200:
                    self.log("✅ Текст отправлен целиком")
                    return True
                else:
                    self.log(f"❌ Ошибка: {response.status_code}")
                    return False
            
            # Если текст слишком длинный - разбиваем
            self.log(f"⚠️ Текст длинный ({text_len} символов), разбиваем")
            
            # Разбиваем по абзацам
            parts = []
            current_part = ""
            
            for paragraph in text.split('\n\n'):
                if len(current_part) + len(paragraph) + 2 < 4096:
                    if current_part:
                        current_part += "\n\n" + paragraph
                    else:
                        current_part = paragraph
                else:
                    if current_part:
                        parts.append(current_part)
                    current_part = paragraph
            
            if current_part:
                parts.append(current_part)
            
            # Отправляем части
            for i, part in enumerate(parts, 1):
                if i == 1:
                    part_text = part
                else:
                    part_text = f"📌 Продолжение ({i}/{len(parts)}):\n\n{part}"
                
                data = {'chat_id': TG_CHANNEL, 'text': part_text[:4096]}
                response = requests.post(url, json=data, timeout=30)
                
                if response.status_code == 200:
                    self.log(f"✅ Часть {i}/{len(parts)} отправлена")
                else:
                    self.log(f"❌ Ошибка части {i}: {response.status_code}")
                
                time.sleep(1)
            
            return True
                
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
        
        new_posts = []
        if state.get('first_run') or not state['last_post_id']:
            new_posts = posts[:5]
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
        
        total_photos = sum(len(p['photos']) for p in new_posts)
        self.log(f"📊 Статистика: 📸 {total_photos} фото")
        
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
                time.sleep(3)
        
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
            self.log(f"   Текст: {post['text'][:100]}...")
            self.log(f"   📸 Фото: {len(post['photos'])}")
            return True
        return False

if __name__ == "__main__":
    parser = VKParser()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1].replace('--', '')
        if cmd == 'catchup':
            parser.catch_up(20)
        elif cmd == 'test':
            parser.test()
        else:
            print("Команды: --catchup, --test")
    else:
        parser.catch_up(10)
