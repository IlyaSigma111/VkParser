import requests
from bs4 import BeautifulSoup
import time
import json
import os
import re
from datetime import datetime
import sys

# Твои данные
VK_GROUP = "rddmnt"  # Короткое имя паблика
TG_TOKEN = "8773397643:AAHOe2bn7XrzPeZ3uzNgmgBh1R0knyYccJ4"  # Токен бота
TG_CHANNEL = "-1003761499584"  # ID каналаimport requests
from bs4 import BeautifulSoup
import time
import json
import os
import re
from datetime import datetime
import sys

# Загрузка настроек из переменных окружения (GitHub Secrets)
VK_GROUP = os.environ.get('VK_GROUP', 'rddmnt')
TG_TOKEN = os.environ.get('TG_TOKEN', '')
TG_CHANNEL = os.environ.get('TG_CHANNEL', '')

class VKParser:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.state_file = 'parser_state.json'
        self.stats_file = 'stats.json'
        
    def load_state(self):
        """Загружает состояние последнего поста"""
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {'last_post_id': None, 'last_post_date': None, 'first_run': True}
    
    def save_state(self, post_id, post_date, first_run=False):
        """Сохраняет состояние"""
        with open(self.state_file, 'w') as f:
            json.dump({
                'last_post_id': post_id,
                'last_post_date': post_date,
                'first_run': first_run
            }, f)
    
    def update_stats(self, sent_count=0):
        """Обновляет статистику"""
        try:
            stats = {'total': 0, 'today': 0, 'last_date': ''}
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    stats = json.load(f)
            
            today = datetime.now().strftime('%Y-%m-%d')
            
            if stats.get('last_date') != today:
                stats['today'] = sent_count
                stats['last_date'] = today
            else:
                stats['today'] = stats.get('today', 0) + sent_count
            
            stats['total'] = stats.get('total', 0) + sent_count
            
            with open(self.stats_file, 'w') as f:
                json.dump(stats, f)
            
            return stats
        except:
            return {'total': 0, 'today': 0}
    
    def get_telegram_last_post(self):
        """Пытается получить последний пост из Telegram канала"""
        try:
            url = f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates"
            response = requests.get(url, params={'limit': 100})
            data = response.json()
            
            if data.get('ok') and data.get('result'):
                # Ищем последнее сообщение в нужном канале
                for update in reversed(data['result']):
                    if 'message' in update:
                        msg = update['message']
                        chat_id = str(msg.get('chat', {}).get('id'))
                        if chat_id == str(TG_CHANNEL) or chat_id == TG_CHANNEL:
                            # Нашли сообщение в нашем канале
                            return {
                                'id': msg.get('message_id'),
                                'text': msg.get('text', ''),
                                'date': msg.get('date')
                            }
            return None
        except Exception as e:
            print(f"Ошибка получения данных из Telegram: {e}")
            return None
    
    def get_vk_posts(self, limit=30):
        """Получает посты из ВК"""
        try:
            # Формируем URL
            if VK_GROUP.isdigit():
                url = f"https://vk.com/public{VK_GROUP}"
            else:
                url = f"https://vk.com/{VK_GROUP}"
            
            print(f"Парсинг {url}")
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                print(f"Ошибка загрузки: {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Ищем посты
            posts = []
            
            # Пробуем разные селекторы
            post_blocks = soup.find_all('div', {'class': 'post'})
            if not post_blocks:
                post_blocks = soup.find_all('div', {'data-post-id': True})
            if not post_blocks:
                post_blocks = soup.find_all('div', {'id': re.compile(r'post\d+')})
            
            print(f"Найдено блоков постов: {len(post_blocks)}")
            
            for block in post_blocks[:limit]:
                try:
                    # ID поста
                    post_id = None
                    
                    # Пробуем из data-атрибута
                    if block.get('data-post-id'):
                        post_id = block.get('data-post-id')
                    
                    # Пробуем из ссылки
                    if not post_id:
                        post_link = block.find('a', {'class': 'post_link'})
                        if post_link and post_link.get('href'):
                            match = re.search(r'wall(-?\d+_\d+)', post_link['href'])
                            if match:
                                post_id = match.group(1)
                    
                    # Пробуем из id блока
                    if not post_id and block.get('id'):
                        match = re.search(r'post(\d+)_(\d+)', block.get('id'))
                        if match:
                            post_id = f"{match.group(1)}_{match.group(2)}"
                    
                    # Текст
                    text_block = block.find('div', {'class': 'wall_post_text'})
                    text = text_block.get_text(strip=True) if text_block else ""
                    
                    # Дата
                    date_block = block.find('span', {'class': 'rel_date'})
                    date = date_block.get_text(strip=True) if date_block else datetime.now().strftime("%Y-%m-%d")
                    
                    # Фото
                    photos = []
                    img_blocks = block.find_all('img')
                    for img in img_blocks:
                        if img.get('src') and ('sun' in img['src'] or 'userapi.com' in img['src']):
                            # Берем максимальный размер
                            photo_url = img['src'].split('?')[0]
                            if photo_url not in photos:
                                photos.append(photo_url)
                    
                    if post_id:
                        post_data = {
                            'id': str(post_id),
                            'text': text[:4096] if text else "",
                            'date': date,
                            'photos': photos[:10],
                            'url': f"https://vk.com/wall{post_id}"
                        }
                        posts.append(post_data)
                        print(f"Найден пост: {post_id}, фото: {len(photos)}")
                        
                except Exception as e:
                    print(f"Ошибка парсинга поста: {e}")
                    continue
            
            # Сортируем по ID (новые сначала)
            posts.sort(key=lambda x: x['id'], reverse=True)
            return posts
            
        except Exception as e:
            print(f"Ошибка: {e}")
            return []
    
    def send_to_telegram(self, post):
        """Отправляет пост в Telegram"""
        try:
            # Если есть фото
            if post['photos']:
                media = []
                for i, photo in enumerate(post['photos'][:10]):
                    media_item = {
                        'type': 'photo',
                        'media': photo
                    }
                    if i == 0 and post['text']:
                        caption = post['text'][:1024]
                        media_item['caption'] = caption
                    media.append(media_item)
                
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMediaGroup"
                data = {
                    'chat_id': TG_CHANNEL,
                    'media': json.dumps(media)
                }
                response = requests.post(url, data=data, timeout=30)
                return response.status_code == 200
            
            # Только текст
            elif post['text']:
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
                data = {
                    'chat_id': TG_CHANNEL,
                    'text': post['text'][:4096],
                    'disable_web_page_preview': False
                }
                response = requests.post(url, json=data, timeout=30)
                return response.status_code == 200
            
            return False
            
        except Exception as e:
            print(f"Ошибка отправки: {e}")
            return False
    
    def check_new_posts(self):
        """Проверяет новые посты"""
        print(f"\n{'='*50}")
        print(f"Запуск проверки в {datetime.now()}")
        print(f"Группа ВК: {VK_GROUP}")
        print(f"Канал TG: {TG_CHANNEL}")
        print(f"{'='*50}\n")
        
        state = self.load_state()
        posts = self.get_vk_posts(limit=20)
        
        if not posts:
            print("❌ Посты в ВК не найдены")
            return 0
        
        print(f"📦 Всего постов в ВК: {len(posts)}")
        print(f"📊 Состояние: last_id={state['last_post_id']}, first_run={state.get('first_run', True)}")
        
        # Определяем новые посты
        new_posts = []
        
        if state.get('first_run', True) or not state['last_post_id']:
            print("🎯 Первый запуск!")
            
            # Проверяем, есть ли посты в Telegram
            tg_last = self.get_telegram_last_post()
            
            if tg_last:
                print(f"📨 В Telegram есть посты, догоняем...")
                # Ищем посты после последнего в TG
                for post in posts:
                    if post['id'] == state.get('last_post_id'):
                        break
                    new_posts.append(post)
            else:
                print("🆕 Канал пустой - отправляем последний пост")
                new_posts = [posts[0]] if posts else []
        else:
            # Обычный режим
            for post in posts:
                if post['id'] == state['last_post_id']:
                    break
                new_posts.append(post)
        
        print(f"🆕 Новых постов для отправки: {len(new_posts)}")
        
        # Отправляем
        sent = 0
        for post in reversed(new_posts):
            print(f"📤 Отправка поста {post['id']}")
            if self.send_to_telegram(post):
                sent += 1
                self.save_state(post['id'], post['date'], first_run=False)
                print(f"✅ Отправлен ({sent}/{len(new_posts)})")
            else:
                print(f"❌ Ошибка на посте {post['id']}")
            time.sleep(2)
        
        # Обновляем статистику
        if sent > 0:
            stats = self.update_stats(sent)
            print(f"📊 Статистика: всего {stats['total']}, сегодня {stats['today']}")
        
        print(f"\n✨ Готово! Отправлено: {sent}\n")
        return sent
    
    def catch_up_posts(self):
        """Догоняет пропущенные посты"""
        print(f"\n{'='*50}")
        print(f"Запуск догона в {datetime.now()}")
        print(f"{'='*50}\n")
        
        state = self.load_state()
        posts = self.get_vk_posts(limit=50)
        
        if not posts:
            print("❌ Нет постов в ВК")
            return 0
        
        print(f"📦 Всего постов в ВК: {len(posts)}")
        
        # Определяем посты для догона
        if state.get('first_run', True) or not state['last_post_id']:
            print("🆕 Канал пустой. Сколько постов отправить?")
            print("1 - последний пост")
            print("5 - последние 5")
            print("10 - последние 10")
            print("20 - последние 20")
            
            choice = input("Выбери количество (1/5/10/20): ").strip()
            
            if choice == '1':
                posts_to_catch = posts[:1]
            elif choice == '5':
                posts_to_catch = posts[:5]
            elif choice == '10':
                posts_to_catch = posts[:10]
            else:
                posts_to_catch = posts[:20]
        else:
            # Ищем индекс последнего поста
            last_index = -1
            for i, post in enumerate(posts):
                if post['id'] == state['last_post_id']:
                    last_index = i
                    break
            
            if last_index >= 0:
                posts_to_catch = posts[:last_index]
            else:
                print("⚠️ Последний пост не найден, отправляю последние 10")
                posts_to_catch = posts[:10]
        
        print(f"📦 Найдено для догона: {len(posts_to_catch)}")
        
        if not posts_to_catch:
            print("✨ Нет постов для догона")
            return 0
        
        # Подтверждение
        print(f"\nБудет отправлено {len(posts_to_catch)} постов")
        confirm = input("Продолжить? (y/n): ").strip().lower()
        
        if confirm != 'y':
            print("❌ Отменено")
            return 0
        
        # Отправляем
        sent = 0
        for post in reversed(posts_to_catch):
            print(f"📤 Отправка {post['id']}")
            if self.send_to_telegram(post):
                sent += 1
                self.save_state(post['id'], post['date'], first_run=False)
                print(f"✅ Отправлен ({sent}/{len(posts_to_catch)})")
            else:
                print(f"❌ Ошибка на {post['id']}")
            time.sleep(2)
        
        # Обновляем статистику
        if sent > 0:
            stats = self.update_stats(sent)
            print(f"📊 Статистика: всего {stats['total']}, сегодня {stats['today']}")
        
        print(f"\n✨ Догон завершен. Отправлено: {sent}\n")
        return sent
    
    def reset_state(self):
        """Сбрасывает состояние"""
        self.save_state(None, None, first_run=True)
        print("🔄 Состояние сброшено. Следующий запуск будет как первый.")

def main():
    parser = VKParser()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--catchup':
            parser.catch_up_posts()
        elif sys.argv[1] == '--check':
            parser.check_new_posts()
        elif sys.argv[1] == '--reset':
            parser.reset_state()
        else:
            print("Использование:")
            print("  python parser.py --check    # Проверить новые")
            print("  python parser.py --catchup  # Догнать пропущенные")
            print("  python parser.py --reset    # Сбросить состояние")
    else:
        parser.check_new_posts()

if __name__ == "__main__":
    main()

class VKParser:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.state_file = 'parser_state.json'
        
    def load_state(self):
        """Загружает состояние последнего поста"""
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except:
            return {'last_post_id': None, 'last_post_date': None, 'first_run': True}
    
    def save_state(self, post_id, post_date, first_run=False):
        """Сохраняет состояние"""
        with open(self.state_file, 'w') as f:
            json.dump({
                'last_post_id': post_id,
                'last_post_date': post_date,
                'first_run': first_run
            }, f)
    
    def get_telegram_last_post(self):
        """Пытается получить последний пост из Telegram канала"""
        try:
            url = f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates"
            response = requests.get(url, params={'limit': 1})
            data = response.json()
            
            if data.get('ok') and data.get('result'):
                # Ищем последнее сообщение в нужном канале
                for update in reversed(data['result']):
                    if 'message' in update:
                        msg = update['message']
                        if str(msg.get('chat', {}).get('id')) == str(TG_CHANNEL):
                            # Нашли сообщение в нашем канале
                            return {
                                'id': msg.get('message_id'),
                                'text': msg.get('text', ''),
                                'date': msg.get('date')
                            }
            return None
        except Exception as e:
            print(f"Ошибка получения данных из Telegram: {e}")
            return None
    
    def get_all_posts(self, limit=20):
        """Получает посты из ВК"""
        try:
            # Формируем URL
            if VK_GROUP.isdigit():
                url = f"https://vk.com/public{VK_GROUP}"
            else:
                url = f"https://vk.com/{VK_GROUP}"
            
            print(f"Парсинг {url}")
            response = self.session.get(url)
            
            if response.status_code != 200:
                print(f"Ошибка загрузки: {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Ищем посты
            posts = []
            post_blocks = soup.find_all('div', {'class': 'post'})
            
            if not post_blocks:
                # Пробуем другой селектор
                post_blocks = soup.find_all('div', {'data-post-id': True})
            
            for block in post_blocks[:limit]:
                try:
                    # ID поста
                    post_link = block.find('a', {'class': 'post_link'})
                    post_id = None
                    if post_link and post_link.get('href'):
                        match = re.search(r'wall(-?\d+_\d+)', post_link['href'])
                        if match:
                            post_id = match.group(1)
                    
                    if not post_id:
                        # Пробуем из data-атрибута
                        post_id = block.get('data-post-id')
                    
                    # Текст
                    text_block = block.find('div', {'class': 'wall_post_text'})
                    text = text_block.get_text(strip=True) if text_block else ""
                    
                    # Дата
                    date_block = block.find('span', {'class': 'rel_date'})
                    date = date_block.get_text(strip=True) if date_block else datetime.now().strftime("%Y-%m-%d")
                    
                    # Фото
                    photos = []
                    img_blocks = block.find_all('img', {'class': 'photo_img'})
                    for img in img_blocks[:10]:
                        if img.get('src'):
                            # Берем максимальный размер
                            photo_url = img['src'].replace('&type=q', '&type=o').replace('&type=s', '&type=o')
                            photos.append(photo_url)
                    
                    if post_id:
                        posts.append({
                            'id': str(post_id),
                            'text': text,
                            'date': date,
                            'photos': photos,
                            'url': f"https://vk.com/wall{post_id}"
                        })
                except Exception as e:
                    print(f"Ошибка парсинга поста: {e}")
                    continue
            
            # Сортируем по ID (новые сначала)
            posts.sort(key=lambda x: x['id'], reverse=True)
            return posts
            
        except Exception as e:
            print(f"Ошибка: {e}")
            return []
    
    def send_to_telegram(self, post):
        """Отправляет пост в Telegram"""
        try:
            # Если есть фото
            if post['photos']:
                media = []
                for i, photo in enumerate(post['photos'][:10]):  # Лимит TG - 10 фото
                    media_item = {
                        'type': 'photo',
                        'media': photo
                    }
                    if i == 0 and post['text']:
                        # Обрезаем длинный текст
                        caption = post['text'][:1024]
                        media_item['caption'] = caption
                    media.append(media_item)
                
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMediaGroup"
                data = {
                    'chat_id': TG_CHANNEL,
                    'media': json.dumps(media)
                }
                response = requests.post(url, data=data)
                return response.status_code == 200
            
            # Только текст
            elif post['text']:
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
                data = {
                    'chat_id': TG_CHANNEL,
                    'text': post['text'][:4096],  # Лимит TG на текст
                    'disable_web_page_preview': False
                }
                response = requests.post(url, json=data)
                return response.status_code == 200
            
            return False
            
        except Exception as e:
            print(f"Ошибка отправки: {e}")
            return False
    
    def check_new_posts(self):
        """Проверяет новые посты (умная логика)"""
        state = self.load_state()
        posts = self.get_all_posts(20)
        
        if not posts:
            print("❌ Посты в ВК не найдены")
            return
        
        print(f"📦 Всего постов в ВК: {len(posts)}")
        print(f"📊 Состояние: last_id={state['last_post_id']}, first_run={state.get('first_run', False)}")
        
        # Если это первый запуск ИЛИ канал пустой
        if state.get('first_run', True) or not state['last_post_id']:
            print("🎯 Первый запуск или пустой канал!")
            
            # Пробуем получить последний пост из Telegram
            tg_last = self.get_telegram_last_post()
            
            if tg_last:
                print(f"📨 Найден последний пост в TG: {tg_last.get('id')}")
                # Есть посты в TG - используем обычную логику
                new_posts = []
                for post in posts:
                    if post['id'] == state['last_post_id']:
                        break
                    new_posts.append(post)
            else:
                print("🆕 Канал пустой - отправляем ТОЛЬКО последний пост")
                # Отправляем только самый свежий пост
                new_posts = [posts[0]] if posts else []
                # Сразу помечаем, что отправили последний
                if new_posts:
                    self.save_state(posts[0]['id'], posts[0]['date'], first_run=False)
        else:
            # Обычный режим - только новые
            new_posts = []
            for post in posts:
                if post['id'] == state['last_post_id']:
                    break
                new_posts.append(post)
        
        print(f"🆕 Новых постов для отправки: {len(new_posts)}")
        
        # Отправляем в хронологическом порядке
        sent = 0
        for post in reversed(new_posts):
            print(f"📤 Отправка поста {post['id']}")
            if self.send_to_telegram(post):
                sent += 1
                self.save_state(post['id'], post['date'], first_run=False)
                print(f"✅ Отправлен ({sent}/{len(new_posts)})")
            else:
                print(f"❌ Ошибка на посте {post['id']}")
            time.sleep(1)
        
        print(f"✨ Готово! Отправлено: {sent}")
        return sent
    
    def catch_up_posts(self):
        """Догоняет все пропущенные посты"""
        state = self.load_state()
        print(f"⏪ Догон постов. Последний известный: {state['last_post_id']}")
        
        # Получаем больше постов
        posts = self.get_all_posts(50)
        
        if not posts:
            print("❌ Нет постов в ВК")
            return
        
        # Если канал пустой
        if state.get('first_run', True) or not state['last_post_id']:
            print("🆕 Канал пустой - сколько постов отправлять?")
            print("1️⃣ Отправить только последний")
            print("2️⃣ Отправить последние 5")
            print("3️⃣ Отправить последние 10")
            print("4️⃣ Отправить все")
            
            choice = input("Выбери (1-4): ").strip()
            
            if choice == '1':
                posts_to_catch = posts[:1]
            elif choice == '2':
                posts_to_catch = posts[:5]
            elif choice == '3':
                posts_to_catch = posts[:10]
            else:
                posts_to_catch = posts[:20]  # Ограничим 20 постами
        else:
            # Обычный догон - все после последнего
            last_index = -1
            for i, post in enumerate(posts):
                if post['id'] == state['last_post_id']:
                    last_index = i
                    break
            
            if last_index >= 0:
                posts_to_catch = posts[:last_index]
            else:
                posts_to_catch = posts
                print("⚠️ Последний пост не найден, отправляю последние 10")
                posts_to_catch = posts[:10]
        
        print(f"📦 Найдено для догона: {len(posts_to_catch)}")
        
        # Отправляем
        sent = 0
        for post in reversed(posts_to_catch):
            print(f"📤 Отправка {post['id']}")
            if self.send_to_telegram(post):
                sent += 1
                self.save_state(post['id'], post['date'], first_run=False)
                print(f"✅ Отправлен ({sent}/{len(posts_to_catch)})")
            else:
                print(f"❌ Ошибка на {post['id']}")
            time.sleep(1)
        
        print(f"✨ Догон завершен. Отправлено: {sent}")

def main():
    parser = VKParser()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--catchup':
            parser.catch_up_posts()
        elif sys.argv[1] == '--check':
            parser.check_new_posts()
        elif sys.argv[1] == '--reset':
            # Сброс состояния (как будто первый запуск)
            parser.save_state(None, None, first_run=True)
            print("🔄 Состояние сброшено. Следующий запуск будет как первый.")
    else:
        parser.check_new_posts()

if __name__ == "__main__":
    main()

