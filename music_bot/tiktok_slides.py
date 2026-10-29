"""Public TikTok photo-post fallback: ordered slides plus their exposed soundtrack."""
import ipaddress
import json
import math
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import aiohttp
from .youtube_fetch import FetchError

class SlideshowUnavailable(FetchError):
    pass

class PublicResolver(aiohttp.resolver.DefaultResolver):
    async def resolve(self, host, port=0, family=0):
        records = await super().resolve(host, port, family)
        if not records or any(not ipaddress.ip_address(item['host']).is_global for item in records):
            raise OSError('Nonpublic destination')
        return records

def safe_url(url, media=False):
    try:
        u=urlsplit(url)
        host=(u.hostname or '').lower()
        allowed=({'www.tiktok.com','tiktok.com','vm.tiktok.com','vt.tiktok.com'} if not media else set())
        suffixes=('tiktokcdn.com','tiktokcdn-us.com','tiktokcdn-eu.com','byteoversea.com','ibytedtos.com','muscdn.com','tiktokv.com')
        return (u.scheme=='https' and not u.username and not u.password and u.port in (None,443)
            and '\\' not in url and len(url)<8192 and not any(c.isspace() or ord(c)<32 for c in url)
            and (host in allowed or media and any(host==s or host.endswith('.'+s) for s in suffixes)))
    except ValueError:
        return False

def parse_item(html):
    found=re.search(r'<script[^>]+id=["\']__UNIVERSAL_DATA_FOR_REHYDRATION__["\'][^>]*>(.*?)</script>',html,re.S)
    if not found:return None
    try:
        data=json.loads(found[1])
        return data['__DEFAULT_SCOPE__']['webapp.video-detail']['itemInfo']['itemStruct']
    except (ValueError,KeyError,TypeError):
        return None

def assets(item, post_id, require_music=True):
    if not isinstance(item,dict) or str(item.get('id'))!=post_id:
        raise SlideshowUnavailable('Slideshow unavailable.')
    post=item.get('imagePost')
    rows=post.get('images',[]) if isinstance(post,dict) else []
    if not isinstance(rows,list) or not 1<=len(rows)<=35:
        raise SlideshowUnavailable('Slideshow unavailable.')
    images=[]
    for row in rows:
        image=row.get('imageURL') if isinstance(row,dict) else None
        urls=image.get('urlList',[]) if isinstance(image,dict) else []
        if not isinstance(urls,list):urls=[]
        url=next((u for u in urls if isinstance(u,str) and safe_url(u,True)),None)
        if not url:raise SlideshowUnavailable('Slideshow unavailable.')
        images.append(url)
    track=item.get('music')
    music=track.get('playUrl') if isinstance(track,dict) else None
    if require_music and (not isinstance(music,str) or not safe_url(music,True)):
        raise SlideshowUnavailable('Slideshow soundtrack unavailable.')
    return images,music

async def request(session,url,limit,media=False,target=None):
    for _ in range(5):
        if not safe_url(url,media):raise SlideshowUnavailable('Unsupported destination.')
        async with session.get(url,allow_redirects=False) as response:
            if response.status in (301,302,303,307,308):
                url=urljoin(url,response.headers.get('Location',''))
                continue
            if response.status!=200:raise SlideshowUnavailable('Public post unavailable.')
            count=0;raw=bytearray()
            with target.open('wb') if target else __import__('contextlib').nullcontext() as output:
                async for chunk in response.content.iter_chunked(32768):
                    count+=len(chunk)
                    if count>limit:raise SlideshowUnavailable('Post exceeds size limit.')
                    if output:output.write(chunk)
                    else:raw.extend(chunk)
            return bytes(raw),url,count
    raise SlideshowUnavailable('Too many redirects.')

