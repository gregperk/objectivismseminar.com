import errno
import feedparser
import json
import os
import re
import urllib.request
import urllib.parse
import time
from podgen import Podcast, Media, Episode, Category, Person

sessions_filename = 'sessions.json'
rss_filename = 'rss.xml'
download_dir = "./downloads"
bucket_prefix = 'https://oapodcasts.s3.amazonaws.com/'
feedUrl = ('https://www.freeconferencecall.com/rss/podcast' +
           '?id=2dd4f6a755aa45d0e05e72cc2367b2611992a141827eb6addeed79c5baf445fe_292812442')

feed_items = feedparser.parse(feedUrl)['entries']
session_items = json.load(open(sessions_filename))


def safe_name(title):
    return re.sub(r'[:/]', '_', title)


def copyfileobj(fsrc, fdst, callback, length=16*1024):
    copied = 0
    while True:
        buf = fsrc.read(length)
        if not buf:
            break
        fdst.write(buf)
        copied += len(buf)
        callback(copied)


# identify new items by title
new_items = []
for item in feed_items:
    link_info = [x for x in item['links'] if x['type'] == 'audio/mp3'][0]
    if 0 == len([session_item for session_item in session_items
                 if item['title'] == session_item['title']]):
        new_items.append({
            'title': item['title'],
            'sourcelink': link_info['href'],
            'link': urllib.parse.quote(f'{bucket_prefix}{safe_name(item["title"])}.mp3'),
            'length': int(link_info['length']),
            'description': "Please visit www.ObjectivismSeminar.com for more information.",
            'pubDate': time.strftime('%Y-%m-%dT%H:%M:%SZ', item['published_parsed'])
        })

# ensure downloads directory is in place
if not os.path.exists(download_dir):
    try:
        os.makedirs(download_dir)
    except OSError as exc:  # Guard against race condition
        if exc.errno != errno.EEXIST:
            raise

# download new items
for item in new_items:
    url = item.pop('sourcelink')
    length = item['length']
    title = item['title']

    def progress(bytes_read):
        print(f'{title}... {int(100 * bytes_read/length)}% downloaded', end='\r')

    file_path = f'{download_dir}/{safe_name(title)}.mp3'
    print(f'{title}... 0% downloaded', end='\r')
    with urllib.request.urlopen(url) as response, open(file_path, 'wb') as out_file:
        copyfileobj(response, out_file, progress)
        print(f'{title}... 100% downloaded')

# write the new sessions json file
new_session_items = new_items + session_items
with open('x-' + sessions_filename, 'w') as outfile:
    json.dump(new_session_items, outfile, indent=2)

print('wrote sessions file')

# write the new podcast rss file
p = Podcast()

p.name = "The Objectivism Seminar"
p.category = Category("Society &amp; Culture", "Philosophy")
p.language = "en-US"
p.explicit = True
p.description = ("A weekly online conference call to systematically study " +
                 "the philosophy of Objectivism via the works of prominent Rand scholars.")
p.website = "https://www.objectivismseminar.com"
p.image = "https://www.objectivismseminar.com/assets/images/atlas-square.jpg"
p.feed_url = "https://www.objectivismseminar.com/archives/rss"
p.authors = [Person("Greg Perkins", "greg@ecosmos.com")]
p.owner = p.authors[0]

p.episodes += [Episode(title=x['title'],
                       media=Media(x['link'], type="audio/mpeg", size=x.get('length', 0)),
                       publication_date=x['pubDate'],
                       summary=x['description']) for x in new_session_items]

p.rss_file(rss_filename)

print('wrote rss file')

#
# TODO:
#
# take out the x- on the written sessions file
#
# should set Episode id (i.e., guid) to the OLD link (that's what it defaults to now),
# then for future episodes can switch to new links.
#
# identify new episodes by pubDate instead of title?
#
