import requests
from bs4 import BeautifulSoup
import json
import os
import sys
import time
import re
from datetime import datetime

# ============================================
# НАСТРОЙКИ (берутся из переменных окружения)
# ============================================
VK_GROUP = os.environ.get('VK_GROUP', 'rddmnt')
TG_TOKEN = os.environ.get('TG_TOKEN', '')
TG_CHANNEL = os.environ.get('TG_CHANNEL', '-1003761499584')
CHECK_INTERVAL = 60  # секунд между проверками

# ============================================
# КЛАСС ПАРСЕРА
# ============================================
class VKtoTGParser:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'
        })
        self.state_file = 'vk_parser_state.json'
        self.log_file = 'parser_log.txt'
        
    def log(self, message, level="INFO"):
        """Логирование с временем"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_msg = f"[{timestamp}] [{level}] {message}"
        print(log_msg)
        
        # Сохраняем в файл
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_msg + '\n')
        except:
            pass
    
    def load_state(self):
        """Загружает состояние последнего поста"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.log(f"Ошибка загрузки состояния: {e}", "ERROR")
        
        return {'last_post_id': None, 'last_post_date': None, 'first_run': True}
    
    def save_state(self, post_id, post_date=None):
        """Сохраняет состояние"""
        try:
            state = {
                'last_post_id': post_id,
                'last_post_date': post_date or datetime.now().isoformat(),
                'first_run': False
            }
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            self.log(f"Состояние сохранено: {post_id}")
        except Exception as e:
            self.log(f"Ошибка сохранения состояния: {e}", "ERROR")
    
    def get_vk_posts(self, limit=20):
        """Парсит посты из ВК"""
        self.log(f"Парсинг ВК группы: {VK_GROUP}")
        posts = []
        
        try:
            # Формируем URL
            if VK_GROUP.isdigit():
                url = f"https://vk.com/public{VK_GROUP}"
            else:
                url = f"https://vk.com/{VK_GROUP}"
            
            self.log(f"Загрузка страницы: {url}")
            response = self.session.get(url, timeout=15)
            
            if response.status_code != 200:
                self.log(f"Ошибка загрузки: {response.status_code}", "ERROR")
                return []
            
            self.log(f"Страница загружена, размер: {len(response.text)} байт")
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Ищем посты
            post_elements = soup.find_all('div', {'class': 'post'})
            if not post_elements:
                post_elements = soup.find_all('div', {'data-post-id': True})
            
            self.log(f"Найдено элементов постов: {len(post_elements)}")
            
            for i, post in enumerate(post_elements[:limit]):
                try:
                    post_data = self.parse_post_element(post)
                    if post_data:
                        posts.append(post_data)
                        self.log(f"Пост {i+1}: ID={post_data['id']}, фото={len(post_data['photos'])}")
                except Exception as e:
                    self.log(f"Ошибка парсинга поста {i}: {e}", "ERROR")
                    continue
            
            # Сортируем по ID (новые сначала)
            posts.sort(key=lambda x: x['id'], reverse=True)
            self.log(f"Всего постов после парсинга: {len(posts)}")
            
        except Exception as e:
            self.log(f"Критическая ошибка парсинга: {e}", "ERROR")
        
        return posts
    
    def parse_post_element(self, post_element):
        """Парсит один элемент поста"""
        # ID поста
        post_id = None
        
        # Пробуем из data-post-id
        if post_element.get('data-post-id'):
            post_id = post_element.get('data-post-id')
        
        # Пробуем из ссылки
        if not post_id:
            post_link = post_element.find('a', {'class': 'post_link'})
            if post_link and post_link.get('href'):
                match = re.search(r'wall(-?\d+_\d+)', post_link['href'])
                if match:
                    post_id = match.group(1)
        
        # Пробуем из id
        if not post_id and post_element.get('id'):
            match = re.search(r'post(\d+)_(\d+)', post_element.get('id'))
            if match:
                post_id = f"{match.group(1)}_{match.group(2)}"
        
        if not post_id:
            return None
        
        # Текст поста
        text = ""
        text_block = post_element.find('div', {'class': 'wall_post_text'})
        if text_block:
            text = text_block.get_text(strip=True)
        
        # Дата
        date = ""
        date_block = post_element.find('span', {'class': 'rel_date'})
        if date_block:
            date = date_block.get_text(strip=True)
        
        # Фото
        photos = []
        img_blocks = post_element.find_all('img')
        for img in img_blocks:
            src = img.get('src', '')
            if 'vk.com' in src or 'userapi.com' in src:
                # Берем максимальный размер
                clean_url = src.split('?')[0]
                if clean_url not in photos:
                    photos.append(clean_url)
        
        # Ограничиваем количество фото
        photos = photos[:10]
        
        return {
            'id': post_id,
            'text': text,
            'date': date,
            'photos': photos,
            'url': f"https://vk.com/wall{post_id}"
        }
    
    def send_to_telegram(self, post):
        """Отправляет пост в Telegram"""
        self.log(f"Отправка поста {post['id']} в Telegram")
        
        try:
            # Если есть фото
            if post['photos']:
                media = []
                for i, photo_url in enumerate(post['photos']):
                    media_item = {
                        'type': 'photo',
                        'media': photo_url
                    }
                    # Подпись только к первому фото
                    if i == 0 and post['text']:
                        caption = post['text'][:1024]  # лимит Telegram
                        media_item['caption'] = caption
                    media.append(media_item)
                
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMediaGroup"
                data = {
                    'chat_id': TG_CHANNEL,
                    'media': json.dumps(media)
                }
                response = requests.post(url, data=data, timeout=30)
                
                if response.status_code == 200:
                    self.log(f"✅ Пост с фото отправлен")
                    return True
                else:
                    self.log(f"❌ Ошибка отправки фото: {response.text[:200]}", "ERROR")
                    
                    # Пробуем отправить без фото
                    if post['text']:
                        return self.send_text_only(post['text'])
                    return False
            
            # Только текст
            elif post['text']:
                return self.send_text_only(post['text'])
            
            return False
            
        except Exception as e:
            self.log(f"❌ Ошибка отправки: {e}", "ERROR")
            return False
    
    def send_text_only(self, text):
        """Отправляет только текст"""
        try:
            url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
            data = {
                'chat_id': TG_CHANNEL,
                'text': text[:4096],  # лимит Telegram
                'disable_web_page_preview': False
            }
            response = requests.post(url, json=data, timeout=30)
            
            if response.status_code == 200:
                self.log(f"✅ Текст отправлен")
                return True
            else:
                self.log(f"❌ Ошибка отправки текста: {response.text[:200]}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Ошибка отправки текста: {e}", "ERROR")
            return False
    
    def check_new_posts(self):
        """Проверяет новые посты"""
        self.log("=" * 50)
        self.log("ЗАПУСК ПРОВЕРКИ НОВЫХ ПОСТОВ")
        self.log("=" * 50)
        
        state = self.load_state()
        self.log(f"Текущее состояние: last_id={state['last_post_id']}, first_run={state.get('first_run', True)}")
        
        posts = self.get_vk_posts(limit=30)
        if not posts:
            self.log("❌ Нет постов в ВК", "ERROR")
            return 0
        
        # Определяем новые посты
        new_posts = []
        
        if state.get('first_run', True) or not state['last_post_id']:
            self.log("🆕 Первый запуск - отправляем последний пост")
            new_posts = [posts[0]] if posts else []
        else:
            for post in posts:
                if post['id'] == state['last_post_id']:
                    break
                new_posts.append(post)
        
        self.log(f"Найдено новых постов: {len(new_posts)}")
        
        # Отправляем в обратном порядке (хронология)
        sent_count = 0
        for post in reversed(new_posts):
            self.log(f"📤 Отправка поста {post['id']}")
            if self.send_to_telegram(post):
                sent_count += 1
                self.save_state(post['id'], post['date'])
                time.sleep(2)  # пауза между постами
            else:
                self.log(f"❌ Не удалось отправить пост {post['id']}", "ERROR")
        
        self.log(f"✅ Отправлено: {sent_count} из {len(new_posts)}")
        return sent_count
    
    def catch_up_posts(self):
        """Догоняет пропущенные посты"""
        self.log("=" * 50)
        self.log("ЗАПУСК ДОГОНА ПРОПУЩЕННЫХ ПОСТОВ")
        self.log("=" * 50)
        
        state = self.load_state()
        posts = self.get_vk_posts(limit=50)
        
        if not posts:
            self.log("❌ Нет постов в ВК", "ERROR")
            return 0
        
        # Определяем посты для догона
        if state.get('first_run', True) or not state['last_post_id']:
            self.log("🆕 Первый запуск - отправляем последние 10 постов")
            posts_to_catch = posts[:10]
        else:
            for i, post in enumerate(posts):
                if post['id'] == state['last_post_id']:
                    posts_to_catch = posts[:i]
                    break
            else:
                posts_to_catch = posts[:10]
        
        self.log(f"Найдено постов для догона: {len(posts_to_catch)}")
        
        if not posts_to_catch:
            self.log("✨ Нет постов для догона")
            return 0
        
        # Отправляем
        sent_count = 0
        for post in reversed(posts_to_catch):
            self.log(f"📤 Отправка поста {post['id']}")
            if self.send_to_telegram(post):
                sent_count += 1
                self.save_state(post['id'], post['date'])
                time.sleep(2)
            else:
                self.log(f"❌ Не удалось отправить пост {post['id']}", "ERROR")
        
        self.log(f"✅ Отправлено: {sent_count} из {len(posts_to_catch)}")
        return sent_count
    
    def reset_state(self):
        """Сбрасывает состояние"""
        self.save_state(None, None)
        self.log("🔄 Состояние сброшено")
        self.send_to_telegram({
            'id': 'reset',
            'text': '🔄 Состояние парсера сброшено',
            'photos': []
        })
    
    def test_telegram(self):
        """Тестирует подключение к Telegram"""
        self.log("🔍 ТЕСТ ПОДКЛЮЧЕНИЯ К TELEGRAM")
        
        test_post = {
            'id': 'test',
            'text': f'✅ Тестовое сообщение от парсера VK→TG\n\nВремя: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\nГруппа: {VK_GROUP}',
            'photos': []
        }
        
        result = self.send_to_telegram(test_post)
        if result:
            self.log("✅ Тест успешен")
        else:
            self.log("❌ Тест провален", "ERROR")
        return result