async def fetch(url,directory,fetcher,alive,mode='video'):
    root=Path(directory)
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(resolver=PublicResolver()),
                timeout=aiohttp.ClientTimeout(total=20),
                headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.tiktok.com/'}) as session:
            raw,resolved,_=await request(session,url,3_000_000)
            match=re.search(r'/(?:photo|video)/(\d+)',urlsplit(resolved).path)
            if not match:raise SlideshowUnavailable('Post identity unavailable.')
            post_id=match[1];item=parse_item(raw.decode('utf-8',errors='replace'))
            if not item:
                # The public video-shaped page sometimes exposes photo-post data.
                from urllib.parse import urlunsplit
                u=urlsplit(resolved)
                alternate=urlunsplit((u.scheme,u.netloc,u.path.replace('/photo/','/video/'),'',''))
                if alternate!=resolved:
                    raw,_,_=await request(session,alternate,3_000_000)
                    item=parse_item(raw.decode('utf-8',errors='replace'))
            if not item:
                raw,_,_=await request(session,'https://www.tiktok.com/api/item/detail/?itemId='+post_id,3_000_000)
                try:item=json.loads(raw).get('itemInfo',{}).get('itemStruct')
                except (ValueError,AttributeError):item=None
            images,music=assets(item,post_id,require_music=mode!='pictures')
            budget=50_000_000
            for index,url in enumerate(images if mode!='audio' else []):
                target=root/f'slide{index:03d}.img'
                _,_,size=await request(session,url,min(budget,8_000_000),True,target)
                budget-=size
                with target.open('rb') as image:magic=image.read(12)
                if not (magic.startswith(b'\xff\xd8\xff') or magic.startswith(b'\x89PNG\r\n\x1a\n')
                        or magic.startswith(b'RIFF') and magic[8:12]==b'WEBP'):
                    raise SlideshowUnavailable('Unsupported slide image.')
            if mode=='pictures':
                photos=[]
                for index in range(len(images)):
                    source=root/f'slide{index:03d}.img';target=root/f'photo{index:03d}.jpg'
                    await fetcher.process(['ffmpeg','-nostdin','-v','error','-y','-protocol_whitelist','file,pipe',
                        '-i',str(source),'-frames:v','1','-vf','scale=1920:1920:force_original_aspect_ratio=decrease',
                        '-q:v','3',str(target)],directory,alive)
                    if not target.exists() or not 0<target.stat().st_size<=10_000_000:
                        raise SlideshowUnavailable('Picture unavailable.')
                    photos.append(target)
                    source.unlink()
                return photos
            audio=root/'soundtrack.media'
            await request(session,music,min(budget,20_000_000),True,audio)
        info=await fetcher.process(['ffprobe','-v','error','-protocol_whitelist','file,pipe','-format_whitelist','mov,mp3,aac,wav,ogg,flac',
            '-show_entries','format=duration','-of','json',str(audio)],directory,alive,output=True)
        duration=float(json.loads(info)['format']['duration'])
        if not math.isfinite(duration) or not 0<duration<=300:
            raise SlideshowUnavailable('Slideshow duration exceeds limit.')
        if mode=='audio':return audio
        timing=duration/len(images)
        lines=[]
        for index in range(len(images)):
            lines.extend([f"file 'slide{index:03d}.img'",f'duration {timing:.6f}'])
        lines.append(f"file 'slide{len(images)-1:03d}.img'")
        (root/'slides.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
        target=root/'post.mp4'
        await fetcher.process(['ffmpeg','-nostdin','-v','error','-y','-protocol_whitelist','file,pipe',
            '-f','concat','-safe','1','-i','slides.txt','-protocol_whitelist','file,pipe','-format_whitelist','mov,mp3,aac,wav,ogg,flac','-i',str(audio),
            '-map','0:v:0','-map','1:a:0','-vf',
            'scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=15',
            '-c:v','libx264','-preset','veryfast','-b:v','700k','-pix_fmt','yuv420p',
            '-c:a','aac','-b:a','128k','-t',str(duration),'-shortest','-movflags','+faststart',str(target)],
            directory,alive)
        if not target.exists() or not 0<target.stat().st_size<=50_000_000:
            raise SlideshowUnavailable('Slideshow exceeds size limit.')
        return target
    except SlideshowUnavailable:
        raise
    except (aiohttp.ClientError,OSError,ValueError,TypeError,KeyError):
        raise SlideshowUnavailable('Public slideshow unavailable.') from None

async def photo_post(url):
    """Offer pictures only when a public TikTok URL confirms photo mode."""
    if not safe_url(url):return False
    path=urlsplit(url).path
    if re.fullmatch(r'/@[^/]+/photo/\d+/?',path):return True
    if re.fullmatch(r'/@[^/]+/video/\d+/?',path):return False
    if urlsplit(url).hostname not in {'vm.tiktok.com','vt.tiktok.com','www.tiktok.com','tiktok.com'}:return False
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(resolver=PublicResolver()),
                timeout=aiohttp.ClientTimeout(total=8)) as session:
            async with __import__('asyncio').timeout(8):
                for _ in range(4):
                    if not safe_url(url):return False
                    path=urlsplit(url).path
                    if re.fullmatch(r'/@[^/]+/photo/\d+/?',path):return True
                    if re.fullmatch(r'/@[^/]+/video/\d+/?',path):return False
                    async with session.get(url,allow_redirects=False) as response:
                        if response.status not in (301,302,303,307,308):return False
                        url=urljoin(url,response.headers.get('Location',''))
    except (aiohttp.ClientError,OSError,TimeoutError,ValueError):
        return False
    return False
