import requests
from bs4 import BeautifulSoup
import time
import json
import os
import re
from datetime import datetime
import sys

VK_GROUP = os.environ.get('VK_GROUP', 'rddmnt')
TG_TOKEN = os.environ.get('TG_TOKEN', '')
TG_CHANNEL = os.environ.get('TG_CHANNEL', '')

class VKParser:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.state_file = 'parser_state.json'
        
    def load_state(self):
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except:
            return {'last_post_id': None, 'first_run': True}
    
    def save_state(self, post_id):
        with open(self.state_file, 'w') as f:
            json.dump({'last_post_id': post_id, 'first_run': False}, f)
    
    def get_vk_posts(self, limit=20):
        try:
            url = f"https://vk.com/{VK_GROUP}"
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            posts = []
            post_blocks = soup.find_all('div', {'class': 'post'})
            
            for block in post_blocks[:limit]:
                try:
                    post_link = block.find('a', {'class': 'post_link'})
                    if not post_link:
                        continue
                        
                    match = re.search(r'wall(-?\d+_\d+)', post_link['href'])
                    if not match:
                        continue
                    
                    post_id = match.group(1)
                    text_block = block.find('div', {'class': 'wall_post_text'})
                    text = text_block.get_text(strip=True) if text_block else ""
                    
                    photos = []
                    img_blocks = block.find_all('img', {'class': 'photo_img'})
                    for img in img_blocks[:10]:
                        if img.get('src'):
                            photos.append(img['src'])
                    
                    posts.append({
                        'id': post_id,
                        'text': text[:4096],
                        'photos': photos
                    })
                except:
                    continue
            
            return sorted(posts, key=lambda x: x['id'], reverse=True)
        except:
            return []
    
    def send_to_telegram(self, post):
        try:
            if post['photos']:
                media = []
                for i, photo in enumerate(post['photos'][:10]):
                    media_item = {'type': 'photo', 'media': photo}
                    if i == 0 and post['text']:
                        media_item['caption'] = post['text'][:1024]
                    media.append(media_item)
                
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMediaGroup"
                data = {'chat_id': TG_CHANNEL, 'media': json.dumps(media)}
                return requests.post(url, data=data, timeout=30).status_code == 200
            elif post['text']:
                url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
                data = {'chat_id': TG_CHANNEL, 'text': post['text'][:4096]}
                return requests.post(url, json=data, timeout=30).status_code == 200
            return False
        except:
            return False
    
    def check_new_posts(self):
        state = self.load_state()
        posts = self.get_vk_posts(limit=20)
        
        if not posts:
            return 0
        
        new_posts = []
        if state.get('first_run'):
            new_posts = [posts[0]] if posts else []
        else:
            for post in posts:
                if post['id'] == state['last_post_id']:
                    break
                new_posts.append(post)
        
        sent = 0
        for post in reversed(new_posts):
            if self.send_to_telegram(post):
                sent += 1
                self.save_state(post['id'])
                time.sleep(2)
        
        return sent
    
    def catch_up_posts(self):
        state = self.load_state()
        posts = self.get_vk_posts(limit=50)
        
        if not posts:
            return 0
        
        if state.get('first_run'):
            posts_to_catch = posts[:10]
        else:
            for i, post in enumerate(posts):
                if post['id'] == state['last_post_id']:
                    posts_to_catch = posts[:i]
                    break
            else:
                posts_to_catch = posts[:10]
        
        sent = 0
        for post in reversed(posts_to_catch):
            if self.send_to_telegram(post):
                sent += 1
                self.save_state(post['id'])
                time.sleep(2)
        
        return sent
    
    def reset_state(self):
        self.save_state(None)

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
        parser.check_new_posts()

if __name__ == "__main__":
    main()