# ============================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================
def main():
    parser = VKtoTGParser()
    
    # Проверяем наличие токенов
    if not TG_TOKEN:
        parser.log("❌ ОШИБКА: TG_TOKEN не задан!", "ERROR")
        sys.exit(1)
    
    if not TG_CHANNEL:
        parser.log("❌ ОШИБКА: TG_CHANNEL не задан!", "ERROR")
        sys.exit(1)
    
    parser.log(f"✅ Парсер инициализирован")
    parser.log(f"📌 VK_GROUP: {VK_GROUP}")
    parser.log(f"📌 TG_CHANNEL: {TG_CHANNEL}")
    
    # Разбор аргументов командной строки
    if len(sys.argv) > 1:
        command = sys.argv[1].replace('--', '')
        parser.log(f"📌 Команда: {command}")
        
        if command == 'check':
            parser.check_new_posts()
        elif command == 'catchup':
            parser.catch_up_posts()
        elif command == 'reset':
            parser.reset_state()
        elif command == 'test':
            parser.test_telegram()
        else:
            parser.log(f"❌ Неизвестная команда: {command}", "ERROR")
            print("""
Доступные команды:
  --check    - проверить новые посты
  --catchup  - догнать пропущенные
  --reset    - сбросить состояние
  --test     - тест Telegram
            """)
    else:
        # По умолчанию проверяем новые
        parser.check_new_posts()

if __name__ == "__main__":
    main()
